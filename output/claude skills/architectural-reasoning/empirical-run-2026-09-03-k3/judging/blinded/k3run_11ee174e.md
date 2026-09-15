## Recommendation

Treat impersonation as a distinct, first-class trust boundary — not a flag on the existing login flow. The governing force here is misuse: a support agent's own credentials become a skeleton key for every account in the system, so the design has to assume both external credential compromise and internal misuse from day one (security-by-construction). The lens worth pushing back with is fault containment: even a correctly-authorized impersonation session is a live blast-radius problem, so the design also has to bound and cut off damage quickly, not just gate entry to it. Where those two pull against each other — strict gating slows support down, tight containment limits what they can do once in — resolve toward containment, because gating failures are visible at request time while containment failures are the ones that turn into incident write-ups.

Concretely:

- **Separate the impersonation token from a normal session token.** It should carry `impersonator_id`, `subject_id`, `ticket_id`, `issued_at`, and a short, non-renewable TTL (15–30 min), minted by the identity/auth service — never by the support tool itself. The support tool should be a consumer of this token, not its issuer; if the tool can mint its own trust, the tool's compromise is the account's compromise.
- **Make the token structurally incapable of laundering as the real user.** Every downstream event (audit log, analytics, webhook, email trigger) must carry the impersonator's identity, not just the subject's. If a single log line can't tell you "agent X was acting as user Y," you don't have accountability, you have a blind spot.
- **Deny-list the target set, don't rely on the requester's judgment.** Support staff should not be able to target other admins, other support accounts, or the impersonation grantor's own account — that's the direct privilege-escalation path (compromise one support account, impersonate your way up). Enforce this in the token-minting service, not the UI.
- **Scope the action set, not just the read/write boundary.** Even if writes are allowed for debugging, block the specific mutations that convert account access into account takeover: password reset, email change, MFA enrollment/removal, payment method changes, data export, API key creation. These are the moves an attacker actually wants; a "full impersonation" that permits them is functionally an account-takeover primitive with extra steps.
- **Fail closed on the audit write.** Order matters: audit entry persists before the session is usable, not after. If the audit store is unreachable, impersonation should not proceed — an unauditable admin session is worse than a denied support ticket.
- **Notify the target user**, synchronously or async depending on support SLAs, so silent access is never the default. This is as much a deterrent to internal misuse as it is a user-trust feature.
- **Give it a kill switch independent of the requester.** Instant revocation (security team, or automatic on password change / user-reported suspicious activity) must terminate an active impersonation session immediately, not just block future ones.
- **No nested or chained impersonation.** A session already running under `impersonator_id` cannot itself impersonate; otherwise you've built a privilege-escalation relay.
- **Require step-up auth (MFA) and a justification/ticket ID at mint time**, and put the endpoint behind internal network access, not public routing — the entry point itself is part of the attack surface, and a leaked admin-tool URL shouldn't be enough on its own.

## Evidence

No codebase was provided for this request, so the above is derived from the threat model implied by the feature description ("support staff impersonate a user for debugging") rather than from inspecting an existing auth/session implementation. Two things would materially change the recommendation and should be checked against the actual system before implementing:

- **Current session/token architecture** — if sessions are opaque server-side session IDs rather than signed tokens, "carry impersonator_id in the token" becomes "carry it in the session record," but the audit-linkage requirement is unchanged.
- **Existing admin authz model** — if there's already a break-glass or elevated-access pattern (e.g., for on-call engineers), impersonation should reuse its approval/audit machinery rather than growing a second, inconsistent one. Two parallel "trust me, I'm staff" systems is itself a risk.

## Tradeoffs

- **Usefulness vs. blast radius:** a read-only impersonation mode is much safer but may not reproduce every bug support needs to see (e.g., write-path issues). If write access is required, it should be justified per-incident, not granted by default — sacrifice some support velocity for a materially smaller attack surface.
- **Friction vs. speed:** ticket-bound MFA and target-account deny-lists add seconds to every support session. That cost is worth paying because the alternative failure mode (a compromised support account with unrestricted impersonation) is a full account-takeover engine, not a minor inconvenience.
- **Notification timing:** synchronous "you are being impersonated" prompts are the strongest trust signal but can block urgent debugging on a locked-out user; async notification (email after the fact) is more practical but weakens the deterrent slightly. This is a product call, not just a security one.

## Next step

**OPEN DESIGN DECISION:** whether any write actions are permitted during impersonation at all, or whether the endpoint ships read-only for v1 and write access is added later behind its own review. This should be resolved by whoever owns the support tooling's actual debugging needs — start read-only unless there's a concrete, named bug class that requires writes, since that's the smallest attack surface that still satisfies the stated goal.

Before building: confirm the current session/token model and any existing elevated-access pattern (see Evidence above), then validate the design against tests that could disprove it — a support account cannot target an admin account, a token is unusable after its TTL even mid-session, revocation terminates an active session immediately, and no downstream action is recorded under the impersonated user's identity alone.
