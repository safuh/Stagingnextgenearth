# Staff and partner provisioning for founder demonstrations

The bootstrap command supports repeatable staff provisioning through the manifest's
`staff` array. The canonical public seed intentionally leaves this array empty:
real employee and partner identities must be supplied by the organisation, never
invented in source control.

## Add a real demo employee

1. Register an account using the employee's own email address at
   `/staff/register`, or choose an email address controlled by the demo operator.
2. Add an entry to a private copy of
   `scripts/data/nextgen_for_earth.seed.json`:

```json
{
  "identifier": "employee@example.org",
  "role": "employee",
  "password_env": "BOOTSTRAP_EMPLOYEE_PASSWORD"
}
```

Append this object to the existing top-level `staff` array. Preserve the other
manifest sections so the normal organisation, programme, people and CMS bootstrap
still runs.

3. Set the password environment variable without putting the password in the
   manifest or committing it:

```bash
read -rsp "Demo employee password: " BOOTSTRAP_EMPLOYEE_PASSWORD
printf '\n'
export BOOTSTRAP_EMPLOYEE_PASSWORD
```

4. Run the normal bootstrap against the running local API:

```bash
make bootstrap MANIFEST=/absolute/path/to/private-nextgen-seed.json
```

The bootstrap process registers or reuses the identity, authenticates as the
organisation owner to create the invitation, then authenticates as the intended
employee to accept it. The invitee receives only the role declared in the
manifest. Supported staff roles include `admin`, `founder`, `executive`,
`employee`, `programme_manager`, `researcher`, `youth_volunteer` and
`institutional_partner`. Founder, executive and administrator grants remain
subject to the organisation owner's elevated-role authority. An existing
invitation with a different role is not accepted automatically; cancel/reissue it
through the audited administration workflow first.

## Repeatability and safety

- The manifest stores no passwords. Password values are read from the named
  environment variables at runtime.
- The script does not overwrite an already-active membership or silently change
  its primary role. Resolve an existing role mismatch through the audited
  administration workspace.
- Suspended memberships are not silently reactivated.
- Invitation acceptance is performed as the intended account, not by the owner.
- Never commit the private manifest or export real credentials into a shared
  shell session.
- For a browser acceptance test, sign in at `/staff/login`, open
  Administration → Members, and confirm the employee's email, active status and
  assigned role. Then sign out and verify that the employee can reach only the
  workspaces authorised by that role.

## Learner accounts are separate

Do not put public learners in the staff bootstrap array. Learners use
`/learners` to register, sign in, discover published courses and apply. A course
manager must approve an application before the learner membership and protected
curriculum access are activated.

The bootstrap regression suite verifies owner-authorised administrator invitations, invitee-only acceptance, and refusal to accept an existing invitation whose role differs from the manifest:

```bash
uv run pytest -q tests/test_bootstrap.py
```
