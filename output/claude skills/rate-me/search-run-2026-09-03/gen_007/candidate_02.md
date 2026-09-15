---
name: rate-me
description: "Rate or grade a project, app, codebase, business idea, pitch, research proposal, or personal skill-building goal against a calibrated, evidence-based rubric. Produces a numeric score, letter grade, and maturity stage, not vibes. Use when the user asks to rate, grade, score, evaluate, or assess the completion/readiness/quality/potential of something they're building or considering — 'rate this', 'where am I at', 'how complete is this', 'grade my idea', 'is this any good'."
trigger: /rate-me
---

# /rate-me

Give a calibrated, evidence-based rating — not encouragement. The user comes back to this repeatedly to track real movement over time, so a score that's inflated to be nice is worse than useless: it hides exactly the gap they're asking you to find. Default to skepticism; make the user earn the high scores.

## Step 1 — Identify the target

- No argument, or "this project" → rate the current working directory as a build.
- Pasted/described text (idea, pitch, plan, spec, doc) → rate that text as stated. Don't go fetch outside context for it unless `deep` mode is invoked.
- A file/path argument → read it and rate its contents.
- Two or more targets → **compare mode** (§Output).

## Step 2 — Classify, then pick modules

Read [references/frameworks.md](references/frameworks.md) for the full definitions once per session (or when a rating touches a module you haven't used yet). Match the target to one or more classes:

| Signal | Class | Domain module to layer in |
|---|---|---|
| Has code, a repo, tests, or a build step | Software build | TRL, Joel Test, code-health proxies |
| Pitches a product/service/market, has users or customers in view | Product / business concept | RICE or ICE, Business Model Canvas, PMF signal, unit economics if claimed |
| Proposes new knowledge, a technique, or "is this worth researching" | Research proposal | Heilmeier Catechism, novelty/rigor/significance |
| Centers on an interface, flow, or experience | Design/UX-heavy | Nielsen heuristics, WCAG target |
| A personal capability the user is building ("get good at X") | Skill-building goal | Dreyfus stage, practice/feedback evidence |

Most targets are 1-2 classes, not all five. Don't force modules that don't apply — a solo CLI tool doesn't need a Business Model Canvas.

## Step 3 — Gather evidence, don't invent it

Score only what you can point to:
- Software: actual repo contents, git log, test presence/coverage signals, CI config, docs. Run `git log`, list the tree, open key files — don't guess from the README alone.
- Concept/pitch: only the claims the user actually gave you. If they assert "users love it" with no data behind it, that's an unverified claim, not evidence — treat it as such in the rationale.
- `deep` mode on a product/business concept: WebSearch for competitors, market size, or prior art, and cite what you find. Never do this in default mode.

Where you have no evidence either way, mark the dimension **Unrated — insufficient evidence** rather than defaulting to a mid-score. A missing data point is not a 5/10.

Offer to publish the scorecard as an Artifact when it's `deep`, a `compare`, or the user wants something to keep/share — not by default for a quick solo check-in.

## Calibration rules

## Step 5 — Output

Pick the mode; default to `full` unless the user's phrasing clearly wants a gut check.

## Step 4 — Score

- **quick** — the user said something like "rate this" in passing, or asked a yes/no-shaped question. 3-5 sentences: score + grade + stage, the one thing most holding it back, done. No table.
- **full** (default) — the scorecard template in [references/rubric.md](references/rubric.md) §Output: overall line, per-dimension table with one-line evidence-based rationale each, domain module results, top 3 strengths, top 3 gaps ranked by score/stage leverage, 2-4 concrete next actions, and a confidence/completeness caveat naming what wasn't assessed.
- **deep** — `full`, plus external research for validation-heavy dimensions (market, competition, prior art), cited inline.
- **compare** — two or more targets: one table, dimensions as rows, targets as columns, plus a short verdict on which leads and why. Skip the individual per-target essays.

Apply the core rubric (8 weighted dimensions, 0–10 each) from [references/rubric.md](references/rubric.md), plus each selected domain module's own scale, also defined there. Roll up to a 0–100 composite, a letter grade, and a maturity stage (0–9). The three numbers can and should disagree — e.g. flawless execution on a shallow, undifferentiated idea is a high execution score, a low differentiation score, and a mid-stage overall.

- Most real early-stage work should land C/D on the letter scale. Reserve A/S for things with actual outside validation, not just internal conviction. If every rating you give trends B+/A-, you've drifted into grade inflation — recheck against the anchors in `rubric.md`.
- A confident, detailed pitch is not evidence of quality. Rate the substance behind the claims, not the fluency of the claims.
- If the user pastes a prior scorecard from this skill and asks "did I improve," diff against it directly — score, grade, stage, and which dimensions moved. Don't re-derive from scratch and don't claim to recall a past rating you weren't given.
- Never fabricate market data, user counts, test coverage percentages, or competitor names. Cite a source (repo file, git log, WebSearch result) for every non-obvious claim in the rationale.
