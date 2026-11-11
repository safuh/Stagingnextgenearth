"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, clearSession, hasSession } from "@/lib/api";

interface Organization {
  id: string;
  name: string;
  slug: string;
  country_code: string;
}
interface Programme {
  id: string;
  title: string;
  summary: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
}
interface Course {
  id: string;
  title: string;
  description: string;
  category: string | null;
  delivery_mode: string;
  status: string;
}
type Panel = "overview" | "programmes" | "learning";

export default function WorkspacePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [panel, setPanel] = useState<Panel>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hasSession()) {
      setError("Your sign-in session is not available. Please sign in again.");
      setLoading(false);
      return;
    }
    apiGet<Organization[]>("/organizations")
      .then((items) => {
        setOrganizations(items);
        if (items[0]) setOrganizationId(items[0].id);
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    setError("");
    Promise.all([
      apiGet<Programme[]>(`/organizations/${organizationId}/programmes`),
      apiGet<Course[]>(`/organizations/${organizationId}/learning/courses`),
    ]).then(([programmeItems, courseItems]) => {
      setProgrammes(programmeItems);
      setCourses(courseItems);
    }).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "Unable to load workspace data.");
    });
  }, [organizationId]);

  if (loading) return <main className="workspace-shell"><p>Loading your workspace…</p></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">MEMBER WORKSPACE</p>
        <h1 className="workspace-title">Your organisation.<br /><em>Your impact.</em></h1>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {organizations.length === 0 && !error ? (
          <div className="workspace-empty"><h2>No organisation access yet</h2><p>Ask your organisation administrator to invite your account to a workspace.</p></div>
        ) : (
          <>
            <label className="org-label" htmlFor="organization">Active organisation</label>
            <select id="organization" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
              {organizations.map((org) => <option value={org.id} key={org.id}>{org.name} · {org.country_code}</option>)}
            </select>
            <nav className="workspace-tabs" aria-label="Workspace sections">
              {(["overview", "programmes", "learning"] as Panel[]).map((item) => (
                <button key={item} className={panel === item ? "active" : ""} onClick={() => setPanel(item)}>{item}</button>
              ))}
            </nav>
            {panel === "overview" && (
              <div className="workspace-stats">
                <article><span>PROGRAMMES</span><strong>{programmes.length}</strong><p>Organisation programmes</p></article>
                <article><span>COURSES</span><strong>{courses.length}</strong><p>Published learning courses</p></article>
                <article><span>COUNTRY</span><strong>{organizations.find((org) => org.id === organizationId)?.country_code ?? "—"}</strong><p>Organisation registration</p></article>
              </div>
            )}
            {panel === "programmes" && (
              <section className="workspace-list"><h2>Programmes</h2>
                {programmes.length === 0 ? <p className="workspace-muted">No programmes are available in this organisation yet.</p> : programmes.map((item) => (
                  <article className="workspace-item" key={item.id}><div><h3>{item.title}</h3><p>{item.summary || "No programme summary provided."}</p></div><span className="status-pill">{item.status}</span></article>
                ))}
              </section>
            )}
            {panel === "learning" && (
              <section className="workspace-list"><h2>Learning programmes</h2>
                {courses.length === 0 ? <p className="workspace-muted">No published courses are available yet.</p> : courses.map((item) => (
                  <article className="workspace-item" key={item.id}><div><h3>{item.title}</h3><p>{item.description}</p><small>{item.category || "General"} · {item.delivery_mode.replace("_", " ")}</small></div><span className="status-pill">{item.status}</span></article>
                ))}
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}
