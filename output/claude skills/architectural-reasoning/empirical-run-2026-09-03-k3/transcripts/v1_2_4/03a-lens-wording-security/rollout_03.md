Governing force here is security by construction: this endpoint creates a new authority — the power to act as any user — so the design question is really "what is the smallest, most mediated, most reversible version of that authority we can grant." The useful challenge to that lens is fault containment: assume the feature works exactly as designed and someone still misuses or hijacks it — what's the blast radius when that happens?

I don't have your actual auth/session code in front of me, so the below is the threat model and the controls it implies, not a code-level review. Treat items that depend on how your session/authz layer actually works as things to verify against the real implementation before you ship.

## Attack surface

**Who can reach the endpoint**
- Any support account that's compromised (phished, reused password, stolen laptop) now inherits "become any user" unless impersonation is its own scoped permission, not a side effect of a generic "is_admin"/"is_support" flag.
- "Internal" is not a trust boundary. If this is reachable from an internal network or admin panel, that network/panel is now as sensitive as your identity provider. IP allowlisting alone is not authentication.

**The impersonated session itself**
- If impersonation just mints a normal user session token, that token is indistinguishable from a real login downstream — every system that trusts "valid session = this user acted" is now wrong. It needs to be a distinguishable, restricted artifact, not a real login.
- Privilege laundering: if the support role can impersonate a user who has permissions the support role itself doesn't have (e.g., a billing admin, another internal employee, an org owner), impersonation becomes a privilege escalation path, not a debugging tool.
- Credential/security-settings mutation while impersonating: changing the target's password, MFA, email, or payment methods from inside an impersonated session is a takeover primitive and needs to be blocked or separately gated, not just logged.
- Session lifetime: impersonation sessions that don't expire quickly, or that survive after the support ticket is closed, extend the blast radius indefinitely.

**Targets**
- No restriction on *who* can be impersonated turns this into a master key. High-privilege accounts (other admins, staff, org owners) and regulated data domains (health, financial, anything under a data-residency constraint) need tighter rules or should be excluded from self-service impersonation entirely.

**Observability gap**
- If actions taken while impersonating are logged only as "user X did Y," the audit trail lies — there's no way to later prove which actions were the user vs. support. This is the single most common way these features get investigated and found wanting after an incident.
- No real-time signal to the target user (or to security) that impersonation happened means the only detection mechanism is a log nobody's watching.

**The endpoint as a new component**
- It's a new privileged code path with its own bugs: IDOR (support agent supplies arbitrary user ID with insufficient checks), missing rate limiting (one compromised agent enumerates/impersonates many users quickly), and it's an attractive target precisely because it's a shortcut past normal auth.

## Keeping the threat model tight

**Authority** — Impersonation is its own capability, granted narrowly (per-role, ideally per-request-justified), not implied by generic admin/support status. State explicitly what it does *not* grant: no credential changes, no security-setting changes, no payment actions, no impersonating a target whose privilege exceeds the impersonator's own — unless a separate, more heavily gated path exists for that.

**Mediation** — Every impersonated action goes through the exact same authorization checks a normal session would hit, tagged with a dual identity (actor=support_agent, subject=target_user) at the point of mediation itself, not bolted on by each downstream consumer. Don't create a bypass lane.

**Contract** — An impersonation session is: explicit (created via a deliberate action, not implicit), reason-logged (ticket/justification required at creation), time-boxed (short TTL, auto-expires), distinguishable (a claim/flag every downstream system can check, not a bare user session token), and revocable (one action kills it — per-session and, for incident response, org-wide).

**Blast radius containment** — Exclude the highest-privilege targets and the highest-risk actions (credential/MFA/payment changes, data export, deletion) from the default flow. If those are genuinely needed for support, they get a narrower, separately approved path — don't widen the common case to cover the rare one.

**End-to-end responsibility for audit** — The audit event (who, whom, when, why, what actions) is owned by the impersonation subsystem at creation and termination, not assembled after the fact from scattered logs. Notifying the target user (even async, "support accessed your account on X for ticket Y") is a cheap trust and detection control worth defaulting to on unless there's a specific reason not to.

**Reversibility** — A kill switch that can terminate all active impersonation sessions immediately, independent of the normal session-expiry path, is cheap insurance for the day the feature itself is the incident.

## Falsifiable checks

Before calling the threat model tight, these should hold and be testable:
- A support account without the impersonation capability cannot invoke the endpoint even if it has other admin flags.
- An impersonated session cannot change the target's password/MFA/email/payment method (attempt it in a test and confirm denial).
- Every impersonated action is attributable to both actor and subject in logs, independently of the application's normal per-user logging.
- Revoking an impersonation session (or the kill switch) ends access within a defined, tested bound (e.g., seconds, not until token expiry).
- Attempting to impersonate a target with higher privilege than the support role is rejected.

## Open design decisions

- Whether target-user notification is synchronous (visible banner/email at time of access) or async (audit-only) — affects trust and support friction differently.
- Whether sensitive actions get a fully separate, more heavily approved impersonation mode versus being simply blocked in the default one.
- Whether step-up auth (re-auth/MFA) is required from the support agent at impersonation start, given this is a high-authority action.

## Next step

Map this against your actual session/authz implementation: confirm how sessions are represented (can they carry an actor/subject distinction cleanly, or does that require a new token shape), where authorization checks currently live (single mediation point or scattered), and where audit logging is currently owned. Those three answers determine whether this is a contained addition or requires a small refactor of the session layer first.
