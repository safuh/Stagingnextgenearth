# Learner Risk Review and Facilitator Interventions

## Purpose and boundary

This capability closes the learning support loop with deterministic, cohort-scoped indicators and human-owned follow-up. It is not predictive analytics, a learner score, a diagnosis, or an automated decision system. A risk flag is a prompt for a qualified facilitator to review the underlying activity and speak with the learner through the programme's normal support process.

The system must never automatically suspend, reject, grade, remove eligibility from, or notify a learner based on these indicators. Missing data must remain visibly distinct from a risk finding.

## Configurable cohort policy

Each cohort carries its own validated thresholds:

| Policy | Default | Accepted range | Meaning |
|---|---:|---:|---|
| Inactivity threshold | 14 days | 1–90 | Days since the latest recorded lesson completion, assessment submission, or present/late attendance |
| Repeated absence threshold | 2 | 1–20 | Number of attendance records explicitly marked absent |
| Absence review window | 30 days | 7–90 | Rolling calendar-day window for absence counting |
| Assessment overdue grace | 2 days | 0–30 | Additional days after an explicitly recorded assessment due date |

The policy can be configured at cohort creation and revised by authorised programme staff. Every review returns the policy used so that the result can be interpreted and reproduced.

## Explainable signal rules

### Inactivity

- Use the most recent recorded lesson completion, assessment submission, or present/late attendance for the learner's course enrolment.
- If no such activity exists, return `insufficient_data` with `no_recorded_learner_activity`.
- Otherwise compare elapsed calendar days with the cohort threshold and return `clear` or `at_risk` with the measured days and last activity timestamp.

### Attendance

- Count attendance records within the configured review window.
- Count only records explicitly marked `absent` toward the repeated-absence threshold; present, late and excused records are not absences.
- If no attendance records exist in the window, return `insufficient_data` with `no_attendance_records_in_window`.
- Otherwise return the absence count, denominator, threshold and window alongside the `clear` or `at_risk` state.

### Overdue assessments

- Consider only assessments with an actual due date/time.
- An assessment is overdue only after the due time plus the cohort grace period and when the learner has no recorded submission attempt.
- If no assessments have due dates, return `insufficient_data` with `no_assessments_with_due_dates`.
- Return each overdue assessment's title, ID and due date so staff can inspect the evidence.

### Combined state

- `at_risk`: at least one signal is `at_risk`.
- `insufficient_data`: no signal is at risk and at least one signal lacks enough evidence.
- `clear`: all three signals are supported by evidence and none is at risk.

Reason codes are stable machine-readable labels; the interface should translate them into plain-language explanations. Never display an opaque score.

## Facilitator intervention lifecycle

1. Review the cohort signal and supporting counts/dates.
2. Confirm the learner and enrolment are in the selected cohort and approved for delivery.
3. Create a staff-only follow-up record with an active programme manager/administrator as owner, optional due date, and an operational action note.
4. Move the record from `open` to `in_progress` when work starts.
5. Resolve it with an outcome note, or cancel it when the action is no longer appropriate.
6. Revisit the cohort review and close the loop on overdue actions.

Every create, update, reassignment and resolution is recorded in the organisation audit trail. Intervention notes are not learner-visible. They must not contain health, disability, safeguarding case details, sensitive personal data or restricted community information. Use the designated safeguarding process for safeguarding concerns.

## Authorised workflows

- Cohort risk review: `GET /organizations/{organization_id}/learning/cohorts/{cohort_id}/risk-review`
- Programme risk overview: `GET /organizations/{organization_id}/learning/programmes/{programme_id}/risk-review`
- List interventions: `GET /organizations/{organization_id}/learning/cohorts/{cohort_id}/interventions`
- Create intervention: `POST /organizations/{organization_id}/learning/cohorts/{cohort_id}/interventions`
- Update or resolve: `PATCH /organizations/{organization_id}/learning/interventions/{intervention_id}`

Only organisation staff with the learning-management roles can view risk reviews or private intervention records. Every query is tenant-scoped. Intervention creation requires an approved enrolment assigned to the selected cohort and an active staff owner.

## Operating cadence

- Review open cohort flags at least weekly during an active intake.
- Review `insufficient_data` separately; improve attendance/activity capture before drawing conclusions.
- Assign each follow-up to one accountable staff owner and a realistic due date.
- Escalate sensitive or safeguarding matters outside the ordinary intervention note.
- Review overdue interventions and record outcomes; do not infer that a closed intervention means the learner has completed the course.
- Revisit thresholds with programme leads when the delivery pattern or attendance cadence changes.

## Acceptance evidence

- Threshold validation and cohort persistence tests pass.
- Date-boundary, no-activity, no-attendance, due-date, grace-period and submission tests pass.
- Cross-tenant access is denied.
- Learner roles cannot access risk reviews or private interventions.
- Create, assign, update, cancel and resolve transitions are audited.
- Programme and cohort dashboards expose counts and reason codes without exposing private notes to learners.
- No automated adverse action or external notification is triggered.
