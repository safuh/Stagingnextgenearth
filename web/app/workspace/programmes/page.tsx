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
