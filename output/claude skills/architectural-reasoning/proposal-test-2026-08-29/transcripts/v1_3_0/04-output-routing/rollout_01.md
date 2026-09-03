# ADR: Extract Fulfillment into an Independently Deployable Service

## Status

Proposed

## Context

`OrderService.place_order` (`orders_service/service.py:2-7`) runs order creation, inventory reservation, payment charge, and fulfillment as one synchronous call stack:

```
order = self._create_order(cart)
self._reserve_inventory(order)
self._charge_payment(order)
self._fulfill(order)  # packs, labels, and schedules carrier pickup -- same process, same deploy
```

`_fulfill` (`service.py:9-11`) generates a pick list and requests carrier pickup — physical-fulfillment work with a different load shape (bursty around pickup cutoffs) and a different change cadence (packing/label/carrier logic) than order-taking (cart checkout, payment). `deploy.yaml` confirms both are currently one deployable — `service: orders`, 4 replicas, 500m CPU — with a comment stating explicitly that order-taking and fulfillment "scale and deploy together." Any capacity or release decision made for one is forced onto the other today.

The driver for this change is explicit: fulfillment needs to scale and deploy independently of order-taking. That is a deployment/scaling justification, which is sufficient grounds for a runtime service boundary (not just a module boundary).

## Decision

Extract fulfillment into a standalone **FulfillmentService** with its own deployable and scaling policy, decoupled from `OrderService` by an **asynchronous event**, not a synchronous call.

**Ownership split:**

| Responsibility | Owner |
|---|---|
| Order record (cart, items, payment status) | OrderService (unchanged) |
| Inventory reservation | OrderService (unchanged) |
| Payment charge | OrderService (unchanged) |
| Pick list generation | FulfillmentService (new, sole owner) |
| Carrier pickup scheduling | FulfillmentService (new, sole owner) |
| Fulfillment state (scheduled/failed/completed) | FulfillmentService writes; OrderService holds a read-only projection only |

**Contract:** after `_charge_payment` succeeds, OrderService publishes an `OrderReadyForFulfillment` event (order id, line items, shipping destination, reservation reference) instead of calling `_fulfill` in-process. FulfillmentService consumes it idempotently and emits `OrderFulfillmentScheduled` or `OrderFulfillmentFailed`. OrderService subscribes to that outcome only to update its own status projection — it must not become a second writer of fulfillment state, or the two services will drift out of sync on retries/redeploys.

This is the primary decision this ADR is making, and it is the one point worth defending explicitly: **the call must be async, not a network-ified version of today's synchronous call.** A synchronous HTTP/RPC replacement would preserve today's shape but reintroduce the exact coupling the split is meant to remove — `place_order` would still block on FulfillmentService being up and fast, so a fulfillment incident becomes a checkout incident, and the two services still can't be deployed on independent schedules without one blocking the other's request path.

## Consequences

**Positive**
- Fulfillment can scale (replica count, CPU) and deploy on its own schedule, per the stated goal — `deploy.yaml` becomes two manifests with independent policies.
- A fulfillment outage or slow deploy no longer blocks checkout/payment.
- Pick-list and carrier logic can iterate without redeploying order-taking.

**Negative / new risks**
- **New failure mode requiring compensation.** Today, if `_fulfill` throws, `place_order` fails *after* `_charge_payment` has already run, with no visible refund or inventory-release path in `service.py` — this is a latent gap in the current code, not something the split introduces. Moving fulfillment out makes this failure mode explicit and asynchronous: an `OrderFulfillmentFailed` event must drive a compensating action (refund, inventory release, customer notice) in OrderService. This must ship before cutover, not after — it closes an existing gap as well as a new one.
- **Delivery guarantees.** The event channel must be at-least-once with an idempotent consumer, or a lost message silently strands a paid order with no fulfillment triggered. Needs a reconciliation check (alert if no fulfillment ack within SLA of payment).
- **Two independently deployable systems** instead of one — more operational surface (two on-call rotations' worth of failure modes, one new network hop, one new message contract to version).

## Alternatives Considered

1. **Synchronous RPC to a separate FulfillmentService.** Rejected as the primary path — preserves temporal coupling between checkout and fulfillment, undermining the independent-scaling/deploy goal that motivated the split. Worth revisiting only if checkout must display carrier-pickup confirmation before completing (see Open Design Decisions).
2. **Stay monolithic, scale fulfillment via an internal worker pool/flag.** Rejected — does not satisfy the explicit requirement to deploy fulfillment changes without redeploying order-taking.
3. **Status quo.** Rejected per the stated driver.

## Migration Plan

1. Introduce the `OrderReadyForFulfillment` / `OrderFulfillmentScheduled|Failed` event contract *inside* the current monolith first: OrderService publishes it, an in-process handler still calls the existing `_generate_pick_list` / `_request_carrier_pickup` logic. Same deploy, behavior-preserving — proves the contract before any network split.
2. Stand up FulfillmentService as a separate deployable consuming the same event over the real broker, run it in shadow (dual-consume, compare outputs) alongside the in-process path.
3. Implement and test the compensation path for `OrderFulfillmentFailed` — this must pass before cutover, since it closes both the pre-existing gap and the new async failure mode.
4. Cut traffic to FulfillmentService, remove `_fulfill` and its helpers from OrderService, split `deploy.yaml` into `orders` and `fulfillment` manifests with independent replica/CPU settings. Remove the shadow path once output parity holds for an agreed window.

## Validation

- Degrade/kill FulfillmentService and load-test order-taking: checkout latency and availability must be unaffected.
- Force a payment-charged-then-fulfillment-fails case: confirm the compensating refund/inventory-release fires and no order is left "paid, never fulfilled" past the alert SLA.
- Ship a fulfillment-only change and confirm zero OrderService deploys/restarts occurred.
- Burst carrier-pickup-scheduling load and confirm FulfillmentService scales independently with no change to `orders` replica count.

## Open Design Decisions

1. **Does checkout need synchronous confirmation of fulfillment scheduling** (e.g., shown to the customer before checkout completes)? Nothing in the provided code implies this. If true, the async design still stands, but checkout UX needs a polling/callback affordance rather than assuming instant confirmation. Resolve with the checkout/product owner.
2. **How does FulfillmentService get the inventory-location data it needs to build a pick list** — embedded fully in the event payload, or a direct read against the system `_reserve_inventory` writes to? Not resolvable from the files in scope (no inventory service code present). Resolve by inspecting `_reserve_inventory`'s data model.
3. **Messaging substrate.** No existing broker is referenced in the provided files. The choice (queue vs. log vs. pub/sub) determines the idempotency and ordering guarantees FulfillmentService's consumer must implement. Resolve against whatever messaging infrastructure the org already runs.
4. **Compensation orchestration.** Should OrderService own the refund/release logic directly on receiving `OrderFulfillmentFailed`, or should a separate saga/orchestrator coordinate it? Either resolves the gap; the choice affects how many services need to change if a third step is added to fulfillment later. Resolve before Migration step 3.
