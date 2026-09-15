## Recommendation

Split the bottleneck's root cause — **content ownership** vs. **delivery/engine ownership** — and give the two consumer teams a self-service path for template changes that never touches Platform's PR queue or deploy pipeline.

Concretely:

1. **Define a stable template contract** Platform owns: a schema of what a template may reference (allowed variables, placeholder syntax, a constrained markup subset — no arbitrary logic/code execution). This is the boundary Platform actually needs to protect.
2. **Move template content out of Platform's deploy unit** into versioned data the rendering engine loads at runtime (config store, template DB, or a separate repo with directory-scoped `CODEOWNERS` per team) — not baked into the service's own codebase/build.
3. **Replace human review with automated validation** for template-only changes: schema conformance, injection/XSS sanitization checks, and a preview-render against fixture data in CI. This is the actual review-queue killer — most of what Platform is reviewing today is presumably "does this fit the schema and render safely," which a linter can do as reliably as a human.
4. **Reserve Platform review for what actually needs it**: changes to the schema/contract itself, or to the rendering engine — rare, high-leverage, and worth a human.

This is the ownership lens: Platform's authoritative responsibility should be the *rendering contract and engine*, not the *content* of every team's notification copy. Right now those are conflated into one deploy unit, which is why every content tweak drags in Platform's review and release cycle.

## Evidence

From the request: the friction is specifically "how templates render for their features" — i.e., content/presentation changes, not engine changes — and each one currently costs a PR review *and* a deploy cycle owned by Platform. That's two separable problems: review latency and deploy coupling. Fixing only one (e.g., faster review) leaves the other in place.

Unverified — worth confirming before committing to the design: whether templates today are already data (e.g., JSON/Handlebars-style files) or are embedded in application code requiring a full build; and whether the "small changes" ever touch logic beyond variable substitution (conditionals, loops) that would strain a pure data/schema approach.

## Tradeoffs

- **Sacrificed:** Platform loses direct visibility into every content change as it happens. Mitigate with CI checks + audit log, not per-change review.
- **Security risk if schema is too loose:** if the contract allows raw HTML or expression evaluation, this reintroduces injection risk into a shared rendering path used by multiple teams' notifications. The schema must be genuinely constrained (sanitized subset, no arbitrary code), which is real design work up front — this is the cost of removing Platform from the loop.
- **Schema too rigid, opposite failure:** if the contract can't express what teams actually need (conditional sections, pluralization, localization), teams will keep hitting the wall and asking Platform for schema extensions — same bottleneck, one level up. The schema needs to be scoped from real current template diffs, not guessed.
- **Alternative rejected:** just widening `CODEOWNERS` so the two teams can merge without Platform review, while leaving deploy as Platform's. This is lower effort but doesn't remove Platform from the deploy cycle, which the request calls out as part of the pain — likely a partial fix at best, worth doing only as an interim step while the data-driven path is built.

## Next step

Pull 10-15 recent template-change PRs and classify each as pure content/copy vs. logic/schema change. That ratio tells you how much of the queue a validated, data-driven self-service path would actually eliminate, and what the schema needs to cover. If the ratio is heavily content-only (likely, given the request describes "small changes to rendering"), the self-service path is worth building; if a meaningful fraction needs new logic, treat schema-extension requests as a distinct, still-Platform-reviewed track separate from routine content changes.

**OPEN DESIGN DECISION:** whether template content should live in Platform's repo (directory-scoped ownership) or in each consuming team's own repo, fetched at runtime. Depends on how tightly template changes are coupled to feature-flag/feature-code changes in those teams' release cycles — resolve this after the PR-classification pass above, once you know whether templates change in lockstep with feature code or independently.
