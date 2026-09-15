## Attack surface

An impersonation endpoint is a privilege-escalation primitive by design — it mints authority for support staff to *become* another identity. The surface has four distinct actors to think about: the support agent (could be compromised, coerced, or malicious), the target user (whose account is now exposed), the endpoint itself (a high-value target for attackers who compromise any admin credential), and downstream systems that trust the resulting session (they can't tell "real user" from "impersonated user" unless you make them).

Concrete vectors:

- **Credential/session compromise of a support agent** → now equivalent to compromising *any* customer account on demand. This is the dominant risk; it turns "one support account phished" into "arbitrary account takeover," so the endpoint's blast radius is much larger than a normal admin tool.
- **Scope creep** — impersonation granted broader than debugging requires (e.g., can also change email/password, initiate payments, export data) rather than a read-mostly debug view.
- **No visibility to the impersonated user** — actions taken during impersonation are indistinguishable from the user's own actions in logs/audit trails downstream, enabling repudiation disputes and hiding abuse.
- **Missing/weak authorization gate** — any admin/support role can impersonate any user, including other admins, VIPs, or the support agent's own manager/coworkers (insider snooping).
- **Session lifecycle** — impersonation token that doesn't expire quickly, isn't scoped to the ticket/reason it was issued for, or survives after the debugging task ends.
- **Downstream trust ambiguity** — payment processors, notification systems, or other services that receive the impersonated session and can't distinguish it from a first-party user action (e.g., triggers a "you logged in from a new device" email to the *user*, tipping them off in a confusing way, or worse, silently doesn't).
- **Endpoint discovery/abuse from outside** — if this is reachable from anything other than the internal admin surface (exposed route, weak network segmentation), it becomes a direct account-takeover API for attackers.
- **Lack of step-up auth** — support agent's normal session cookie alone is enough to impersonate, with no re-authentication for this specific high-privilege action.

## Design principles to keep the model tight

**Primary lens — security by construction.** Impersonation should not be "log in as the user" (full authority transfer) but a purpose-built, minimal capability:

- **Least privilege by default**: issue a scoped, clearly-marked "support session" — not the user's actual session token. Restrict its capabilities to what debugging requires (read account state, view recent activity/errors) and explicitly deny destructive/sensitive actions (password/email change, payment methods, data export, deleting the account) unless a specific ticket explicitly requires it and a second approval gates it.
- **Mediation at every trust boundary**: every downstream service that receives a request under impersonation should be able to see it's impersonated (a distinct claim in the token, e.g. `acting_as: support_agent_id, on_behalf_of: user_id, ticket: id`), not a bare user session. This lets you fan out policy decisions (e.g., "disallow payment actions under impersonation") to the services that actually own those invariants, rather than centralizing every rule in the impersonation endpoint itself.
- **Explicit authorization, not implicit role check**: gate by (a) support role, (b) an open ticket/reason code tied to the specific user, (c) target-user tier restrictions (e.g., admins, executives, or flagged accounts require a second approver). Don't let "is support staff" alone be sufficient.
- **Short-lived, narrowly-scoped tokens**: minutes-to-low-hours TTL, single target user, auto-revoked when the ticket closes or on agent logout.
- **Step-up authentication** on the impersonation action itself (re-auth/MFA), since it's the highest-leverage action a support account can take.

**Challenge — fault containment and blast radius.** The security-by-construction lens optimizes for preventing bad actions; the failure mode it under-weights is *detection and recovery* once an agent account is already compromised or an agent goes rogue. Scoped tokens reduce blast radius per-incident, but you also need:

- **Full audit trail, attributable and tamper-evident**: every impersonated action logged with `(support_agent_id, ticket_id, user_id, action, timestamp)`, stored somewhere the support org can't quietly edit (append-only / shipped to a separate log sink support doesn't have write access to).
- **User-visible notice**: notify the user (email/in-app) that their account was accessed by support, ideally in real time or on session end, with ticket reference. This closes the "user has no way to detect abuse" gap and is often a compliance requirement (SOC2/GDPR-adjacent).
- **Rate/frequency anomaly detection**: alert on unusual patterns — one agent impersonating many accounts in a short window, impersonating the same user repeatedly without ticket correlation, or impersonating admin/exec accounts.
- **Break-glass review**: routine sampling or mandatory review of impersonation logs (even 100% review for a low-volume feature) rather than "logs exist but no one reads them."

The tension: pure least-privilege scoping (primary lens) reduces what a single impersonation *can* do; audit/visibility (challenge lens) reduces how long abuse goes *undetected*. You need both — scoping without audit just makes abuse quieter, not less likely.

## Tradeoffs

- Scoped/limited-capability sessions add engineering cost (every downstream consumer must understand the "acting-as" claim) versus the simpler-but-riskier "mint the user's actual session."
- Step-up auth and ticket-binding add friction for support staff, which is the right tradeoff given the leverage this endpoint grants, but will draw pushback — worth setting SLA expectations with the support org up front.
- Real-time user notification is the most defensible-by-default choice but may need a product decision (some orgs delay notice to avoid alarming users during active fraud investigations where the *user's own* account may be compromised, not the target of legitimate debugging). **OPEN DESIGN DECISION**: whether notification is synchronous (at impersonation start) or deferred (session-end digest) — resolve with legal/compliance and product, not engineering alone.
- **OPEN DESIGN DECISION**: whether impersonation of admin/internal accounts is allowed at all, or categorically blocked — depends on what "support staff" needs to debug versus what's reachable through safer means (read-only internal tooling, log access) without a live session.

## Next step

Before implementation: confirm (1) what capabilities support actually needs (read-only debug view is often sufficient and eliminates most of this threat model), (2) who can approve impersonation of sensitive account tiers, and (3) where the audit log ships to and who reviews it. If read-only telemetry access can solve the underlying support need, that's a smaller, tighter alternative worth ruling out before building full impersonation.