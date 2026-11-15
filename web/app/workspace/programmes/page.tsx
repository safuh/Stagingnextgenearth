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
  const [goals, setGoals] = useState<Goal[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [selectedGoalId, setSelectedGoalId] = useState("");
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
      return;
    }
    Promise.all([
      apiGet<Goal[]>(`/organizations/${organizationId}/programmes/${selectedId}/goals`),
      apiGet<Milestone[]>(`/organizations/${organizationId}/programmes/${selectedId}/milestones`),
    ]).then(([goalRows, milestoneRows]) => {
      setGoals(goalRows);
      setMilestones(milestoneRows);
      setSelectedGoalId((current) => goalRows.some((goal) => goal.id === current) ? current : goalRows[0]?.id ?? "");
    }).catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load programme plan."));
  }, [organizationId, selectedId]);

  async function refreshPlan() {
    if (!organizationId || !selectedId) return;
    const [goalRows, milestoneRows] = await Promise.all([
      apiGet<Goal[]>(`/organizations/${organizationId}/programmes/${selectedId}/goals`),
      apiGet<Milestone[]>(`/organizations/${organizationId}/programmes/${selectedId}/milestones`),
    ]);
    setGoals(goalRows);
    setMilestones(milestoneRows);
    setSelectedGoalId((current) => goalRows.some((goal) => goal.id === current) ? current : goalRows[0]?.id ?? "");
  }

  async function createGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/goals`, {
        title: data.get("goal_title"), description: data.get("goal_description") || null,
        target_date: data.get("goal_target_date") || null,
      });
      event.currentTarget.reset();
      await refreshPlan();
      setNotice("Programme goal created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create goal.");
    } finally { setBusy(false); }
  }

  async function createMilestone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/programmes/${selectedId}/goals/${selectedGoalId}/milestones`, {
        title: data.get("milestone_title"), description: data.get("milestone_description") || null,
        due_date: data.get("milestone_due_date") || null,
      });
      event.currentTarget.reset();
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

  async function run(label: string, work: () => Promise<unknown>) {
    setBusy(true); setError(""); setNotice("");
    try {
      await work();
      await load(organizationId);
      setNotice(label);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The programme operation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run("Programme draft created.", () => apiPost(`/organizations/${organizationId}/programmes`, {
      title: data.get("title"), slug: data.get("slug"), summary: data.get("summary") || null,
      start_date: data.get("start_date") || null, end_date: data.get("end_date") || null,
    }));
    event.currentTarget.reset();
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
