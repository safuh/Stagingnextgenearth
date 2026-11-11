"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, clearSession, hasSession } from "@/lib/api";

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
