# Admin Impersonation Endpoint — Attack Surface and Threat Model

## Recommendation

Treat impersonation as a distinct, first-class credential type with its own authority — not "log in as the target user with an admin's blessing." The single biggest risk in these designs isn't the endpoint itself, it's what happens *after* the token is issued: if downstream services can't distinguish an impersonated session from a real one, you've built a confused-deputy machine that every other service implicitly trusts. Constrain at the moment of issuance, then enforce that constraint at every consumer, not just the front door.

## Attack surface

**Getting to the endpoint**
- Support staff account compromise (phishing, credential stuffing) becomes account-takeover-as-a-service for *any* user, not just the support agent's own account.
- Insider abuse: a legitimate agent impersonating a user outside a legitimate ticket (curiosity, harassment, fraud, data resale).
- Privilege creep: the "support" role quietly gaining impersonation rights through broad RBAC groups, or a bug making a wider role set eligible than intended.

**The impersonation grant itself**
- Target selection with no scoping — any support agent can impersonate any user, including other admins, finance/ops accounts, or high-value targets (executives, users mid-dispute).
- No step-up authentication — a stale SSO session is enough to mint an impersonation token, no re-auth/MFA at time of use.
- Token scope is too broad — if the minted session/token is functionally identical to the real user's normal session token, it inherits *all* of that user's privileges, including things support never needs (payment method changes, credential rotation, data export, deleting the account).
- Chained/nested impersonation — an agent impersonates user A, then uses A's own admin/support rights (if A happens to have any) to escalate further.

**Downstream propagation (the part most designs miss)**
- Services that only check "is this a valid session" and not "is this session impersonated, and what's it scoped to" will happily let an impersonation token do anything the real user could — this is the confused-deputy failure mode. Perimeter enforcement at the admin-tool gateway doesn't help if a call three services deep trusts the same session token at face value.
- Logging/audit systems that record the *impersonated user's* ID as the actor, losing the fact that a support agent was driving — this breaks forensics after an incident.
- Side channels: viewing the target's stored secrets, payment instruments in plaintext, MFA recovery codes, or being able to change the target's credentials while impersonating (which would let an agent lock the real user out or take over the account permanently).

**Operational/visibility gaps**
- No indication to the impersonated user that their account was accessed — undermines detection and user trust, and is often a compliance requirement (GDPR/SOC2/HIPAA depending on domain).
- No time bound — sessions that outlive the support ticket, get bookmarked, or get reused.
- No kill switch — no way for security or the user to immediately terminate an active impersonation session.
- No anomaly detection — one agent impersonating hundreds of accounts, or impersonation clustering right before account fraud, goes unnoticed without monitoring built for this specific pattern.

## Keeping the threat model tight

1. **Distinct credential, not a shared session shape.** Mint a token/session carrying explicit claims: `impersonator_id`, `target_id`, `ticket_ref`, `granted_at`, `expires_at`, `scope: restricted`. Never let it collapse to something indistinguishable from the target's normal session.
2. **Enforce scope end-to-end, not at the gateway.** Every service that honors sessions must check the impersonation claim and apply the reduced scope itself. Deny by default: an impersonated session can't touch payment credential changes, MFA/password reset, data export, or account deletion unless explicitly allowlisted. This is the one design choice most likely to be skipped under time pressure and is where the actual security value lives.
3. **Step-up auth to grant, not just to log in.** Require fresh MFA at the moment of impersonation request, independent of SSO session age.
4. **Mandatory justification tied to a ticket/case ID**, captured before the token is issued, not as an optional log field.
5. **Deny-list the sensitive targets by default.** No impersonating other staff/admins; anything above a defined sensitivity tier (execs, flagged/fraud accounts) requires a second approver.
6. **Short, hard TTL with no silent renewal.** Re-request (with re-justification) rather than extend.
7. **Tamper-evident audit trail, separate from normal app logs**, recording agent identity, target, scope, actions taken, and duration — attributed to the *agent*, not blended into the target's activity log.
8. **User-visible signal** — at minimum a record the user can see later ("Support accessed your account on X for ticket Y"); ideally a live banner during an active session, if product/compliance requires it.
9. **Kill switch** — security team and, ideally, the user can terminate an active impersonation session immediately, independent of TTL.
10. **Anomaly alerting** on volume per agent, off-hours use, and repeated impersonation of the same target.

## Tradeoffs

Real-time scope enforcement at every downstream service is meaningfully more engineering work than a single gateway check, and it's the part most likely to be cut. That cut is exactly what turns "internal debugging tool" into "account takeover as a service" the moment any one downstream service is careless about session validation. If full end-to-end enforcement can't ship in v1, the fallback is a much smaller allowlist of what impersonation is permitted to touch at all (read-only, no writes) until enforcement catches up — not a broad token issued on trust.

## Failure modes to watch for

- A downstream service added later doesn't know about the impersonation claim and treats the token as a normal session (silent privilege escalation).
- Audit log and app log disagree on who performed an action (attribution loss, breaks incident response).
- TTL extension becomes a de facto standing grant because renewal has no friction.

## Validation before shipping

- Write a test that asserts every write-capable endpoint explicitly checks the impersonation scope claim (not just an integration test of the happy path) — this catches the confused-deputy gap directly.
- Attempt impersonation of an admin account and of a user outside the agent's ticket; both should fail closed.
- Confirm audit records survive a direct write to the impersonated user's own activity log (i.e., they're in a separate, staff-attributed store).

**OPEN DESIGN DECISION:** whether the impersonated user gets a real-time visible banner versus after-the-fact notification — resolve with whoever owns compliance/privacy requirements for this product, since it changes both UX and legal posture.
