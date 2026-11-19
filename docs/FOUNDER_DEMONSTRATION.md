# Founder demonstration and handover

## Demonstration objective

Demonstrate one coherent organisational platform: a public website backed by governed portal records, distinct access journeys for learners and organisation members, and an executive view that separates operational records from verified public claims.

## Suggested 20-minute run of show

1. **Public organisation website (3 min)**
   - Show published programmes, courses, approved people and partner records.
   - Open a programme detail page and show projects, learning opportunities and reported indicators.
   - Explain that public sections are projections of approved portal records; review drafts and unverified partner candidates remain private.

2. **Learner journey (4 min)**
   - Open `/learners`.
   - Optionally pre-create learner demo identities from the bootstrap manifest using a dedicated password environment variable per account.
   - The bootstrap submits applications to published courses but deliberately does not approve them or grant learner memberships.
   - Register a new learner account with a unique test email.
   - Apply to a published course.
   - Show the learner's own application status.
   - In the course administration workspace, approve the application and demonstrate that an active learner membership is created.
   - Sign in as the learner and show the protected curriculum, lessons, assessments, progress and certificate verification when configured.

3. **Staff and partner onboarding (4 min)**
   - Register an identity at `/staff/register`.
   - As an organisation administrator, invite the exact registered email and assign the approved role.
   - Share the generated invitation URL privately.
   - Sign in as the invited account and accept the invitation.
   - Show that role assignment happens only through an authorised membership operation, not through the public registration form.

4. **Programme and people operations (3 min)**
   - Show programme catalogue, delivery activities, volunteer allocations and attendance.
   - Distinguish public people-directory profiles from authenticated membership accounts.
   - Explain the volunteer safeguarding gate and approval process.

5. **Research, climate intelligence and ODK (4 min)**
   - Show research studies, proposal/protocol governance, dataset review and provenance.
   - Open Research → Configure ODK Central; show the encrypted connection summary, project form catalogue, explicit form mappings and recent sync history.
   - Demonstrate a real ODK Central connection and worker sync only when a test Central project and dedicated read-only account are configured.
   - Demonstrate NASA POWER, OpenAlex and climate ingestion only when the providers are configured and live data is available.
   - Distinguish imported observations from independently reviewed, safeguarded research evidence.

6. **Founder / executive overview and CMS (3 min)**
   - Open Administration → Executive overview.
   - Review membership, programme, study, course, partner and CMS pipeline counts.
   - Explain that these are portal record counts, not independently verified impact.
   - Show source URLs, editorial review, independent approval and publication controls.
   - Use **Print / save founder briefing** to create a meeting handout or PDF from the live snapshot.

## Evidence and presentation rules

- Use a dedicated demo organisation or test accounts; do not use real employee credentials or disclose private invitation URLs in a presentation.
- Never present seed data as independently verified implementation, active staff, signed partnerships, completed events or measured impact.
- Partner candidates remain unverified until the organisation records evidence and changes their verification state.
- CMS entries remain unpublished until an authorised reviewer verifies the source and approves publication. Authors cannot approve their own submissions.
- Research concepts remain concepts until protocol, ethics/safeguarding, investigators, timeline and approvals are established.
- If a provider integration is unavailable, state that it is configured but not currently returning live data; do not fabricate a result.
- Do not use production learner records for a demonstration.

## Go-live acceptance checklist

- [ ] Latest branch pulled and all database migrations applied without deleting database volumes.
- [ ] Backend test suite, Ruff, frontend lint and production build pass on the deployment target.
- [ ] PostGIS migration and spatial smoke tests pass against the deployment database.
- [ ] Owner account, MFA/credential policy, secrets and backups are configured for production.
- [ ] A real employee account has registered, been invited and accepted the invitation.
- [ ] A second authorised reviewer has independently reviewed and published a source-verified CMS entry.
- [ ] A learner has registered, applied to a published course, been approved and accessed protected learning content.
- [ ] Volunteer safeguarding and any required parent/guardian consent have been verified before approval.
- [ ] Partner records have been verified before public display.
- [ ] NASA POWER, OpenAlex and climate-provider credentials, quotas, provenance and failure handling are checked in the target environment.
- [ ] ODK Central connection test succeeds, form mappings are verified against a test form, scheduled sync worker is running, pagination and duplicate handling are confirmed, and imported observations remain pending review.
- [ ] Public website, accessibility, mobile layout, privacy notices, security headers, logging and recovery procedures are reviewed.

The print action creates a snapshot of the current executive overview. It does not certify the underlying data or replace independent programme, finance, research, safeguarding or partner verification.
