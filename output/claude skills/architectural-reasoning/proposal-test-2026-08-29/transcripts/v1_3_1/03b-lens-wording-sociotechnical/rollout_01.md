## Recommendation

Don't fix this by loosening code review or adding people to Platform's rotation. Fix it by moving the boundary: Platform keeps ownership of the rendering *engine* and the *contract* it exposes; the two feature teams get ownership of their own template *content* through a self-service path that doesn't route through Platform's PR queue or deploy cycle at all.

Concretely: externalize templates out of the notifications service's deployable into a schema-validated, versioned artifact (a template registry, or config in each feature team's own repo). Platform defines a constrained template DSL/schema — what fields can be bound, what conditionals are allowed, what's injected server-side and non-overridable (unsubscribe links, compliance footers, rate-limit tokens). Feature teams publish changes to that schema through CI validation (lint + snapshot/render tests) and an async publish step, with no Platform review required for anything expressible in the schema. Platform review only re-enters the loop when a team needs a capability the schema doesn't yet support — which should be rare if the schema is sized correctly.

## Evidence (from the request as given)

- Ownership is currently single-threaded through Platform for a class of changes ("how notification templates render") that two other teams are the actual domain experts on — they know their own copy, layout, and conditional logic; Platform doesn't.
- The stated cost is coupled to *review + deploy of the shared service*, not to the content of the changes themselves. That's the signal that the wrong artifact is being gated: template content is being shipped through a pipeline sized for service code.
- The ask is explicitly to reduce the bottleneck *without* growing Platform — so the fix has to remove work from Platform's queue structurally, not make Platform faster at the same work.

Governing lens: **sociotechnical alignment**. The review queue bottleneck is a team-boundary problem — the team that must approve a change (Platform) has no unique knowledge relevant to most of the changes it's approving (per-feature copy/rendering tweaks), while the teams who do have that knowledge can't act without going through it. That mismatch is what generates the back-and-forth.

Challenge lens: **information hiding / ownership**. Before handing template content to feature teams, name what Platform must keep authoritative regardless of who edits templates: delivery guarantees, rate limiting, compliance-required elements, and anything that could be abused as an injection point into rendered output if teams get unconstrained control. That's why the fix is a *schema-constrained* self-service path, not repo access or a lighter-touch review — a naive "give teams write access with lighter review" alternative still routes every change through Platform's deploy cycle and expands the service's blast radius to code neither team fully owns.

## Tradeoffs

- **Alternative — CODEOWNERS-lite / faster review:** doesn't remove Platform from the loop, doesn't reduce deploy coupling; scales linearly with team count. Rejected — doesn't solve "without growing the team."
- **Alternative — each team runs its own notification renderer:** removes the bottleneck by duplicating the engine, but loses the cross-cutting guarantees (delivery, dedup, unsubscribe, compliance) Platform exists to centralize, and is expensive to reverse. Rejected — trades a review bottleneck for fragmentation.
- **Chosen — schema-validated self-service templates:** feature teams lose some expressiveness (constrained to what the DSL covers); Platform loses some visibility into exact wording per change but gains queue capacity. Main failure mode: if the schema is under-scoped, teams hit its edges constantly and escalation requests just reconstitute the bottleneck one layer up.

**OPEN DESIGN DECISION:** how expressive the template schema needs to be isn't answerable from the request alone. Resolve it by auditing a sample of recent Platform-approved template PRs from these two teams (last ~20–30) and classifying what actually changed — copy only, new data bindings, new conditionals, structural layout — before finalizing the DSL. If most changes are copy/data-binding, a narrow schema will absorb nearly all future requests; if teams frequently need new conditional logic, the schema needs to be generous there or this migration under-delivers.

## Next step

Smallest reversible action: pick one of the two teams, extract their current templates into the proposed schema/config format, and route their next few changes through CI-gated self-service publish instead of a Platform PR — while the deploy artifact and rendering engine stay untouched. Validate over a few weeks by comparing change lead time and incident rate against the PR-gated baseline for the other team. Reversal condition: if teams are routinely blocked by schema gaps or an incident traces back to a template bypassing a Platform-owned guardrail, revert that team to the PR-gated flow and iterate on the schema before re-attempting the pilot.
