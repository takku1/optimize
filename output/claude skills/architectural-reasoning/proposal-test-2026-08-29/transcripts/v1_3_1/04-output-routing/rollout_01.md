# ADR: Extract Fulfillment into an Independently Deployable Service

## Status
Proposed

## Context
`OrderService.place_order` (service.py:2-7) runs four steps in a single synchronous call stack: `_create_order`, `_reserve_inventory`, `_charge_payment`, `_fulfill`. `_fulfill` (service.py:9-11) generates a pick list and requests carrier pickup — packing, labeling, and carrier scheduling. The inline comment at service.py:6 states this runs "same process, same deploy" as order-taking.

`deploy.yaml` defines a single deployable (`service: orders`, 4 replicas, `cpu_request: 500m`) covering both order-taking and fulfillment; its top comment states explicitly that the two "scale and deploy together" today.

No message broker, queue, async boundary, retry logic, or separate fulfillment module is visible in the code — `_fulfill` is a private method on `OrderService`, called in-line. There is no exception handling around `_reserve_inventory`, `_charge_payment`, or `_fulfill`; a failure in any step propagates uncaught, with no visible rollback of already-applied side effects (e.g., an exception in `_fulfill` after payment has already been charged).

Request: split fulfillment out of this monolith into its own service so it can scale and deploy independently of order-taking.

## Forces
- **Independent scaling.** Fulfillment work (pick-list generation, carrier scheduling) likely has a different load profile than order-taking (payment, inventory) — e.g., bursts around carrier pickup windows versus steady checkout traffic. The single deployable in deploy.yaml forces both to share replica count and CPU allocation. *(Empirical performance)*
- **Independent deploy.** The shared deployable means a fulfillment-only change (carrier integration, packing logic) requires redeploying order-taking, and vice versa, increasing blast radius and coupling releases that have no reason to ship together. *(Evolutionary architecture)*
- **Ownership.** Pick-list generation and carrier pickup are a distinct domain responsibility from cart/order creation, inventory reservation, and payment. Today they share one owner (`OrderService`) with no module boundary between them. *(Information hiding / ownership)*
- **Failure containment.** Extraction replaces an in-process call with a network call. The existing code has no compensation logic if a later step fails after an earlier one has committed (e.g., payment charged, then fulfillment fails); this gap is latent today but a network hop makes partial failure materially more frequent. *(Fault containment / recovery)*
- **Contract coupling.** `place_order` currently returns only after fulfillment has been initiated (service.py:6-7). The new boundary must decide whether "order placed" still implies "fulfillment initiated," or whether these become separately observable outcomes. *(End-to-end responsibility)*

## Options

**A — Synchronous RPC/HTTP call from Orders to a separate Fulfillment service.**
Move `_generate_pick_list` and `_request_carrier_pickup` behind a Fulfillment service API; Orders calls it synchronously where `_fulfill()` is today. Preserves the current return-after-fulfillment-initiated contract with the smallest code change.
Rejected as the primary decision: it buys independent *deploy* but not independent *scaling* or *availability* — Orders' request thread blocks on Fulfillment's latency, and a Fulfillment outage becomes an Orders outage. That contradicts the stated goal and turns a same-process call into a hard synchronous dependency without gaining resilience.

**B — Asynchronous, event-driven handoff (recommended).**
Orders persists the order and durably publishes an `OrderPlaced` event after `_charge_payment` succeeds; `place_order` returns at that point. Fulfillment consumes the event independently, owns pick-list generation and carrier scheduling, and scales/deploys on its own schedule.
Achieves both independent scaling and independent deploy, and removes Fulfillment's latency/availability from Orders' request path.
Cost: introduces eventual consistency (an order is "placed" before fulfillment is confirmed initiated) and requires durability guarantees — outbox pattern, idempotent consumption keyed by order id, retry/DLQ — that don't exist in the current code.

**C — Status quo (single deployable).**
Rejected — this is the condition the ADR exists to change; it directly blocks independent scaling and deploy, the stated requirement.

## Decision
Adopt **Option B**. Extract Fulfillment as its own service, owning `_generate_pick_list` and `_request_carrier_pickup` (service.py:10-11) and its own deploy/scaling configuration — replacing the single entry in deploy.yaml with two deployables, each independently sized. Orders retains `_create_order`, `_reserve_inventory`, `_charge_payment`, and becomes the owner/publisher of an order-placed event; it no longer calls fulfillment logic directly. Write the event via a transactional outbox alongside the order-commit write, to avoid a dual-write race between "order committed" and "event published." Fulfillment consumes the event using order id as an idempotency key so re-delivery doesn't duplicate a carrier pickup request.

`place_order`'s return contract changes as a direct consequence: it returns once payment is confirmed, not once fulfillment is initiated. Any caller that today implicitly relies on "order returned successfully" meaning "carrier pickup requested" needs a new way to observe fulfillment status (see open decisions below).

## Consequences
**Gains:** Fulfillment and Orders scale and deploy independently, matching the stated goal; Orders' checkout latency and availability are no longer coupled to carrier/packing systems; fulfillment logic and its failure modes become explicit and testable in isolation instead of buried in a private method.

**Costs:** eventual consistency between order placement and fulfillment initiation, where none was visible before; new failure modes (event lost, delayed, or duplicated) replace the old one (uncaught exception aborts the whole call); new operational surface (outbox table or equivalent, broker/queue, DLQ, monitoring for stuck or failed fulfillment events) that doesn't exist today.

**Pre-existing risk this migration surfaces rather than creates:** service.py shows no compensation for `_reserve_inventory` or `_charge_payment` if a later step fails. Extracting fulfillment does not fix this — Orders still needs explicit handling (or an accepted-risk note) for "payment charged, inventory reserved, order-placed event fails to publish," since the outbox pattern only guarantees the event given a successful order commit, not resilience of the steps before it.

## Open design decisions
- **OPEN DESIGN DECISION:** transport/broker technology for the order-placed event (e.g., existing message infra vs. new). Nothing in service.py or deploy.yaml indicates what messaging infrastructure, if any, is already operated by this team — resolve against that inventory rather than here.
- **OPEN DESIGN DECISION:** how a caller learns fulfillment status after `place_order` returns (poll a Fulfillment API, push notification, or no change to caller-facing behavior). Not visible in the provided code; resolve with whoever owns the caller-facing contract for `place_order`.
- **OPEN DESIGN DECISION:** retry/backoff and DLQ policy for failed fulfillment consumption, and the on-call path for stuck orders. Resolve with an explicit SLO for time from order placed to fulfillment initiated.

## Validation and reversal
Validate before rollout:
1. A component test asserting Fulfillment's event consumption is idempotent under duplicate delivery of the same order id.
2. A load test confirming Fulfillment can scale its replica count independently of Orders under a fulfillment-only traffic spike — the scenario the current shared replica count in deploy.yaml cannot handle.
3. A fault-injection test confirming a Fulfillment outage does not block or fail `place_order` — this is the specific claim that justifies choosing B over A.

Reversal condition: if event-consumption latency or duplicate-delivery handling proves harder to operate than the coupling it removes (e.g., sustained DLQ backlog, unacceptable time-to-fulfillment), fall back to Option A (synchronous call) as an intermediate step — trading scaling/availability independence for operational simplicity — rather than reverting to the single-deployable monolith.
