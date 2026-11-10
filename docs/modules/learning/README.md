# Learning and training module

The learning module is tenant-scoped and uses organisation memberships for every
management and learner workflow. It is designed for NextGen for Earth's climate
literacy, youth leadership, community engagement, research skills, safeguarding,
volunteer development and mentorship programmes.

## MVP capabilities

- Course catalogue, draft/publish lifecycle and delivery mode.
- Ordered modules and lessons with text, video, document, link and workshop
  content references.
- Learner applications with explicit administrator/programme-manager approval.
- Quiz, assignment and evaluation definitions; learner submissions and
  recorded staff evaluations.
- Course-scoped mentor-to-mentee assignments.
- Workshop attendance with duplicate-session protection.
- Course resources referencing private storage objects or externally hosted
  learning media. Storage credentials and signed URLs are not persisted.
- Learner progress reporting and automatic certificate issuance at 100% progress
  after all defined assessments meet their pass marks.
- Publicly verifiable certificate codes, with revocation state retained in the
  database.

## API

All endpoints are under
`/api/organizations/{organization_id}/learning` and require an active
organisation membership, except none of the management APIs are anonymous.
Course and assessment administration, application decisions, mentorship
assignment, attendance, resource registration and evaluation require the
`admin` or `programme_manager` role. Enrolled learners may submit assessments
and update their own progress.

Key routes:

- `POST/GET /courses`, `POST /courses/{course_id}/publish`
- `POST /courses/{course_id}/modules`, `POST /modules/{module_id}/lessons`
- `POST /courses/{course_id}/enrollments` and
  `POST /courses/{course_id}/enrollments/{learner_id}/decision`
- `POST /courses/{course_id}/assessments`,
  `POST /assessments/{assessment_id}/submissions`,
  `POST /submissions/{attempt_id}/evaluate`
- `POST /courses/{course_id}/mentorships`
- `POST /courses/{course_id}/attendance`
- `POST /courses/{course_id}/resources`
- `POST /courses/{course_id}/enrollments/{learner_id}/progress`
- `GET /courses/{course_id}/progress`
- `GET /certificates/verify/{verification_code}`

## Operational boundaries

This increment stores lesson/resource metadata; actual media bytes must use the
existing private object-storage and scanning pipeline. Do not store public
bucket URLs or signed URLs as durable resource identifiers. Quiz scoring is
staff-evaluated in this MVP; the configuration field is metadata, not an
execution engine. Certificate issuance is a completion credential, not an
accredited qualification. A production rollout still needs safeguarding review,
retention policy, learner consent/guardian workflows where applicable, email
notifications, accessible portal UI and certificate PDF rendering.
