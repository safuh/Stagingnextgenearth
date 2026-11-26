"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPatch, apiPost, clearSession, hasSession } from "@/lib/api";

type Programme = {
  id: string; title: string; slug: string; summary: string | null;
  status: string; start_date: string | null; end_date: string | null;
};
type Project = {
  id: string; title: string; summary: string | null; status: string;
  country_code: string; county: string | null;
};
type Goal = { id: string; title: string; description: string | null; target_date: string | null; status: string };
type Milestone = { id: string; goal_id: string; title: string; description: string | null; due_date: string | null; status: string };
type IndicatorProgress = {
  indicator: { id: string; key: string; title: string; description: string | null; unit: string; direction: string; baseline_value: number | null; target_value: number | null };
  latest_measurement: { value: number; period_start: string; period_end: string } | null;
  progress_percent: number | null;
};
type MemberOption = { user_id: string; role: string };
type Deliverable = { id: string; title: string; description: string | null; due_date: string | null; status: string; project_id: string | null; assigned_to: string | null; evidence_url: string | null; review_note: string | null };
type DeliverableEvent = { id: string; actor_user_id: string | null; action: string; details: Record<string, unknown>; created_at: string };
type TimelineEvent = { id: string; entity_type: string; entity_id: string; entity_title: string; actor_user_id: string; action: string; details: Record<string, unknown>; created_at: string };
const transitions: Record<string, string[]> = {
  draft: ["planned", "archived"],
  planned: ["active", "archived"],
  active: ["completed", "archived"],
  completed: ["archived"],
  archived: [],
};

export default function ProgrammeAdminPage() {
  const [organizationId, setOrganizationId] = useState("");
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [members, setMembers] = useState<MemberOption[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [selectedGoalId, setSelectedGoalId] = useState("");
  const [indicators, setIndicators] = useState<IndicatorProgress[]>([]);
  const [deliverables, setDeliverables] = useState<Deliverable[]>([]);
  const [activityTimeline, setActivityTimeline] = useState<TimelineEvent[]>([]);
  const [deliverableEvents, setDeliverableEvents] = useState<Record<string, DeliverableEvent[]>>({});
  const [historyOpen, setHistoryOpen] = useState<Record<string, boolean>>({});
  const [historyLoading, setHistoryLoading] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load(id: string) {
    const rows = await apiGet<Programme[]>(`/organizations/${id}/programmes`);
    setProgrammes(rows);
    setSelectedId((current) => rows.some((item) => item.id === current) ? current : rows[0]?.id ?? "");
  }

  useEffect(() => {
    if (!hasSession()) {
      setError("Sign in to manage organisation programmes.");
      setLoading(false);
      return;
    }
    apiGet<Array<{ id: string }>>("/organizations")
      .then((items) => {
        if (items[0]) setOrganizationId(items[0].id);
        else setError("No organisation membership was found.");
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    load(organizationId).catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load programmes."));
  }, [organizationId]);

  useEffect(() => {
    if (!organizationId) return;
    apiGet<MemberOption[]>(`/organizations/${organizationId}/memberships/directory`)
      .then(setMembers)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load organisation members."));
  }, [organizationId]);

  useEffect(() => {
    if (!organizationId || !selectedId) {
      setProjects([]);
      return;
    }
    apiGet<Project[]>(`/organizations/${organizationId}/programmes/${selectedId}/projects`)
      .then(setProjects)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load linked projects."));
  }, [organizationId, selectedId]);

  useEffect(() => {
    if (!organizationId || !selectedId) {
      setGoals([]);
      setMilestones([]);
      setSelectedGoalId("");
      setIndicators([]);
      setDeliverables([]);
      setActivityTimeline([]);
      return;
    }
    apiGet<TimelineEvent[]>(`/organizations/${organizationId}/programmes/${selectedId}/activity-timeline`)
      .then(setActivityTimeline)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load programme activity timeline."));
    Promise.all([
      apiGet<Goal[]>(`/organizations/${organizationId}/programmes/${selectedId}/goals`),
      apiGet<Milestone[]>(`/organizations/${organizationId}/programmes/${selectedId}/milestones`),
      apiGet<IndicatorProgress[]>(`/organizations/${organizationId}/programmes/${selectedId}/indicators`),
      apiGet<Deliverable[]>(`/organizations/${organizationId}/programmes/${selectedId}/deliverables`),
    ]).then(([goalRows, milestoneRows, indicatorRows, deliverableRows]) => {
      setGoals(goalRows);
      setMilestones(milestoneRows);
      setIndicators(indicatorRows);
      setDeliverables(deliverableRows);
      setSelectedGoalId((current) => goalRows.some((goal) => goal.id === current) ? current : goalRows[0]?.id ?? "");
    }).catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load programme plan."));
  }, [organizationId, selectedId]);

  async function refreshPlan() {
    if (!organizationId || !selectedId) return;
    const [goalRows, milestoneRows, indicatorRows, deliverableRows] = await Promise.all([
      apiGet<Goal[]>(`/organizations/${organizationId}/programmes/${selectedId}/goals`),
      apiGet<Milestone[]>(`/organizations/${organizationId}/programmes/${selectedId}/milestones`),
      apiGet<IndicatorProgress[]>(`/organizations/${organizationId}/programmes/${selectedId}/indicators`),
      apiGet<Deliverable[]>(`/organizations/${organizationId}/programmes/${selectedId}/deliverables`),
    ]);
    setGoals(goalRows);
    setMilestones(milestoneRows);
    setIndicators(indicatorRows);
    setDeliverables(deliverableRows);
    setSelectedGoalId((current) => goalRows.some((goal) => goal.id === current) ? current : goalRows[0]?.id ?? "");
  }

  async function createGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/goals`, {
        title: data.get("goal_title"), description: data.get("goal_description") || null,
        target_date: data.get("goal_target_date") || null,
      });
      form.reset();
      await refreshPlan();
      setNotice("Programme goal created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create goal.");
    } finally { setBusy(false); }
  }

  async function createMilestone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/goals/${selectedGoalId}/milestones`, {
        title: data.get("milestone_title"), description: data.get("milestone_description") || null,
        due_date: data.get("milestone_due_date") || null,
      });
      form.reset();
      await refreshPlan();
      setNotice("Milestone created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create milestone.");
    } finally { setBusy(false); }
  }

  async function updatePlanStatus(kind: "goals" | "milestones", itemId: string, status: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/${kind}/${itemId}/status`, { status });
      await refreshPlan();
      setNotice(kind === "goals" ? "Goal status updated." : "Milestone status updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update programme plan.");
    } finally { setBusy(false); }
  }

  async function createIndicator(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/indicators`, {
        key: data.get("indicator_key"), title: data.get("indicator_title"),
        description: data.get("indicator_description") || null, unit: data.get("indicator_unit"),
        direction: data.get("indicator_direction"),
        baseline_value: data.get("baseline_value") === "" ? null : Number(data.get("baseline_value")),
        target_value: data.get("target_value") === "" ? null : Number(data.get("target_value")),
      });
      form.reset();
      await refreshPlan();
      setNotice("Programme indicator created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create indicator.");
    } finally { setBusy(false); }
  }

  async function recordMeasurement(event: FormEvent<HTMLFormElement>, indicatorId: string) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/indicators/${indicatorId}/measurements`, {
        period_start: data.get("period_start"), period_end: data.get("period_end"),
        value: Number(data.get("measurement_value")), notes: data.get("measurement_notes") || null,
      });
      form.reset();
      await refreshPlan();
      setNotice("Indicator measurement recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record measurement.");
    } finally { setBusy(false); }
  }

  async function createDeliverable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/deliverables`, {
        title: data.get("deliverable_title"), description: data.get("deliverable_description") || null,
        due_date: data.get("deliverable_due_date") || null,
        project_id: data.get("deliverable_project_id") || null,
        assigned_to: data.get("deliverable_assigned_to") || null,
      });
      form.reset();
      await refreshPlan();
      setNotice("Deliverable created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create deliverable.");
    } finally { setBusy(false); }
  }

  async function toggleDeliverableHistory(deliverableId: string) {
    const opening = !historyOpen[deliverableId];
    setHistoryOpen((current) => ({ ...current, [deliverableId]: opening }));
    if (!opening || deliverableEvents[deliverableId]) return;
    setHistoryLoading((current) => ({ ...current, [deliverableId]: true }));
    try {
      const rows = await apiGet<DeliverableEvent[]>(
        `/organizations/${organizationId}/programmes/${selectedId}/deliverables/${deliverableId}/events`,
      );
      setDeliverableEvents((current) => ({ ...current, [deliverableId]: rows }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load deliverable audit history.");
      setHistoryOpen((current) => ({ ...current, [deliverableId]: false }));
    } finally {
      setHistoryLoading((current) => ({ ...current, [deliverableId]: false }));
    }
  }

  async function submitEvidence(event: FormEvent<HTMLFormElement>, deliverableId: string) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/deliverables/${deliverableId}/submit`, {
        evidence_url: data.get("evidence_url"), note: data.get("evidence_note") || null,
      });
      form.reset();
      await refreshPlan();
      setNotice("Evidence submitted for review.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit deliverable evidence.");
    } finally { setBusy(false); }
  }

  async function reviewDeliverable(deliverableId: string, decision: "accepted" | "revisions_required") {
    const note = window.prompt("Review note (optional):") ?? "";
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/deliverables/${deliverableId}/decision`, {
        decision, note: note || null,
      });
      await refreshPlan();
      setNotice(decision === "accepted" ? "Deliverable accepted." : "Revisions requested.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to review deliverable.");
    } finally { setBusy(false); }
  }

  async function run(label: string, work: () => Promise<unknown>): Promise<boolean> {
    setBusy(true); setError(""); setNotice("");
    try {
      await work();
      await load(organizationId);
      setNotice(label);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The programme operation failed.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const created = await run("Programme draft created.", () => apiPost(`/organizations/${organizationId}/programmes`, {
      title: data.get("title"), slug: data.get("slug"), summary: data.get("summary") || null,
      start_date: data.get("start_date") || null, end_date: data.get("end_date") || null,
    }));
    if (created) form.reset();
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run("Programme details saved.", () => apiPatch(
      `/organizations/${organizationId}/programmes/${selectedId}`,
      {
        title: data.get("title"), slug: data.get("slug"),
        summary: data.get("summary") || null,
        start_date: data.get("start_date") || null,
        end_date: data.get("end_date") || null,
      },
    ));
  }

  const selected = programmes.find((item) => item.id === selectedId) ?? null;
  const programmeCounts = {
    total: programmes.length,
    active: programmes.filter((item) => item.status === "active").length,
    planned: programmes.filter((item) => item.status === "planned").length,
    completed: programmes.filter((item) => item.status === "completed").length,
  };
  if (loading) return <main className="workspace-shell"><p>Loading programme administration…</p></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/workspace">NextGen For Earth</Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">PROGRAMME GOVERNANCE</p>
        <h1 className="workspace-title">Programme <em>management.</em></h1>
        <p className="workspace-muted">Create programmes, maintain catalogue metadata, control lifecycle transitions and inspect linked projects.</p>
        <div className="staff-actions" aria-label="Programme workspace actions">
          <button className="secondary-action" disabled={busy || !organizationId} onClick={() => {
            setBusy(true); setError(""); setNotice("");
            load(organizationId).then(() => setNotice("Programme records refreshed."))
              .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to refresh programmes."))
              .finally(() => setBusy(false));
          }}>{busy ? "Working…" : "Refresh records"}</button>
        </div>
        <div className="staff-grid" aria-label="Programme portfolio summary">
          <article className="staff-card"><small>Total programmes</small><strong>{programmeCounts.total}</strong></article>
          <article className="staff-card"><small>Active</small><strong>{programmeCounts.active}</strong></article>
          <article className="staff-card"><small>Planned</small><strong>{programmeCounts.planned}</strong></article>
          <article className="staff-card"><small>Completed</small><strong>{programmeCounts.completed}</strong></article>
        </div>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        <div className="staff-grid">
          <section className="staff-card">
            <h2>Create a programme</h2>
            <form onSubmit={create}>
              <label>Programme title<input name="title" minLength={2} maxLength={240} required /></label>
              <label>Public URL slug<input name="slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" maxLength={140} required /></label>
              <label>Summary<textarea name="summary" maxLength={10000} /></label>
              <label>Start date<input name="start_date" type="date" /></label>
              <label>End date<input name="end_date" type="date" /></label>
              <button className="primary-action" disabled={busy}>Create draft programme</button>
            </form>
          </section>
          <section className="staff-card">
            <h2>Programme records</h2>
            {programmes.length === 0 ? <p className="workspace-muted">No programmes have been created yet.</p> : (
              <label>Select programme
                <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
                  {programmes.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.status}</option>)}
                </select>
              </label>
            )}
            {selected && (
              <>
                <form onSubmit={save}>
                  <label>Title<input name="title" defaultValue={selected.title} key={selected.id + selected.title} required minLength={2} maxLength={240} /></label>
                  <label>Slug<input name="slug" defaultValue={selected.slug} key={selected.id + selected.slug} required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" /></label>
                  <label>Summary<textarea name="summary" defaultValue={selected.summary ?? ""} key={selected.id + (selected.summary ?? "")} maxLength={10000} /></label>
                  <label>Start date<input name="start_date" type="date" defaultValue={selected.start_date ?? ""} key={selected.id + (selected.start_date ?? "")} /></label>
                  <label>End date<input name="end_date" type="date" defaultValue={selected.end_date ?? ""} key={selected.id + (selected.end_date ?? "")} /></label>
                  <button className="primary-action" disabled={busy}>Save programme details</button>
                </form>
                <div className="staff-record">
                  <strong>Lifecycle: {selected.status}</strong>
                  <label>Move to<select id="next-status" defaultValue="" key={selected.id + selected.status}>
                    <option value="" disabled>Choose an allowed transition</option>
                    {(transitions[selected.status] ?? []).map((status) => <option key={status} value={status}>{status}</option>)}
                  </select></label>
                  <button className="secondary-action" disabled={busy || transitions[selected.status]?.length === 0} onClick={() => {
                    const control = document.getElementById("next-status") as HTMLSelectElement | null;
                    if (control?.value) void run("Programme lifecycle updated.", () =>
                      apiPost(`/organizations/${organizationId}/programmes/${selected.id}/status`, { status: control.value }));
                  }}>Apply lifecycle transition</button>
                </div>
                <section className="staff-record">
                  <h2>Goals and milestones</h2>
                  <p className="workspace-muted">Define programme outcomes, break them into milestones and record progress through controlled lifecycle transitions.</p>
                  <form onSubmit={createGoal}>
                    <label>Goal title<input name="goal_title" minLength={2} maxLength={240} required /></label>
                    <label>Description<textarea name="goal_description" maxLength={10000} /></label>
                    <label>Target date<input name="goal_target_date" type="date" /></label>
                    <button className="primary-action" disabled={busy}>Add programme goal</button>
                  </form>
                  {goals.length > 0 && (
                    <>
                      <label>Goal for new milestone<select value={selectedGoalId} onChange={(event) => setSelectedGoalId(event.target.value)}>
                        {goals.map((goal) => <option key={goal.id} value={goal.id}>{goal.title} · {goal.status}</option>)}
                      </select></label>
                      <form onSubmit={createMilestone}>
                        <label>Milestone title<input name="milestone_title" minLength={2} maxLength={240} required /></label>
                        <label>Description<textarea name="milestone_description" maxLength={10000} /></label>
                        <label>Due date<input name="milestone_due_date" type="date" /></label>
                        <button className="secondary-action" disabled={busy || !selectedGoalId}>Add milestone</button>
                      </form>
                    </>
                  )}
                  <h3>Programme goals ({goals.length})</h3>
                  {goals.length === 0 ? <p className="workspace-muted">No goals have been defined.</p> : goals.map((goal) => (
                    <article key={goal.id} className="staff-record">
                      <strong>{goal.title}</strong>
                      <small>{goal.status}{goal.target_date ? ` · Target ${goal.target_date}` : ""}</small>
                      {goal.description && <p>{goal.description}</p>}
                      <div className="staff-actions">
                        {goal.status === "planned" && <button className="secondary-action" disabled={busy} onClick={() => void updatePlanStatus("goals", goal.id, "active")}>Start goal</button>}
                        {goal.status === "active" && <button className="secondary-action" disabled={busy} onClick={() => void updatePlanStatus("goals", goal.id, "achieved")}>Mark achieved</button>}
                        {["planned", "active"].includes(goal.status) && <button className="secondary-action" disabled={busy} onClick={() => void updatePlanStatus("goals", goal.id, "cancelled")}>Cancel goal</button>}
                      </div>
                    </article>
                  ))}
                  <h3>Milestones ({milestones.length})</h3>
                  {milestones.length === 0 ? <p className="workspace-muted">No milestones have been added.</p> : milestones.map((milestone) => (
                    <article key={milestone.id} className="staff-record">
                      <strong>{milestone.title}</strong>
                      <small>{goals.find((goal) => goal.id === milestone.goal_id)?.title ?? "Programme goal"} · {milestone.status}{milestone.due_date ? ` · Due ${milestone.due_date}` : ""}</small>
                      {milestone.description && <p>{milestone.description}</p>}
                      <div className="staff-actions">
                        {milestone.status === "planned" && <button className="secondary-action" disabled={busy} onClick={() => void updatePlanStatus("milestones", milestone.id, "in_progress")}>Start</button>}
                        {["planned", "in_progress", "blocked"].includes(milestone.status) && <button className="secondary-action" disabled={busy} onClick={() => void updatePlanStatus("milestones", milestone.id, "cancelled")}>Cancel</button>}
                        {["in_progress", "blocked"].includes(milestone.status) && <button className="secondary-action" disabled={busy} onClick={() => void updatePlanStatus("milestones", milestone.id, "completed")}>Mark completed</button>}
                        {milestone.status === "in_progress" && <button className="secondary-action" disabled={busy} onClick={() => void updatePlanStatus("milestones", milestone.id, "blocked")}>Mark blocked</button>}
                      </div>
                    </article>
                  ))}
                </section>
                <section className="staff-record">
                  <h2>Impact indicators</h2>
                  <form onSubmit={createIndicator}>
                    <label>Indicator key<input name="indicator_key" pattern="[a-z][a-z0-9_]{1,79}" required /></label>
                    <label>Indicator title<input name="indicator_title" minLength={2} maxLength={240} required /></label>
                    <label>Description<textarea name="indicator_description" maxLength={5000} /></label>
                    <label>Unit<input name="indicator_unit" maxLength={40} placeholder="trees, people, hectares…" required /></label>
                    <label>Direction<select name="indicator_direction"><option value="increase">Increase</option><option value="decrease">Decrease</option><option value="monitor">Monitor only</option></select></label>
                    <label>Baseline<input name="baseline_value" type="number" step="any" /></label>
                    <label>Target<input name="target_value" type="number" step="any" /></label>
                    <button className="primary-action" disabled={busy}>Create indicator</button>
                  </form>
                  {indicators.map((entry) => (
                    <article className="staff-record" key={entry.indicator.id}>
                      <strong>{entry.indicator.title}</strong>
                      <small>{entry.indicator.key} · {entry.indicator.direction} · {entry.indicator.unit}</small>
                      <p>{entry.latest_measurement ? `Latest: ${entry.latest_measurement.value} ${entry.indicator.unit} (period ending ${entry.latest_measurement.period_end})` : "No measurement recorded yet"}</p>
                      {entry.progress_percent !== null && <p>Progress against target: {entry.progress_percent}%</p>}
                      <form onSubmit={(event) => void recordMeasurement(event, entry.indicator.id)}>
                        <label>Period start<input name="period_start" type="date" required /></label>
                        <label>Period end<input name="period_end" type="date" required /></label>
                        <label>Measured value<input name="measurement_value" type="number" step="any" required /></label>
                        <label>Notes<textarea name="measurement_notes" maxLength={5000} /></label>
                        <button className="secondary-action" disabled={busy}>Record measurement</button>
                      </form>
                    </article>
                  ))}
                </section>
                <section className="staff-record">
                  <h2>Deliverables and evidence review</h2>
                  <form onSubmit={createDeliverable}>
                    <label>Deliverable title<input name="deliverable_title" minLength={2} maxLength={240} required /></label>
                    <label>Description<textarea name="deliverable_description" maxLength={10000} /></label>
                    <label>Due date<input name="deliverable_due_date" type="date" /></label>
                    <label>Related project
                      <select name="deliverable_project_id" defaultValue="">
                        <option value="">No project link</option>
                        {projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}
                      </select>
                    </label>
                    <label>Assign to active member
                      <select name="deliverable_assigned_to" defaultValue="">
                        <option value="">Unassigned</option>
                        {members.map((member) => <option key={member.user_id} value={member.user_id}>{member.role} · {member.user_id}</option>)}
                      </select>
                    </label>
                    <button className="primary-action" disabled={busy}>Create deliverable</button>
                  </form>
                  {deliverables.length === 0 ? <p className="workspace-muted">No deliverables have been registered.</p> : deliverables.map((item) => (
                    <article className="staff-record" key={item.id}>
                      <strong>{item.title}</strong>
                      <small>{item.status}{item.due_date ? ` · Due ${item.due_date}` : ""}</small>
                      {item.description && <p>{item.description}</p>}
                      <div className="staff-actions">
                        <button className="secondary-action" disabled={historyLoading[item.id]} onClick={() => void toggleDeliverableHistory(item.id)}>
                          {historyLoading[item.id] ? "Loading history…" : historyOpen[item.id] ? "Hide audit history" : "View audit history"}
                        </button>
                      </div>
                      {historyOpen[item.id] && (
                        <div className="staff-record" aria-label={`Audit history for ${item.title}`}>
                          <strong>Deliverable audit trail</strong>
                          {!deliverableEvents[item.id] ? <p className="workspace-muted">Loading events…</p> :
                            deliverableEvents[item.id].length === 0 ? <p className="workspace-muted">No lifecycle events recorded.</p> :
                            deliverableEvents[item.id].map((entry) => (
                              <article key={entry.id}>
                                <strong>{entry.action.replaceAll("_", " ")}</strong>
                                <small>{new Date(entry.created_at).toLocaleString()} · {entry.actor_user_id ? `Actor ${entry.actor_user_id}` : "System"}</small>
                                {typeof entry.details.note === "string" && <p>{entry.details.note}</p>}
                                {typeof entry.details.evidence_url === "string" && <p><a href={entry.details.evidence_url} target="_blank" rel="noreferrer">View evidence submitted in this event</a></p>}
                              </article>
                            ))
                          }
                        </div>
                      )}
                      {item.assigned_to && <small>Assigned to {item.assigned_to}</small>}
                      {item.evidence_url && <p><a href={item.evidence_url} target="_blank" rel="noreferrer">Open submitted evidence</a></p>}
                      {["planned", "in_progress", "revisions_required"].includes(item.status) && (
                        <form onSubmit={(event) => void submitEvidence(event, item.id)}>
                          <label>Evidence URL<input name="evidence_url" type="url" minLength={8} maxLength={1000} placeholder="https://…" required /></label>
                          <label>Submission note<textarea name="evidence_note" maxLength={4000} /></label>
                          <button className="secondary-action" disabled={busy}>Submit evidence</button>
                        </form>
                      )}
                      {item.review_note && <p>Review note: {item.review_note}</p>}
                      {item.status === "submitted" && (
                        <div className="staff-actions">
                          <button className="secondary-action" disabled={busy} onClick={() => void reviewDeliverable(item.id, "accepted")}>Accept evidence</button>
                          <button className="secondary-action" disabled={busy} onClick={() => void reviewDeliverable(item.id, "revisions_required")}>Request revisions</button>
                        </div>
                      )}
                    </article>
                  ))}
                </section>
                <section className="staff-record">
                  <h2>Programme activity timeline</h2>
                  <p className="workspace-muted">One manager-only chronological record of goals, milestones, indicators, assignments, scheduled activities, volunteer allocations and deliverable reviews.</p>
                  {activityTimeline.length === 0 ? <p className="workspace-muted">No programme events have been recorded yet.</p> :
                    activityTimeline.map((entry) => (
                      <article key={entry.id}>
                        <strong>{entry.action.replaceAll("_", " ")} · {entry.entity_type.replaceAll("_", " ")}: {entry.entity_title}</strong>
                        <small>{new Date(entry.created_at).toLocaleString()} · Actor {entry.actor_user_id}</small>
                        {typeof entry.details.from === "string" && typeof entry.details.to === "string" && <p>{entry.details.from} → {entry.details.to}</p>}
                        {typeof entry.details.value === "number" && <p>Recorded value: {entry.details.value}{typeof entry.details.unit === "string" ? " " + entry.details.unit : ""}</p>}
                        {typeof entry.details.user_id === "string" && <p>Volunteer: {entry.details.user_id}</p>}
                        {typeof entry.details.assigned_to === "string" && <p>Assignee: {entry.details.assigned_to}</p>}
                        {typeof entry.details.note === "string" && <p>{entry.details.note}</p>}
                      </article>
                    ))
                  }
                </section>
                <div className="staff-record">
                  <strong>Linked projects ({projects.length})</strong>
                  {projects.length === 0 ? <p className="workspace-muted">No projects are linked to this programme yet. Create projects with this programme selected in the project workflow.</p> : projects.map((project) => (
                    <article key={project.id}>
                      <strong>{project.title}</strong>
                      <small>{project.status} · {project.country_code}{project.county ? ` · ${project.county}` : ""}</small>
                      {project.summary && <p>{project.summary}</p>}
                    </article>
                  ))}
                </div>
                <p><Link href={`/programmes/${selected.slug}`}>View public programme page →</Link></p>
              </>
            )}
          </section>
        </div>
        <p><Link href="/workspace">Return to workspace</Link></p>
      </section>
    </main>
  );
}
