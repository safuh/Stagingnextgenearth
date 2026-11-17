# Employment applications

The public careers flow is authenticated. Candidates register or sign in through the public account experience before submitting an application; the application endpoint never creates an employee membership.

## Candidate lifecycle

- Submit an application to `POST /api/public/organizations/{organization_slug}/employment-applications`.
- Read only the signed-in candidate's own application history through `GET /api/public/organizations/{organization_slug}/my-employment-applications`.
- Withdraw a pending application through `POST /api/public/organizations/{organization_slug}/employment-applications/{application_id}/withdraw`.
- A withdrawn application remains in the review record and cannot later be approved.
- A candidate may submit a new application after withdrawal or a final decision. Only one pending application per candidate and organisation is allowed.
- Approved candidates receive an active employee membership after an authorised reviewer approves the application. Their directory profile remains private and pending independent publication review.

## Reviewer controls

Founder, executive and administrator roles can review the tenant-scoped queue and approve or reject pending applications. Applicants cannot review their own applications. Decisions are final for that application record; a subsequent application is a separate record. Concurrent withdrawal and decision operations lock the application row on databases that support row-level locking.

## Data handling

Application details and candidate history are private. Candidate history responses omit the applicant's account identifier; reviewer queue responses include the identifier for authorised staff. Public directory publication is a separate review process. Do not collect identity document numbers, passwords, health information or other unnecessary sensitive data in application text.

## Resubmission integrity

The database enforces one pending application per organisation and user with a partial unique index. Historical withdrawn, rejected and approved records are retained. Downgrading the resubmission migration is intentionally blocked when duplicate historical applications exist, because restoring the former one-record-per-user constraint would otherwise destroy the ability to represent that history.
