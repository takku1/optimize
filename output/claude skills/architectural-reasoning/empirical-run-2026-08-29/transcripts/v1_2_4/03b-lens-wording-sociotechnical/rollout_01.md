## Recommendation

Reframe the boundary. Right now "notification template change" and "notification service deploy" are fused — any change to what gets rendered requires Platform to review code and cut a release. The fix isn't more reviewers, it's separating **content ownership** from **delivery-mechanics ownership**, so most requests never cross a team boundary at all.

Give the two feature teams a **self-service template contract**: templates become versioned, declarative artifacts (a constrained schema/expression language — think a locked-down Handlebars/Liquid subset with typed data bindings, not arbitrary code) that feature teams own and can publish independently of the notifications service's binary. Platform owns and gates only:

- the rendering engine and its safety invariants (escaping, injection/XSS prevention, sandboxing of the expression language)
- the schema itself (what fields/logic a template is allowed to use)
- delivery mechanics — sending, throttling, dedup, compliance/PII redaction, observability

Feature teams own template content and copy within that schema, validated by CI (schema conformance, lint, preview render) instead of a human PR review from Platform. Template publication becomes a config push, not a service deploy.

## Evidence (from the situation as described)

- The recurring friction is specifically about "how templates render for their features" — i.e., content/presentation logic, not delivery semantics (sending, retries, rate limits). That's a strong signal the coupling is artificial, not essential.
- "Small changes" + "PR review plus a deploy cycle" is the classic symptom of a missing contract: when there's no stable interface, every change looks like a code change and has to go through the code's owner.
- Platform naming the review queue as the bottleneck (not the correctness of the changes) suggests the changes themselves are usually low-risk — a good candidate to move from human gating to automated validation.

## Challenge / tension to resolve

The counter-force here is fault containment and security: a templating layer that's too expressive becomes an injection or logic-bug surface Platform can no longer reason about, and "self-service" can quietly turn into "unreviewed arbitrary code in a shared service." That's why the contract should be a constrained declarative schema, not a plugin system with real code execution — keep the escape hatch narrow (formatting, conditionals, data binding) and route anything needing real logic back through Platform as an explicit schema extension request, not a one-off PR.

There's also a sociotechnical read worth naming: this is Conway's Law working against you — two teams keep needing changes to a system a third team owns because the architecture doesn't match the team boundary. Moving the content boundary to match team ownership is the structural fix; adding process (faster review SLAs, a rotating reviewer) only papers over it.

## Tradeoffs

- Upfront cost to build the schema, validation/CI pipeline, and safe rendering sandbox — this isn't free, but it's a one-time investment against a recurring tax.
- Some loss of centralized consistency/quality control over notification content; mitigate with lightweight automated checks (brand/format linting) rather than human review.
- Schema will initially be too narrow for some requests — expect an escape valve (fallback to the old PR path) for anything not expressible; track how often it's used as the signal for where the schema needs to grow.

**OPEN DESIGN DECISION:** whether template artifacts live in each feature team's own repo/deploy pipeline (fully independent publish) or in a centralized template registry that Platform still hosts but exposes a self-service write API for (async-validated, no PR gate). Pick the registry model if rollback safety, audit trail, and cross-team visibility into what's live matter most; pick the decentralized model if deploy independence is the dominant pain point. Resolve this by asking Platform how often they've needed to force-rollback a bad template today — frequent rollbacks argue for the registry.

## Next step

Pilot with one team's lowest-risk, highest-frequency change type (e.g., copy/text edits with no new data bindings). Build just enough schema + validation to cover that case, cut Platform out of the loop for it, and measure: review-queue volume drop, time-to-ship for template changes, and any validation escapes (bugs that would've been caught by human review). Use that data to decide how far to extend the schema before onboarding the second team.
