"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { apiGet, apiPost, clearSession, hasSession } from "@/lib/api";

interface Organization {
  id: string;
  name: string;
  country_code: string;
}
interface Membership {
  role: "admin" | "programme_manager" | "researcher" | "youth_volunteer" | "institutional_partner";
  status: string;
}
interface Study {
  id: string;
  title: string;
  abstract: string | null;
  study_type: string | null;
  status: string;
  lead_researcher_id: string;
  ethics_reference: string | null;
}
interface Dataset {
  id: string;
  study_id: string | null;
  title: string;
  description: string | null;
  version: string;
  format: string;
  source: string;
  license: string | null;
  access_classification: string;
  status: string;
  collection_start: string | null;
  collection_end: string | null;
  owner_user_id: string;
}

const RESEARCH_ROLES = ["admin", "programme_manager", "researcher", "institutional_partner"];

export default function ResearchWorkspacePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [studies, setStudies] = useState<Study[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hasSession()) {
      setError("Your sign-in session is unavailable. Please sign in again.");
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
    let active = true;
    setError("");
    setMembership(null);
    setStudies([]);
    setDatasets([]);
    Promise.all([
      apiGet<Membership>(`/organizations/${organizationId}/memberships/me`),
      apiGet<Study[]>(`/organizations/${organizationId}/research-studies`),
      apiGet<Dataset[]>(`/organizations/${organizationId}/research-datasets?limit=200`),
    ]).then(([member, studyItems, datasetItems]) => {
      if (!active) return;
      if (!RESEARCH_ROLES.includes(member.role) || member.status !== "active") {
        setError("Research workspace access is not available for this membership.");
        return;
      }
      setMembership(member);
      setStudies(studyItems);
      setDatasets(datasetItems);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load research workspace.");
    });
    return () => { active = false; };
  }, [organizationId]);

  async function createStudy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const created = await apiPost<Study>(`/organizations/${organizationId}/research-studies`, {
        title: String(values.get("title") || ""),
        abstract: String(values.get("abstract") || "") || null,
        study_type: String(values.get("study_type") || "") || null,
        ethics_reference: String(values.get("ethics_reference") || "") || null,
      });
      setStudies((current) => [created, ...current]);
      form.reset();
      setNotice("Study registered as a concept. Add the required governance and ethics records before field activity.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create the study.");
    } finally {
      setSaving(false);
    }
  }

  async function createDataset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const studyId = String(values.get("study_id") || "");
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const created = await apiPost<Dataset>(`/organizations/${organizationId}/research-datasets`, {
        title: String(values.get("title") || ""),
        description: String(values.get("description") || "") || null,
        version: String(values.get("version") || "1.0"),
        format: String(values.get("format") || ""),
        source: String(values.get("source") || ""),
        license: String(values.get("license") || "") || null,
        access_classification: String(values.get("access_classification") || "organization"),
        study_id: studyId || null,
      });
      setDatasets((current) => [created, ...current]);
      form.reset();
      setNotice("Dataset metadata registered as a draft. Submit it for independent review before treating it as approved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to register the dataset.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading research workspace…</p></main>;

  const count = (items: Dataset[], status: string) => items.filter((item) => item.status === status).length;
  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">RESEARCH & CLIMATE INTELLIGENCE</p>
        <h1 className="workspace-title">Research workspace.<br /><em>Evidence, with provenance.</em></h1>
        <p className="workspace-intro">Manage study discovery and inspect the governance state of organisation datasets. File contents remain behind separate, authorised access workflows.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {organizations.length === 0 && !error ? (
          <div className="workspace-empty"><h2>No organisation access yet</h2><p>Ask an organisation administrator to invite your account.</p></div>
        ) : (
          <>
            <label className="org-label" htmlFor="research-organization">Active organisation</label>
            <select id="research-organization" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
              {organizations.map((org) => <option value={org.id} key={org.id}>{org.name} · {org.country_code}</option>)}
            </select>
            {membership && (
              <>
                <section className="role-workspace">
                  <div><span className="eyebrow">YOUR ACCESS</span><h2>{membership.role.replace(/_/g, " ")}</h2><p>All study and dataset access is re-authorised by the API for this organisation.</p></div>
                  <div className="role-workspace-links"><Link href="/workspace">Back to organisation workspace →</Link></div>
                </section>
                <div className="research-metrics" aria-label="Research dataset summary">
                  <article><span>Studies</span><strong>{studies.length}</strong></article>
                  <article><span>Datasets</span><strong>{datasets.length}</strong></article>
                  <article><span>Awaiting review</span><strong>{count(datasets, "submitted")}</strong></article>
                  <article><span>Approved</span><strong>{count(datasets, "approved")}</strong></article>
                </div>
                <div className="staff-grid research-authoring-grid">
                  <section className="staff-card">
                    <p className="eyebrow">RESEARCH DESIGN</p>
                    <h2>Register a study</h2>
                    <p>New studies begin in concept status and are owned by the creating researcher.</p>
                    <form onSubmit={createStudy}>
                      <label>Study title<input name="title" minLength={3} maxLength={240} required /></label>
                      <label>Study type<input name="study_type" maxLength={80} placeholder="e.g. observational, field study" /></label>
                      <label>Abstract<textarea name="abstract" rows={4} maxLength={20000} /></label>
                      <label>Ethics reference<input name="ethics_reference" maxLength={160} /></label>
                      <button className="primary-action" disabled={saving}>{saving ? "Saving…" : "Create study"}</button>
                    </form>
                  </section>
                  <section className="staff-card">
                    <p className="eyebrow">DATA GOVERNANCE</p>
                    <h2>Register dataset metadata</h2>
                    <p>Registration creates a draft only. File uploads and access grants use separate controlled workflows.</p>
                    <form onSubmit={createDataset}>
                      <label>Dataset title<input name="title" minLength={3} maxLength={240} required /></label>
                      <label>Linked study<select name="study_id" defaultValue=""><option value="">No linked study</option>{studies.map((study) => <option value={study.id} key={study.id}>{study.title}</option>)}</select></label>
                      <label>Description<textarea name="description" rows={3} maxLength={20000} /></label>
                      <div className="research-form-pair">
                        <label>Version<input name="version" defaultValue="1.0" maxLength={40} required /></label>
                        <label>Format<input name="format" placeholder="CSV, GeoTIFF…" minLength={2} maxLength={40} required /></label>
                      </div>
                      <label>Source<input name="source" minLength={2} maxLength={200} required /></label>
                      <div className="research-form-pair">
                        <label>Licence<input name="license" maxLength={120} /></label>
                        <label>Classification<select name="access_classification" defaultValue="organization"><option value="organization">Organisation</option><option value="restricted">Restricted</option><option value="public">Public</option></select></label>
                      </div>
                      <button className="primary-action" disabled={saving}>{saving ? "Saving…" : "Register draft dataset"}</button>
                    </form>
                  </section>
                </div>
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">STUDY REGISTRY</p><h2>Research studies</h2></div><span>{studies.length} records</span></div>
                  {studies.length === 0 ? <p className="workspace-muted">No studies are registered in this organisation yet.</p> : (
                    <div className="research-record-grid">{studies.map((study) => (
                      <article className="research-record" key={study.id}>
                        <div className="research-record-top"><span className="status-chip">{study.status.replace(/_/g, " ")}</span>{study.study_type && <span>{study.study_type}</span>}</div>
                        <h3>{study.title}</h3>
                        <p>{study.abstract || "No study abstract supplied."}</p>
                        <dl><div><dt>Lead researcher</dt><dd>{study.lead_researcher_id}</dd></div><div><dt>Ethics reference</dt><dd>{study.ethics_reference || "Not recorded"}</dd></div></dl>
                      </article>
                    ))}</div>
                  )}
                </section>
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">DATA GOVERNANCE</p><h2>Dataset registry</h2></div><span>{datasets.length} records</span></div>
                  {datasets.length === 0 ? <p className="workspace-muted">No datasets are registered in this organisation yet.</p> : (
                    <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Dataset</th><th>Version</th><th>Format</th><th>Classification</th><th>Status</th><th>Collection period</th></tr></thead>
                      <tbody>{datasets.map((dataset) => (
                        <tr key={dataset.id}><td><strong>{dataset.title}</strong><small>{dataset.source}</small>{dataset.license && <small>Licence: {dataset.license}</small>}</td><td>{dataset.version}</td><td>{dataset.format.toUpperCase()}</td><td>{dataset.access_classification}</td><td><span className="status-chip">{dataset.status.replace(/_/g, " ")}</span></td><td>{dataset.collection_start || "—"} – {dataset.collection_end || "—"}</td></tr>
                      ))}</tbody>
                    </table></div>
                  )}
                  <p className="workspace-muted">This registry displays metadata only. It does not expose object-storage keys, file bytes, or download URLs.</p>
                </section>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}
