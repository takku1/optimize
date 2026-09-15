## Rating: Grammar-checking browser extension (SaaS)

**60/100 — Grade C — Stage 7: Production-ready**
Confidence: Medium (self-reported/described metrics — subscriber count, ratings, churn, blog citations — taken as stated per default mode; nothing independently fetched or verified, since this wasn't run in `deep` mode)

| Dimension | Score | Weight | Why |
|---|---|---|---|
| Clarity & Definition | 6/10 | 10% | The product itself (browser extension, grammar checking, $8/mo) is stated plainly, but there's no detail on what it actually checks/does beyond the category label — two people would build a similar *category* of product, not the same one. |
| Problem/Value Validity | 7/10 | 15% | 2,400 people are paying monthly and 340 reviews average 4.6/5 — that's real willingness-to-pay evidence, not an assumed need. Capped below "strong" because none of it is independently verified here. |
| Differentiation | 1/10 | 10% | Nothing in the claims addresses why a user picks this over Grammarly, LanguageTool, or native browser/OS grammar tools. Not even asserted, let alone shown. |
| Feasibility | 9/10 | 15% | Moot as a forward-looking question — it's been live and generating revenue for 14 months. Feasibility is already demonstrated, not projected. |
| Execution/Completion | 8/10 | 20% | Weekly releases for six months with no major incident, CI, 82% test coverage, and a paying user base all point to a real, functioning, actively maintained product. |
| Evidence & Validation | 7/10 | 15% | Paying subscribers, a large review sample, tracked churn, and three independent blog mentions are all concrete validation signals — this is the strongest-evidenced dimension. Held at "solid" rather than "strong" because everything is self-reported and none of it was independently checked (no links fetched). |
| Risk Exposure | 1/10 | 10% | No risks are named anywhere in the claims — not data privacy (a grammar checker reads user text), not Chrome Web Store platform dependency, not competitive response from incumbents. Absent, not mitigated. |
| Impact/Upside | 3/10 | 5% | At ~2,400 subscribers × $8/mo (~$230K ARR) in a category with entrenched, well-funded competitors (Grammarly and others), the ceiling here reads as a solid niche business, not a category-defining outcome. |

**Domain modules:**
- *Software build* — TRL: 9 (actual system, proven through 14 months of real operation). Joel Test: only ~2/12 confirmable (source control and automated build/test implied by CI; the other 10 — bug database, written spec, testers, etc. — unknown). Code-health proxies: tests ✓ (82% coverage), CI ✓, docs unrated (not described), tech-debt smell unrated (no code was inspected — this is a described target, not an opened repo). DORA: deployment frequency ≈ weekly (High-performer band); change failure rate, lead time, and MTTR not reported.
- *Product/business* — RICE/ICE: not applicable — no specific feature or initiative was presented to score. Business Model Canvas: ~2/9 blocks filled with real substance (Revenue Streams is concrete; Value Proposition and Channels are only partially specified; Customer Segments, Relationships, Key Resources/Activities/Partnerships, and Cost Structure are all unstated). PMF signal (Sean Ellis): no formal "very disappointed" survey data exists; proxy signals (4.6/5 across 340 reviews, 4% monthly churn, 3 unsolicited third-party mentions) point toward positive but unmeasured PMF. Unit economics: LTV ≈ $200, derived from the supplied numbers ($8/mo ÷ 4% monthly churn ≈ 25-month average lifetime, gross-revenue basis, not cost-adjusted) — this is a calculation from your figures, not a supplied number. CAC was not given, so LTV:CAC is not computable.

**Top strengths:**
1. Real, converted demand — 2,400 paying subscribers plus a 4.6/5 average across 340 reviews is evidence of people paying and staying, not just expressing interest.
2. Proven operational stability — 14 months live, six months of weekly releases with no major incident, CI in place, 82% test coverage.
3. Unsolicited third-party validation — three independent productivity blogs citing it as a recommended tool, without an affiliate/partnership relationship, is a real (if unverified-by-us) external signal.

**Top gaps (ranked by leverage):**
1. Differentiation — nothing explains why this wins against Grammarly, LanguageTool, or free/native alternatives; at this price point in a saturated category, this is the single biggest threat to durability and the lowest score on the sheet.
2. Risk exposure — no stated handling of data privacy (this product reads user text by design), no mention of Chrome Web Store platform/policy dependency, no competitive-response plan.
3. Business model depth — most of the Business Model Canvas (channels, cost structure, partnerships, customer relationships) is unfilled, and there's no CAC, so per-customer profitability is unknown even though LTV is roughly estimable from what was given.

**Next actions:**
1. Write down one specific, defensible differentiation claim (a feature, a niche audience, a privacy stance, a price/positioning angle) and check it directly against the top 1-2 competitors — this is what the Differentiation score is missing.
2. Name the concrete risks — text-privacy handling, Chrome Web Store dependency, competitive substitution — and state what, if anything, mitigates each.
3. Start tracking CAC (ad spend, organic/referral split by channel) so LTV:CAC becomes computable instead of half-known.
4. Run an actual Sean Ellis PMF survey ("how would you feel if you could no longer use this?") to convert the current proxy signals (rating, churn, unsolicited citations) into a real PMF percentage.

**Not assessed:** No code or repository was inspected (this was rated from a pasted description, not an opened project) — Joel Test, tech-debt smell, and documentation quality are therefore unrated rather than scored low. The three blog citations were not fetched or read (default mode, not `deep`), so their content and independence are taken on the claim as given, not verified. Cost structure, CAC, channels, and the actual feature set relative to competitors were not described and so are not scored.
