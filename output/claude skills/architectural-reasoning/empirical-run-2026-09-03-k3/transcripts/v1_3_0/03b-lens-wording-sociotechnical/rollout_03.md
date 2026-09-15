# Recommendation

Move the boundary from *code review + shared deploy* to a **stable, self-service template contract**. Platform should own and version a schema for what's substitutable in a notification template (variables, conditional blocks, named slots/partials) plus the rendering engine and its validation. The two feature teams should own their own template content *inside* that contract — stored and deployed through their own repos/CI, not Platform's — so a copy change or a new variable no longer requires a Platform PR or a Platform-owned deploy.

This is a sociotechnical alignment problem, not a rendering-engine problem: the actual friction is that team ownership boundaries don't match the deployable unit. Every team's "small change" currently has to cross an ownership boundary it doesn't need to cross, because content and engine are coupled in one repo/release. Splitting the *contract* (owned by Platform, changed rarely, reviewed carefully) from the *content* (owned by each feature team, changed often, self-served) removes Platform from the critical path for the class of changes that's generating the queue, without adding headcount.

# Evidence

From what's described:
- The friction is specifically about *how templates render for other teams' features* — i.e., content/parameters, not core rendering behavior. That's a strong signal these are contract-level changes (data), not engine-level changes (logic Platform must own).
- The coupling mechanism causing the bottleneck is explicit: every change requires a Platform-owned PR review *and* a Platform-owned deploy cycle. Two teams both routing through the same review+deploy chokepoint for low-risk changes is what's producing "a lot of cross-team back-and-forth" and a growing queue — this is an incentive/ownership mismatch, not a capacity shortfall, which is why adding headcount is the wrong lever.
- No indication (in what's given) that the two teams' template needs interact with each other or with shared mutable state — worth confirming before designing, since if they *do* share the same template instances, the fix also needs namespacing per team, not just a schema.

# Tradeoffs

Sacrificed by moving to a contract boundary:
- **Uniformity of review.** Platform loses visibility into each individual content/copy change. Mitigate by keeping CI validation against the schema (required fields, allowed HTML/markup, length limits, banned patterns) so bad input fails fast without a human gate.
- **Flexibility for truly novel needs.** If a team needs something the schema doesn't express (new layout primitive, new logic type), that still requires a Platform-reviewed contract change — same cost as today, but only for the tail of requests, not the median one.
- **Engine complexity.** Platform now maintains a schema/versioning surface instead of ad hoc code, which is real ongoing cost — but it's Platform-scoped work they control, not queue-scoped work gated by two other teams' release timing.

Failure mode to design against: schema drift or teams working around it (e.g., stuffing logic into a "just a string" field) causing runtime breaks Platform gets paged for. Guard with strict server-side validation and a sandboxed template language (no arbitrary code execution) rather than trusting client-side discipline.

# Next step

1. Pull the last ~10–20 cross-team template PRs and bucket them: copy/variable changes vs. structural/logic changes vs. true engine changes. This tells you whether a schema can cover the majority (validates the whole approach) or whether the "small changes" are more varied than assumed.
2. Design the v1 contract (variables + conditional blocks + named slots) to cover the dominant bucket only — don't try to cover every historical request on day one.
3. Pilot with one team: move their template content into their own repo/CI against the schema, with CI-enforced validation replacing Platform PR review for in-contract changes.
4. Define explicit criteria for "needs Platform review" (schema/contract changes, new template capabilities) vs. "self-service" (anything expressible in the existing schema), so the escape hatch doesn't quietly become the default path again.

**OPEN DESIGN DECISION:** whether template content needs conditional/programmatic logic (not just variable substitution). If yes, the schema needs a genuinely sandboxed templating language with no side effects — resolve this from the PR bucket analysis in step 1 before committing to schema shape.
