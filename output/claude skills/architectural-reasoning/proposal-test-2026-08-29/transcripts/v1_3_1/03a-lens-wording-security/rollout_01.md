# Admin Impersonation Endpoint: Attack Surface and Threat Model

## Recommendation

Build impersonation as a **mediated, capability-scoped, fully-audited flow** — never as a
mechanism that hands a support agent the target user's real credentials or an
indistinguishable copy of their session. The admin endpoint should mint a distinct
**"on-behalf-of" (OBO) token** that carries two identities (actor = support staff, subject =
impersonated user), is scoped to the minimum action set debugging requires, expires quickly,
and is unforgeable evidence of who did what. Treat this as a new trust boundary, not an
extension of the existing session system.

No repository was inspected for this request (none was in scope), so the analysis below
reasons from the feature description itself. Before implementation, the actual owner of
session/auth state, the existing token format, and the audit-logging path must be identified
in the real codebase — the design below assumes none of that exists yet and states where
that assumption would change the recommendation.

## Attack surface

| Surface | Risk if unmitigated |
|---|---|
| **Who can invoke impersonation** | Any authenticated staff account with the endpoint reachable becomes a full account-takeover primitive for every user. |
| **How impersonation is authorized** | If authorization is just "has the `support` role," a single compromised or malicious support credential compromises the entire user base. |
| **What the impersonated session can do** | If the OBO session is indistinguishable from the real user's session, it can change email/password, read payment data, or take irreversible actions — turning a debugging tool into a full account-takeover tool. |
| **Session lifetime and scope** | A long-lived or unscoped impersonation token left active after the debugging task ends is a standing backdoor. |
| **Auditability** | If impersonated actions are logged only as the target user (or not distinguished at all), there's no way to attribute harm, detect abuse, or satisfy compliance/legal holds. |
| **User awareness/consent** | Silent impersonation with no user-visible signal removes the last line of detection (the user noticing something happened on their account). |
| **The endpoint itself** | It is now the single highest-value target in the system — CSRF, IDOR (impersonate arbitrary user ID), and privilege-escalation bugs here are worse than almost anywhere else in the app. |
| **Downstream trust** | Any service that trusts "authenticated session ⇒ this is really the user" (payments, notifications, external APIs) inherits the impersonation risk unless it can see the actor/subject distinction. |
| **Support tooling as an attack path** | The support team's own accounts, workstations, and the internal admin UI become attacker targets, since compromising *one* support account now yields impersonation of *any* user. |

## Threat model — what "tight" means here

Governing force: **security by construction** — the design must make misuse structurally
hard, not merely policy-forbidden. The challenge to weigh against it is **end-to-end
responsibility**: every layer that consumes the impersonated session (payments, downstream
services, audit consumers) must itself honor the actor/subject distinction, or the
containment is only as strong as the weakest consumer.

Concretely:

- **Distinct identity, not credential reuse.** The OBO token must encode `actor_id`
  (support staff) and `subject_id` (target user) separately. Never generate a token that is
  bit-for-bit what the real user would have.
- **Least privilege by default, escalate explicitly.** Default impersonation to read-only.
  Any write/mutating action requires either an explicit additional grant or a second
  approval step (ticket reference, second-admin sign-off, or step-up auth) — this is an
  **OPEN DESIGN DECISION**: whether write access is needed at all for the debugging use case,
  or whether read-only plus log/replay tooling covers it. Resolve by asking support what
  they actually need to diagnose, not what's convenient to build.
- **Time-boxed and reason-bound.** Token TTL measured in minutes, requires a
  free-text or ticket-linked reason at mint time, and is bound to a specific target user ID
  (no wildcard/self-service target selection beyond what the ticket names).
- **Tamper-evident, append-only audit trail.** Every action taken under an OBO token logs
  both `actor_id` and `subject_id`, is written to a store the support team itself cannot
  edit or delete, and is queryable per-user (so a user or investigator can answer "was I ever
  impersonated, by whom, when, and what changed").
- **User-visible signal.** At minimum, notify the user (email or in-account banner) that a
  support impersonation session occurred, after the fact if not in real time. This is the
  cheapest, highest-leverage abuse deterrent and detection mechanism available. Mark as
  **OPEN DESIGN DECISION** if product/legal wants real-time consent instead of after-the-fact
  notice — that changes the UX materially.
- **Break-glass, not standing access.** The endpoint should require the target user ID and a
  reason on every invocation; there should be no long-lived "impersonation mode" toggle.
- **Isolate the endpoint's own authz.** Gate it behind its own permission (not a broad
  `is_staff` flag), and treat IDOR on the target-user parameter as a critical-severity class
  of bug, since it's the difference between "debug one ticket" and "impersonate anyone."

## Tradeoffs

- **Full-fidelity impersonation session** (looks identical to the user's real session) is
  the highest-fidelity debugging tool but the worst threat model — sacrifices
  containment and auditability for developer convenience. Rejected as the default.
- **Read-only "view as" mode** (render the user's UI state without a mutable session) is the
  smallest attack surface and covers most debugging needs, at the cost of not reproducing
  bugs that only manifest on write paths. Recommended as the default tier.
- **Full OBO token with scoped write grants** covers the remaining cases but requires the
  extra machinery (approval step, tighter TTL, stronger audit) above. Recommended as an
  explicit escalation path, not the default.
- **Status quo (no impersonation tool)** avoids all of this risk but pushes debugging cost
  onto asking users to reproduce issues themselves or granting staff direct DB access — likely
  a worse threat model than a well-built OBO flow, since direct DB access is even less
  auditable.

## Next step

Smallest reversible action: ship the **read-only "view as"** tier first, gated on its own
permission, with mandatory reason capture and full actor/subject audit logging — no write
capability yet. Validate with: (1) an authz test confirming the endpoint rejects any staff
account lacking the specific impersonation permission, (2) an IDOR test confirming the
target-user parameter can't be manipulated to escalate scope, and (3) an audit-log query
proving every read action under impersonation is attributable to both actor and subject.
Only after that is live and reviewed should write-scoped escalation be designed, since it is
the highest-risk increment and should not ship in the same change as the initial mediation
layer.
