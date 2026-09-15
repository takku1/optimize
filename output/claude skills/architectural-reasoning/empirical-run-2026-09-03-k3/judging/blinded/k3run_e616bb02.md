**Recommendation**

Model impersonation as a distinct, first-class grant — not a flag bolted onto existing session issuance. Concretely: a separate `ImpersonationGrant` object with its own contract (issuer, target, scope, TTL, justification, approver), a token type that downstream services can distinguish from a real user session at every check, and an audit trail that is the system of record for what happened — not a byproduct of logs. The single highest-leverage design decision is: **never let an impersonated session be indistinguishable from a real one anywhere it matters.** Almost every real-world impersonation incident traces back to that conflation, not to the initial authorization check.

**Evidence**

Working from the general shape of this feature (no existing endpoint code was provided to inspect, so this reasons from the standard trust-boundary structure of admin-impersonation systems and known failure patterns in that class, not from your repo):

The attack surface breaks into boundaries, roughly in order of consequence:

1. **Authorization boundary — who can invoke it.** This endpoint is a universal account-takeover primitive by design: whoever can call it successfully can act as *any* user. That makes the support-staff credential itself the highest-value target in your whole system. A compromised support account with this endpoint is worse than a compromised admin account in most systems, because it's built to look legitimate downstream.

2. **Confused-deputy / attribution boundary — can downstream systems tell impersonated actions from real ones.** If the impersonated session just becomes "logged in as user X" with no marker, every log, every "who did this" query, every fraud/abuse heuristic, and every support ticket from that point forward is silently wrong. This is the boundary most implementations get wrong, and it's the one an attacker (or a careless support agent) benefits from most.

3. **Scope boundary — what the impersonated session can do.** "Debugging" usually only needs read access plus maybe reproducing a specific bug. A general impersonation grant that inherits full write/delete/payment/settings-change capability turns a support tool into a way to quietly modify or drain any account.

4. **Lifecycle boundary — start, TTL, and revocation.** Does the grant expire on its own? Can it be killed mid-session if abuse is detected? Is there a ceiling on concurrent or per-day grants per support agent (rate limiting the blast radius of one compromised or rogue agent)?

5. **Target-tier boundary — who can be impersonated.** Impersonating a normal user is one risk tier; impersonating another support agent, an org admin, or a finance/billing-role account is a materially higher one and arguably needs a different (approval-gated) path rather than the same endpoint with no distinction.

6. **Observability / non-repudiation boundary.** Audit logging here isn't "nice to have" telemetry, it's the primary control that makes this feature acceptable at all — because prevention alone (authz checks) doesn't stop a legitimate-but-malicious support agent. The audit record needs to be tamper-evident, shipped somewhere the support org can't quietly edit, and it needs to capture *why* (ticket/justification reference), not just who/when.

7. **Target awareness boundary.** Does the impersonated user find out, ever? Silent impersonation with no user-visible trace is the version most likely to be abused for surveillance rather than debugging, and the version that looks worst in an incident postmortem.

8. **Session-fixation / token-leak boundary.** If impersonation works by minting a real user session token and handing it to the support UI, that token is now a bearer credential for the victim account sitting in a support tool's browser/logs/network — same value as if it leaked from the user's own client.

**Tradeoffs**

- A dedicated impersonation token type (distinguishable everywhere) costs more upfront engineering than reusing the existing session/auth path, but reusing existing sessions is exactly what produces failure mode #2 (indistinguishable actions) — this is the tradeoff worth paying for.
- Read-only-by-default scope reduces usefulness for some debugging (can't reproduce a bug that requires a write) but shrinks the blast radius by an order of magnitude; write access should be a separate, harder-to-get elevation, not the default.
- Real-time user notification increases transparency and trust but adds product surface, can alarm users mid-incident, and — if the notification path itself is compromised alongside the attacker's access — tips them off; an always-visible account-activity record (even if not push-notified) is a lower-friction middle ground.
- Approval/ticket-linkage for higher-tier targets slows support response time; ungated impersonation of any account is faster but means one compromised or malicious agent can reach your most sensitive accounts with no second signal.
- Short TTLs plus per-agent rate limits reduce the value of a stolen support credential but add re-request friction for legitimately long debugging sessions.

**Next step**

Concrete shape to implement:

1. Separate grant/token type for impersonation, checked explicitly wherever authz happens — not inherited implicitly from "is this a valid session."
2. Default scope = read-only; any write capability is a distinct, explicitly-requested elevation, logged separately.
3. Mandatory justification field (ticket/case ID) at grant time; grant is rejected without one.
4. Short TTL (minutes-to-low-hours, not day-long), auto-expiry, and an explicit revoke/kill path usable by security or the target user's org admin.
5. Tiered targets: normal users go through the standard flow; staff/admin/finance-role targets require a second approver or route through a break-glass process instead of the same endpoint.
6. Tamper-evident audit log (who, whom, when, scope, justification, actions taken) shipped to a system support staff can't edit, feeding your existing detection/SIEM pipeline if you have one.
7. Every downstream write made under impersonation carries an "acted by staff X on behalf of user Y" marker in its own record — not just in the auth log — so it survives independent of the audit trail.
8. Per-agent rate limits / anomaly alerting on impersonation volume (e.g., one agent impersonating an unusual number of accounts in a short window).

**OPEN DESIGN DECISION** — user notification model: real-time in-product notice vs. passive account-activity record vs. none. Resolve with input from support/trust-and-safety on false-alarm rate and from legal/privacy on disclosure obligations in your jurisdictions.

**OPEN DESIGN DECISION** — whether write access under impersonation is ever allowed, and if so what's excluded (payment methods, security settings, email/password changes should likely be hard-blocked even under an elevated grant). Resolve by enumerating what debugging tickets have actually required historically; don't grant write scope speculatively.
