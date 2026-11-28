"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiGet, apiPatch, apiPost, clearSession, hasSession } from "@/lib/api";

interface Cohort {
  id: string;
  programme_id: string;
  code: string;
  title: string;
  status: string;
  assigned_count: number;
  inactivity_threshold_days: number;
  absence_threshold: number;
  absence_window_days: number;
  overdue_grace_days: number;
}
interface Programme {
  id: string;
  title: string;
  status: string;
}
interface Member {
  user_id: string;
  role: string;
  roles: string[];
}
interface RiskFlag {
  state: "at_risk" | "clear" | "insufficient_data";
  reason_code?: string | null;
  [key: string]: unknown;
}
interface RiskLearner {
  enrollment_id: string;
  learner_ref: string;
  course_id: string;
  risk_state: "at_risk" | "clear" | "insufficient_data";
  reason_codes: string[];
  flags: Record<string, RiskFlag>;
}
interface RiskReview {
  cohort_id: string;
  cohort_title: string;
  thresholds: Record<string, number>;
  summary: {
    enrolments_reviewed: number;
    unique_learners: number;
    at_risk_learners: number;
    insufficient_data_learners: number;
    clear_learners: number;
    open_interventions: number;
    overdue_interventions: number;
  };
  learners: RiskLearner[];
}
interface ProgrammeReview {
  programme_id: string;
  programme_title: string;
  summary: RiskReview["summary"];
  cohorts: Array<{
    cohort_id: string;
    cohort_title: string;
    thresholds: Record<string, number>;
    summary: RiskReview["summary"];
  }>;
}
interface Intervention {
  id: string;
  cohort_id: string;
  enrollment_id: string;
  learner_ref: string;
  assigned_to: string | null;
  due_date: string | null;
  note: string;
  status: "open" | "in_progress" | "resolved" | "cancelled";
  resolution_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

const facilitatorRoles = new Set(["admin", "founder", "executive", "programme_manager"]);
const shortId = (value: string) => value.slice(-8).toUpperCase();
const formatDate = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleDateString() : "Not recorded";
const stateLabel = (state: string) =>
  state === "at_risk" ? "Review required" : state === "clear" ? "No current flag" : "Insufficient data";

export default function LearningInterventionsPage() {
  const [organizationId, setOrganizationId] = useState("");
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedCohortId, setSelectedCohortId] = useState("");
  const [selectedProgrammeId, setSelectedProgrammeId] = useState("");
  const [review, setReview] = useState<RiskReview | null>(null);
  const [programmeReview, setProgrammeReview] = useState<ProgrammeReview | null>(null);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const base = `/organizations/${organizationId}/learning`;
  const learnerDisplay = (learnerId: string) =>
    review?.learners.find((item) => item.learner_id === learnerId)?.learner_identifier ?? `Learner ${shortId(learnerId)}`;
  const facilitators = members.filter((member) =>
    member.roles.some((role) => facilitatorRoles.has(role)) || facilitatorRoles.has(member.role),
  );

  useEffect(() => {
    if (!hasSession()) {
      setError("Your sign-in session is not available. Sign in again.");
      setLoading(false);
      return;
    }
    apiGet<Array<{ id: string }>>("/organizations")
      .then((items) => {
        if (items[0]) setOrganizationId(items[0].id);
        else {
          setError("No active organisation membership was found.");
          setLoading(false);
        }
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "Unable to load organisations.");
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    Promise.all([
      apiGet<Cohort[]>(`/organizations/${organizationId}/learning/cohorts`),
      apiGet<Programme[]>(`/organizations/${organizationId}/programmes`),
      apiGet<Member[]>(`/organizations/${organizationId}/memberships/directory`),
    ])
      .then(([cohortItems, programmeItems, memberItems]) => {
        setCohorts(cohortItems);
        setProgrammes(programmeItems);
        setMembers(memberItems);
        const firstCohort = cohortItems.find((item) => ["open", "active"].includes(item.status)) ?? cohortItems[0];
        if (firstCohort) {
          setSelectedCohortId(firstCohort.id);
          setSelectedProgrammeId(firstCohort.programme_id);
        }
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load learning operations."))
      .finally(() => setLoading(false));
  }, [organizationId]);

  const refreshCohort = useCallback(async (cohortId = selectedCohortId) => {
    if (!organizationId || !cohortId) return;
    const [risk, actions] = await Promise.all([
      apiGet<RiskReview>(`${base}/cohorts/${cohortId}/risk-review`),
      apiGet<Intervention[]>(`${base}/cohorts/${cohortId}/interventions`),
    ]);
    setReview(risk);
    setInterventions(actions);
  }, [base, organizationId, selectedCohortId]);

  useEffect(() => {
    if (!organizationId || !selectedCohortId) return;
    setError("");
    setReview(null);
    setInterventions([]);
    setReviewLoading(true);
    refreshCohort().catch((cause: unknown) => {
      setReview(null);
      setInterventions([]);
      setError(cause instanceof Error ? cause.message : "Unable to load cohort risk review.");
    }).finally(() => setReviewLoading(false));
  }, [organizationId, selectedCohortId, refreshCohort]);

  useEffect(() => {
    if (!organizationId || !selectedProgrammeId) return;
    setProgrammeReview(null);
    apiGet<ProgrammeReview>(`${base}/programmes/${selectedProgrammeId}/risk-review`)
      .then(setProgrammeReview)
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load programme risk summary."));
  }, [base, organizationId, selectedProgrammeId]);

  async function updateRiskPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCohortId) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const updated = await apiPatch<Cohort>(`${base}/cohorts/${selectedCohortId}`, {
        inactivity_threshold_days: Number(data.get("inactivity_threshold_days")),
        absence_threshold: Number(data.get("absence_threshold")),
        absence_window_days: Number(data.get("absence_window_days")),
        overdue_grace_days: Number(data.get("overdue_grace_days")),
      });
      setCohorts((current) => current.map((item) => item.id === updated.id ? updated : item));
      await refreshCohort();
      setNotice("Cohort risk policy updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update cohort risk policy.");
    } finally {
      setBusy(false);
    }
  }

  async function createIntervention(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCohortId) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    try {
      await apiPost<Intervention>(`${base}/cohorts/${selectedCohortId}/interventions`, {
        enrollment_id: data.get("enrollment_id"),
        assigned_to: data.get("assigned_to"),
        due_date: data.get("due_date") || null,
        note: data.get("note"),
      });
      form.reset();
      await refreshCohort();
      setNotice("Staff follow-up created and audit-recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create intervention.");
    } finally {
      setBusy(false);
    }
  }

  async function startIntervention(item: Intervention) {
    setBusy(true);
    setError("");
    try {
      await apiPatch<Intervention>(`${base}/interventions/${item.id}`, { status: "in_progress" });
      await refreshCohort();
      setNotice("Intervention moved to in progress.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update intervention.");
    } finally {
      setBusy(false);
    }
  }

  async function editIntervention(event: FormEvent<HTMLFormElement>, item: Intervention) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await apiPatch<Intervention>(`${base}/interventions/${item.id}`, {
        assigned_to: data.get("assigned_to"),
        due_date: data.get("due_date") || null,
        note: data.get("note"),
      });
      await refreshCohort();
      setNotice("Follow-up details and assignment updated and audit-recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update follow-up details.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelIntervention(item: Intervention) {
    setBusy(true);
    setError("");
    try {
      await apiPatch<Intervention>(`${base}/interventions/${item.id}`, { status: "cancelled" });
      await refreshCohort();
      setNotice("Follow-up cancelled and audit-recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to cancel follow-up.");
    } finally {
      setBusy(false);
    }
  }

  async function resolveIntervention(event: FormEvent<HTMLFormElement>, item: Intervention) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await apiPatch<Intervention>(`${base}/interventions/${item.id}`, {
        status: "resolved",
        resolution_note: data.get("resolution_note"),
      });
      await refreshCohort();
      setNotice("Intervention resolved and resolution recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to resolve intervention.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading learner support operations…</p></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/workspace"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">PROGRAMME OPERATIONS / LEARNER SUPPORT</p>
        <h1 className="workspace-title">Learner <em>support.</em></h1>
        <p className="workspace-muted">Transparent cohort signals and staff-owned follow-ups. These indicators support human review; they never make enrolment, grading or eligibility decisions.</p>
        <div className="staff-actions">
          <label>Cohort
            <select value={selectedCohortId} onChange={(event) => {
              const next = cohorts.find((item) => item.id === event.target.value);
              setSelectedCohortId(event.target.value);
              if (next) setSelectedProgrammeId(next.programme_id);
            }}>
              <option value="">Choose a cohort</option>
              {cohorts.map((cohort) => <option key={cohort.id} value={cohort.id}>{cohort.title} · {cohort.code}</option>)}
            </select>
          </label>
          <label>Programme overview
            <select value={selectedProgrammeId} onChange={(event) => setSelectedProgrammeId(event.target.value)}>
              <option value="">Choose a programme</option>
              {programmes.map((programme) => <option key={programme.id} value={programme.id}>{programme.title}</option>)}
            </select>
          </label>
          <Link className="secondary-action" href="/workspace/learning-admin">Back to learning management</Link>
        </div>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}

        {programmeReview && (
          <section className="staff-card" aria-labelledby="programme-risk-heading">
            <p className="eyebrow">PROGRAMME PORTFOLIO</p>
            <h2 id="programme-risk-heading">{programmeReview.programme_title}</h2>
            <div className="staff-grid">
              <article><strong>{programmeReview.summary.unique_learners}</strong><span>Unique learners</span></article>
              <article><strong>{programmeReview.summary.at_risk_learners}</strong><span>Learners requiring review</span></article>
              <article><strong>{programmeReview.summary.insufficient_data_learners}</strong><span>Insufficient evidence</span></article>
              <article><strong>{programmeReview.summary.open_interventions}</strong><span>Open follow-ups</span></article>
            </div>
            <p className="workspace-muted">Cohort roll-up: {programmeReview.cohorts.length} intakes. Counts are evidence-based and no missing activity is treated as disengagement.</p>
          </section>
        )}

        {reviewLoading && <p className="workspace-muted">Refreshing cohort evidence…</p>}
        {review && (
          <>
            <section className="staff-card" aria-labelledby="cohort-risk-heading">
              <p className="eyebrow">COHORT REVIEW</p>
              <h2 id="cohort-risk-heading">{review.cohort_title}</h2>
              <div className="staff-grid">
                <article><strong>{review.summary.unique_learners}</strong><span>Unique learners</span></article>
                <article><strong>{review.summary.at_risk_learners}</strong><span>Review required</span></article>
                <article><strong>{review.summary.insufficient_data_learners}</strong><span>Insufficient evidence</span></article>
                <article><strong>{review.summary.open_interventions}</strong><span>Open interventions</span></article>
                <article><strong>{review.summary.overdue_interventions}</strong><span>Overdue follow-ups</span></article>
              </div>
              <p className="workspace-muted">Policy: {review.thresholds.inactivity_threshold_days} days inactivity · {review.thresholds.absence_threshold} absences in {review.thresholds.absence_window_days} days · {review.thresholds.overdue_grace_days} days assessment grace.</p>
              <div className="staff-actions">
                <button className="secondary-action" disabled={busy} onClick={() => void refreshCohort()}>Refresh evidence</button>
                <details>
                  <summary>Adjust cohort thresholds</summary>
                  <form onSubmit={updateRiskPolicy}>
                    <label>Inactivity threshold (days)<input type="number" name="inactivity_threshold_days" min="1" max="90" defaultValue={review.thresholds.inactivity_threshold_days} required /></label>
                    <label>Repeated absences threshold<input type="number" name="absence_threshold" min="1" max="20" defaultValue={review.thresholds.absence_threshold} required /></label>
                    <label>Absence review window (days)<input type="number" name="absence_window_days" min="7" max="90" defaultValue={review.thresholds.absence_window_days} required /></label>
                    <label>Assessment overdue grace (days)<input type="number" name="overdue_grace_days" min="0" max="30" defaultValue={review.thresholds.overdue_grace_days} required /></label>
                    <button className="primary-action" disabled={busy}>Save risk policy</button>
                  </form>
                </details>
              </div>
            </section>

            <section className="staff-card" aria-labelledby="risk-roster-heading">
              <h2 id="risk-roster-heading">Learner evidence review</h2>
              {review.learners.length === 0 ? <p className="workspace-muted">No approved enrolments are assigned to this cohort yet.</p> : review.learners.map((learner) => (
                <article className="staff-record" key={learner.enrollment_id}>
                  <div className="staff-actions">
                    <strong>Learner {learner.learner_ref}</strong>
                    <span className={`status-pill status-${learner.risk_state}`}>{stateLabel(learner.risk_state)}</span>
                  </div>
                  <small>Course reference {shortId(learner.course_id)} · Enrolment {shortId(learner.enrollment_id)}</small>
                  <div className="staff-actions">
                    {Object.entries(learner.flags).map(([key, flag]) => (
                      <span key={key} className={`status-pill status-${flag.state}`}>{key}: {stateLabel(flag.state)}</span>
                    ))}
                  </div>
                  {learner.reason_codes.length > 0 && <small>Reason codes: {learner.reason_codes.join(" · ")}</small>}
                  <details>
                    <summary>Evidence and thresholds</summary>
                    <pre className="workspace-data">{JSON.stringify(learner.flags, null, 2)}</pre>
                  </details>
                </article>
              ))}
            </section>

            <section className="staff-card" aria-labelledby="intervention-create-heading">
              <p className="eyebrow">FACILITATOR ACTIONS</p>
              <h2 id="intervention-create-heading">Create a follow-up</h2>
              <form onSubmit={createIntervention}>
                <label>Learner enrolment
                  <select name="enrollment_id" required defaultValue="">
                    <option value="" disabled>Select learner</option>
                    {review.learners.map((learner) => <option key={learner.enrollment_id} value={learner.enrollment_id}>Learner {learner.learner_ref} · {learner.risk_state.replaceAll("_", " ")}</option>)}
                  </select>
                </label>
                <label>Action owner
                  <select name="assigned_to" required defaultValue="">
                    <option value="" disabled>Select programme manager</option>
                    {facilitators.map((member) => <option key={member.user_id} value={member.user_id}>{member.role.replaceAll("_", " ")} · {shortId(member.user_id)}</option>)}
                  </select>
                </label>
                <label>Follow-up due date<input type="date" name="due_date" /></label>
                <label>Operational note<textarea name="note" minLength={3} maxLength={3000} required placeholder="Record the practical follow-up action and expected outcome." /></label>
                <p className="workspace-muted">Do not record health, disability, safeguarding case details or other sensitive personal information here.</p>
                <button className="primary-action" disabled={busy || review.learners.length === 0 || facilitators.length === 0}>Create staff follow-up</button>
              </form>
            </section>

            <section className="staff-card" aria-labelledby="interventions-heading">
              <h2 id="interventions-heading">Follow-up register</h2>
              {interventions.length === 0 ? <p className="workspace-muted">No follow-ups recorded for this cohort.</p> : interventions.map((item) => (
                <article className="staff-record" key={item.id}>
                  <div className="staff-actions">
                    <strong>Learner {item.learner_ref}</strong>
                    <span className={`status-pill status-${item.status}`}>{item.status.replaceAll("_", " ")}</span>
                  </div>
                  <p>{item.note}</p>
                  <small>Owner {item.assigned_to ? shortId(item.assigned_to) : "Unassigned"} · Due {formatDate(item.due_date)} · Created {formatDate(item.created_at)}</small>
                  {item.resolution_note && <small>Resolution: {item.resolution_note}</small>}
                  {["open", "in_progress"].includes(item.status) && (
                    <details>
                      <summary>Edit owner, due date or action note</summary>
                      <form onSubmit={(event) => void editIntervention(event, item)}>
                        <label>Action owner
                          <select name="assigned_to" required defaultValue={item.assigned_to ?? ""}>
                            <option value="" disabled>Select programme manager</option>
                            {facilitators.map((member) => <option key={member.user_id} value={member.user_id}>{member.role.replaceAll("_", " ")} · {shortId(member.user_id)}</option>)}
                          </select>
                        </label>
                        <label>Follow-up due date<input type="date" name="due_date" defaultValue={item.due_date ?? ""} /></label>
                        <label>Operational note<textarea name="note" minLength={3} maxLength={3000} required defaultValue={item.note} /></label>
                        <button className="secondary-action" disabled={busy}>Save follow-up changes</button>
                      </form>
                    </details>
                  )}
                  {item.status === "open" && <button className="secondary-action" disabled={busy} onClick={() => void startIntervention(item)}>Start follow-up</button>}
                  {item.status === "in_progress" && (
                    <>
                      <form onSubmit={(event) => void resolveIntervention(event, item)}>
                        <label>Resolution note<input name="resolution_note" minLength={3} maxLength={3000} required placeholder="Record the outcome of the follow-up" /></label>
                        <button className="secondary-action" disabled={busy}>Resolve follow-up</button>
                      </form>
                      <button className="secondary-action" disabled={busy} onClick={() => void cancelIntervention(item)}>Cancel follow-up</button>
                    </>
                  )}
                </article>
              ))}
            </section>
          </>
        )}
        {!selectedCohortId && cohorts.length === 0 && <section className="staff-card"><h2>No cohorts yet</h2><p className="workspace-muted">Create a programme intake in Learning Management before configuring cohort risk review.</p><Link className="secondary-action" href="/workspace/learning-admin">Open learning management</Link></section>}
      </section>
    </main>
  );
}
