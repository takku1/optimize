## Rating: "Unified workspace" app (remote team chat/tasks/docs in one place)

**14/100 — Grade F — Stage 1: Concept**
Confidence: High (the evidence base is thin, which itself is clear — little ambiguity to weigh)

| Dimension | Score | Weight | Why |
|---|---|---|---|
| Clarity & Definition | 2/10 | 10% | One sentence of scope ("see all their chat, tasks and docs in one place"). Which tools integrate, read-only vs. actionable, aggregation vs. replacement — all undefined. Two builders would ship different products from this. |
| Problem/Value Validity | 2/10 | 15% | "Context switching wastes time" is asserted, not evidenced — no named customer segment (company size, industry), no interview, no quote. |
| Differentiation | 1/10 | 10% | This is one of the most saturated pitches in SaaS — Slack, MS Teams, Notion, ClickUp, Coda, Front, Unito, and Zapier-style connectors already target exactly this. No stated reason a team would switch or add this. |
| Feasibility | 3/10 | 15% | No team, timeline, or stack given. The pitch itself implies a large integration surface (OAuth + sync + permissions + search across many third-party APIs), which is a genuinely hard, ongoing engineering and platform-dependency problem. |
| Execution/Completion | 0/10 | 20% | Stated directly: "no code yet just the idea." |
| Evidence & Validation | 0/10 | 15% | No users, data, waitlist, or experiment of any kind. |
| Risk Exposure | 1/10 | 10% | Unaddressed: third-party API dependency/revocation risk (Slack, MS, Google routinely restrict integration access), enterprise security/compliance review (this product needs deep access to a company's chat and docs — a hard sell), and incumbent bundling risk. None named. |
| Impact/Upside | 5/10 | 5% | If it worked and won real adoption, the addressable pain is broad (any remote team) — but the ceiling is capped by how much value incumbents already capture in this space. |

**Domain modules:**
- **ICE:** Impact 5, Confidence 3, Ease 3 — low confidence and low ease drag this down; report, don't average away, the fact that two of three inputs are weak.
- **Business Model Canvas:** 2/9 blocks touched (Customer Segments and Value Proposition, both vague); Channels, Customer Relationships, Revenue Streams, Key Resources, Key Activities, Key Partnerships, Cost Structure — none addressed.
- **PMF signal (Sean Ellis):** No data collected — no users to survey yet.
- **Unit economics:** Not claimed — not applicable.

**Top strengths:**
1. The underlying pain point (context switching across tools) is a real, broadly-recognized category of complaint, not a fabricated one.
2. The pitch is at least stated as a clear elevator sentence — easy to react to and iterate on.
3. Target market (remote teams) is large and easy to reach for early conversations.

**Top gaps (ranked by leverage):**
1. **No differentiation** — this is the single biggest risk. "Unify chat/tasks/docs" is already the pitch of several funded companies and every major platform's own roadmap. Without a specific wedge, this doesn't clear the bar to exist.
2. **Zero external validation** — nothing here has been checked against an actual person outside your own head. Right now this is a hypothesis, not a problem confirmed to be real.
3. **Undefined scope** — "all their chat, tasks and docs" is not a buildable spec. It spans wildly different technical problems depending on which tools and what "see" means.

**Next actions:**
1. Talk to 10-15 people who actually work on remote teams (ops leads, eng managers) and ask what they do today and how costly switching actually is — get specifics, not agreement with your framing.
2. Pick one narrow wedge — one pair of tools (e.g., Slack + Linear, or Slack + Notion) and one workflow — instead of "all chat, tasks, docs."
3. List the 5-8 closest existing options (Slack, MS Teams, Notion, Coda, Front, Unito, Zapier) and write down specifically why someone would add or switch to this instead.
4. Fill out a one-page lean canvas or BMC to force real answers on who pays, what channel reaches them, and who owns the buying decision (likely IT/security in a B2B context, not just the end user).

**Not assessed:** Technical architecture and team capability (not stated), competitor landscape and TAM (not researched — default mode, no external search run), and the security/compliance burden of a product with deep access to a company's chat and documents (a real, likely-large risk that hasn't been addressed at all).
