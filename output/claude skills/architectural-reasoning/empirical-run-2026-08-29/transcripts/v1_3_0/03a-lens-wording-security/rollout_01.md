## Recommendation

Treat impersonation as a **distinct, first-class identity state** — not a swapped `user_id` in an existing session — with its own owner, short-lived scoped token, mandatory justification, and an audit trail the admin cannot alter. The governing force here is security by construction (this endpoint is a built-in privilege-escalation primitive) challenged by end-to-end responsibility (every downstream system that consumes "who is this request from" must be able to tell the difference between the user acting and the admin acting-as).

## Attack surface

**1. The grant path (who can start impersonation)**
- Gate on a dedicated `impersonate_users` permission, not a generic `is_admin` flag — role bloat means "admin" often includes people who shouldn't have this.
- Deny-list impersonation of privileged accounts (other admins, service accounts) to block lateral escalation — an admin impersonating an admin is a privilege-escalation chain, not a support action.
- Require step-up auth (recent MFA, not just an existing session) to start impersonation — the endpoint should not be reachable on session hijack alone.
- Require a reason/ticket ID as an argument, not a UI-only convention — make it structurally impossible to start impersonation without a linkable justification.

**2. The impersonation artifact itself**
- Mint a separate, signed, short-TTL token (15–30 min) carrying both `acting_admin_id` and `target_user_id` as distinct claims — never overwrite the session's identity in place. Downstream services must be able to see both identities, not infer impersonation from a side channel.
- Bind the token to the admin's own session/device so it can't be exfiltrated and replayed independently of the admin being authenticated.
- No silent renewal — expiry means re-request, which re-triggers the audit and justification step.

**3. What's allowed while impersonating**
- Block security-critical mutations on the target account during impersonation: password/email/MFA changes, payment method changes, account deletion, granting the target new permissions. These are the actions an attacker most wants from a stolen admin credential; carve them out regardless of debugging convenience.
- Everything else should be logged at the action level, not just at session start/end — "admin X impersonated user Y" is not enough; you need "admin X, impersonating Y, did Z at time T."

**4. Audit integrity**
- Write impersonation start/end/action logs to a sink the admin's own role cannot delete or edit — an internal app table is not sufficient if the compromised credential is an admin's, because that credential can also touch the log. Externalize to a SIEM or append-only store.
- Alert on anomalous patterns: impersonating the same user repeatedly, bulk impersonation across many accounts, impersonation of VIP/executive accounts, off-hours use.

**5. User-facing signal**
- Visible impersonation banner in the UI for the duration — reduces admin error (acting on the wrong identity accidentally), not just malice.
- **OPEN DESIGN DECISION:** whether the target user is notified (real-time or after-the-fact) that support accessed their account. This is a product/trust tradeoff, not a pure security call — flag it for the product owner; the security posture is stronger with notification, but it adds support friction and may need an exemption path for fraud investigations.

## Tradeoffs

The heavier design (separate token, external audit sink, step-up auth, action-level blocking of sensitive mutations) costs more to build than the shortcut of swapping `user_id` in the existing session and logging a single "impersonation started" event. The shortcut is rejected here: it produces a system where a compromised admin credential is functionally equivalent to *any* user's credential with no distinguishable audit trail and no built-in blast-radius limit. Given this endpoint is inherently a privilege-escalation primitive, the cost is justified — the threat model to defend against is less "external attacker breaks in" and more "legitimate credential is compromised or misused, and the system must contain and evidence that."

## Failure modes and containment

- **Token leaked** → device/session binding + short TTL cap the window.
- **Admin credential compromised** → step-up auth at grant time, deny-list on privileged targets, and anomaly alerting catch misuse even though the credential itself is valid.
- **Audit tampering** → external immutable sink removes the admin's own ability to erase evidence.
- **Sensitive-action abuse** → hard-blocking password/email/payment/MFA changes during impersonation removes the highest-value abuse cases even if everything else fails.

## Next step

Before implementation, get the product/support team's answer on the notification question (open decision above) — it changes the shape of the impersonation-session data model (whether it needs a customer-visible audit surface, not just an internal one). Once that's settled, the impersonation token/session lifecycle (start, action-logging, expiry, forced-end) is the piece worth writing a spec for first, since every other control (RBAC, deny-list, blocked mutations) hangs off it.
