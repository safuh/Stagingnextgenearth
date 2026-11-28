# Learning management operations

The learning API is tenant-scoped under
`/api/organizations/{organization_id}/learning`. Every operation requires an
active organisation membership. The API, not the browser, enforces role
permissions. The authenticated member can retrieve their own active role using
`GET /api/organizations/{organization_id}/memberships/me`; this endpoint does
not expose other members or private profile data.

## Roles

- `admin` and `programme_manager`: create and publish courses, create modules
  and lessons, review applications and submissions, assign mentors, and manage
  attendance.
- `researcher`, `youth_volunteer`, and `institutional_partner`: browse
  published courses, apply for enrolment, access approved course material,
  submit assessments, and record their own lesson completion where eligible.

Staff reporting endpoints reject learner roles with HTTP 403. Course and
assessment lookups are scoped to the organisation in the route. Do not treat
client-side navigation or hidden controls as an authorization boundary.

## Course authoring and publication

1. Create a draft with `POST /courses`.
2. Add ordered modules with `POST /courses/{course_id}/modules`.
3. Add ordered lessons with `POST /modules/{module_id}/lessons`.
4. Publish with `POST /courses/{course_id}/publish`. Publishing requires at
   least one lesson; archived courses cannot be republished.
5. Inspect the ordered outline with `GET /courses/{course_id}/curriculum`.
   Draft curriculum is visible to staff only.

Course listing uses `GET /courses`. Managers may request
`?include_drafts=true`; other roles receive published courses only.

## Enrollment and assessment

- Learners apply using `POST /courses/{course_id}/enrollments`.
- Staff review the queue using `GET /courses/{course_id}/enrollments` and
  decide with `POST /courses/{course_id}/enrollments/{learner_id}/decision`.
- Learners with approved enrolment can list assessment instructions using
  `GET /courses/{course_id}/assessments` and submit to
  `POST /assessments/{assessment_id}/submissions`.
- Staff review submissions using `GET /courses/{course_id}/submissions` and
  evaluate an attempt with `POST /submissions/{attempt_id}/evaluate`.

Assessment configuration is never returned by the learner catalogue endpoint.
Submissions and learner identifiers are visible only to authorised programme
staff. Configured multiple-choice quizzes are delivered through the learner quiz
endpoint and scored server-side; answer keys are never returned to the browser.
Assignments and evaluation-type assessments remain staff-reviewed. Automated quiz
results cannot be manually re-scored.

## Mentorship and attendance

- Assign a mentor with `POST /courses/{course_id}/mentorships`. Mentor and
  mentee must be distinct active members of the same organisation; mentors
  must have an administrator, programme-manager, or researcher role.
- Staff can review assignments with
  `GET /courses/{course_id}/mentorships`.
- Record workshop attendance with
  `POST /courses/{course_id}/attendance`. The learner must have approved or
  completed enrolment.
- Staff can review attendance with
  `GET /courses/{course_id}/attendance`.
- Learners can retrieve only relationships involving their own account with
  `GET /my-mentorships`; the response identifies whether the caller is the
  mentor or mentee and includes the course, relationship status and staff notes.
- Learners can retrieve their own records with `GET /my-attendance`, including
  session date, title, course and attendance status. Both personal-history
  endpoints are tenant-scoped and derive the learner identity from the access
  token; callers cannot supply another learner ID.

These endpoints return user IDs, not public profile details. The UI should
resolve display names only through an independently authorised organisation
member directory; do not expose private profile fields to other learners.

## Staff workspace

Authorised administrators and programme managers can retrieve a minimal active
member directory using `GET /api/organizations/{organization_id}/memberships/directory`.
It returns only user IDs and organisation roles, never account identifiers or
private profile fields. Learner roles receive HTTP 403. The staff workspace
uses this directory to select mentors and mentees and uses approved/completed
enrollment records to select attendance participants.

The Next.js staff workspace is available at
`/workspace/learning-admin`. It provides course authoring and publishing,
enrollment decisions, assessment creation and evaluation, mentorship
assignment, and attendance recording/reporting. The workspace is a client
interface only; all permissions remain enforced by the API.

## MVP limitations and operational safeguards

- The Next.js BFF keeps access and rotating refresh tokens in HttpOnly,
  SameSite=Strict cookies; browser JavaScript cannot read them. Mutating BFF
  requests require an exact same-origin Origin header. Refresh coordination is
  process-local, so run one web replica until a shared coordinator is deployed.
  See [web deployment and session security](web-deployment.md).
- Adaptive question banks, notifications, and dedicated role dashboards remain
  future work. Configured multiple-choice quiz delivery and server-side scoring are
  available; assignments and evaluation-type assessments remain staff-reviewed.
- Course resources backed by private object storage must be delivered through
  the existing authorised storage-grant flow; never expose storage references
  or permanent object credentials in public lesson content.
- Apply safeguarding, consent, retention, and privacy review before enrolling
  minors in live programmes or enabling mentor-to-learner communications.


## Applying the curriculum pilot seed

The four-track pilot curriculum is maintained in `scripts/data/nextgen_curriculum_content.json`. To apply or refresh the demo courses, lessons, official source links and formative quizzes, run:

```bash
python scripts/seed_nextgen_demo.py --organization-slug next-gen-for-earth-demo
```

The Render API container startup already invokes this idempotent seed command for the default demo organisation `next-gen-for-earth-demo`, so the staging deployment refreshes the demo catalogue. For a different organisation slug, run the command explicitly in the target environment after backup/approval. The seed updates managed demo lesson text and quiz configuration to match the versioned JSON source; do not use it as a general production content migration where staff-authored lesson edits must be preserved.

The tracks are labelled pilot content and require subject-matter review before cohort delivery. Research, clinical, safeguarding and community-knowledge material must be approved by the relevant organisational leads. Course completion certificates certify platform completion only; they do not imply professional accreditation.


## Learner roster and bulk enrolment decisions

The staff learning workspace exposes a course-scoped roster with enrolment status, progress and application date. Staff can filter by learner ID and lifecycle status. The current identity model does not provide a reviewed display-name field, so the roster temporarily uses learner account IDs. This is an operational identifier, not a privacy-safe learner profile; reviewed display names and role-filtered learner detail remain outstanding.

For bounded batch review, managers can call `POST /courses/{course_id}/enrollments/bulk-decision` with 1–100 unique learner IDs and an `approved` or `rejected` decision. The response contains a result for every learner, including successful transitions and individual conflict/not-found details. Each decision is committed independently, so one invalid or already-decided application does not roll back successful decisions in the same batch. The endpoint requires a course-management role and validates the course within the organisation. The workspace splits larger selections into batches of at most 100 and displays partial failures.

This increment does not replace the cohort/intake model, learner profile and history, bulk invitations, or audited transfer/withdrawal lifecycle; those remain in [issue #143](https://github.com/safuh/Stagingnextgenearth/issues/143).


## Learning outcomes metric definitions

Programme and organisation reports distinguish **unique learners** from **course enrolments**. `totals.learners` counts distinct user IDs across the reporting scope; `totals.enrolments` counts course-enrolment records, so a person enrolled in multiple courses contributes once to unique learners and once per course to enrolments. `approved` and `completed` remain enrolment-state counts. Average progress is calculated by first averaging each learner's progress across their enrolments in the reporting scope, then averaging those learner-level values; each person therefore contributes once to the reported mean. Attendance, mentorship and assessment figures are activity/record counts, not unique learner counts. CSV exports include both unique-learner and enrolment denominators.


## Learning outcomes metric definitions

Programme and organisation reports distinguish **unique learners** from **course enrolments**. `totals.learners` counts distinct user IDs across the reporting scope; `totals.enrolments` counts course-enrolment records, so a person enrolled in multiple courses contributes once to unique learners and once per course to enrolments. `approved` and `completed` remain enrolment-state counts. Average progress is calculated by first averaging each learner's progress across their enrolments in the reporting scope, then averaging those learner-level values; each person therefore contributes once to the reported mean. Attendance, mentorship and assessment figures are activity/record counts, not unique learner counts. CSV exports include both unique-learner and enrolment denominators.


## Staff learner progress detail

Course managers can inspect an individual learner's activity at `GET /courses/{course_id}/learners/{learner_id}/progress`. The route verifies the organisation/course relationship, requires a learning-management role and returns only the matching course enrolment, lesson completion timestamps, assessment attempts/evaluation outcomes, attendance records and mentee-side mentorship assignments. It does not expose mentor notes or unrelated course history. The learning admin roster provides an on-demand expandable activity view; it fetches details only when a staff member opens a learner row.


## Draft curriculum editing

Course metadata, module outlines and lesson content can be updated while a course is in the `draft` state:

- `PATCH /courses/{course_id}` updates course metadata. A supplied `programme_id: null` detaches the course from its programme.
- `PATCH /courses/{course_id}/modules/{module_id}` updates a module title, description or position.
- `PATCH /courses/{course_id}/lessons/{lesson_id}` updates lesson content, resource URL, duration, title, type or position.

All three operations require a course-management role and verify that the target belongs to the route organisation and course. Empty patch bodies and explicit nulls for required fields are rejected. Position conflicts return HTTP 409. Published and archived courses are immutable through these endpoints; the API returns HTTP 409 rather than silently changing content that learners may already be using.

The learning admin now exposes draft course, module and lesson editing forms. Published courses are presented as read-only. This is the first authoring-lifecycle increment, not complete version governance: immutable published snapshots, independent curriculum review, revision history and learner progress pinned to a curriculum version remain outstanding in [issue #144](https://github.com/safuh/Stagingnextgenearth/issues/144).
