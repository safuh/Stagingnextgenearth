# Organisation administration workspace

The administrator portal is available at `/workspace/administration` and is linked from the organisation workspace for active administrator members.

## Capabilities

- View organisation memberships and their role/status.
- Invite an existing platform account as programme manager, researcher, youth volunteer or institutional partner.
- Change member roles and suspend/reactivate existing memberships.
- Transfer organisation ownership to an existing active member.
- Review the latest 100 organisation governance audit events.

## Access and safety boundaries

The portal reads its tenant from the caller's active organisation list and then loads the caller's membership. The UI is not an authorization boundary: every read and mutation is independently protected by the API's active membership and administrator checks.

Invitations remain in the `invited` state until the invited account accepts. The portal does not create user accounts, expose passwords or activate invitations on behalf of invitees. Membership identifiers are shown to administrators because the existing membership and audit APIs expose those identifiers to administrators.

Only the current organisation owner may grant administrator access or transfer ownership. A separate administrator-only summary endpoint supplies owner metadata so the portal can display the transfer form only to the current owner. The backend prevents demoting or suspending the owner before transfer and prevents removal of the last active administrator. Ownership transfer requires an already-active member and atomically changes the owner and membership roles.

Audit history is tenant-scoped and administrator-only. It records governance changes, not a complete application-wide activity log. The portal does not expose learner records, research file contents, raw climate data or participant-level programme data.

## Session limitation

The web client currently keeps access tokens in memory. Reloading the page ends the client session. A production deployment should place authentication behind a server-side BFF with secure HttpOnly cookies, CSRF protections and explicit session rotation before broad deployment.
