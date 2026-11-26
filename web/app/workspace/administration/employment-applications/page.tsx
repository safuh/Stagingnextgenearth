"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, apiPost, clearSession } from "@/lib/api";

type Organization = { id: string; name: string };
type Application = {
  id: string; organization_id: string; user_id: string; full_name: string;
  desired_position: string; qualifications: string; experience_summary: string | null;
  status: string; review_note: string | null; applicant_identifier: string | null;
  reviewed_by: string | null; reviewed_at: string | null;
};

export default function EmploymentApplicationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [applications, setApplications] = useState<Application[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(id: string) {
    const rows = await apiGet<Application[]>(`/organizations/${id}/employment-applications`);
    setApplications(rows);
  }

  useEffect(() => {
    apiGet<Organization[]>("/organizations")
      .then((items) => {
        setOrganizations(items);
        if (items[0]) setOrganizationId(items[0].id);
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    load(organizationId).catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load applications."));
  }, [organizationId]);

  async function decide(item: Application, decision: "approved" | "rejected") {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(
        `/organizations/${organizationId}/employment-applications/${item.id}/decision`,
        { decision, note: notes[item.id]?.trim() || null },
      );
      await load(organizationId);
      setNotice(decision === "approved"
        ? "Application approved. Employee access is active and a private directory profile was created for review."
        : "Application rejected. No organisation membership was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to process application.");
    } finally {
      setBusy(false);
    }
  }

  const pending = applications.filter((item) => item.status === "pending");

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/workspace">NextGen For Earth</Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">PEOPLE & ONBOARDING</p>
        <h1 className="workspace-title">Employment <em>applications.</em></h1>
        <p className="workspace-muted">Review candidate submissions. Approval creates an active employee membership and a private, unverified directory profile. Public visibility remains a separate administrator decision.</p>
        <p><Link className="secondary-action" href="/workspace/administration">← Administration</Link></p>
        {organizations.length > 1 && <label>Organisation<select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>{organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label>}
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        <section className="staff-card admin-member-section">
          <h2>Pending applications ({pending.length})</h2>
          {pending.length === 0 && <p className="workspace-muted">There are no pending employment applications.</p>}
          {pending.map((item) => (
            <article className="admin-member-row" key={item.id}>
              <div className="admin-member-meta">
                <strong>{item.full_name}</strong>
                <span>{item.desired_position} · {item.applicant_identifier ?? item.user_id}</span>
                <p>{item.qualifications}</p>
                {item.experience_summary && <p>{item.experience_summary}</p>}
                <label>Review note (optional)<textarea rows={2} maxLength={2000} value={notes[item.id] ?? ""} onChange={(event) => setNotes((old) => ({ ...old, [item.id]: event.target.value }))} /></label>
              </div>
              <div className="admin-member-actions">
                <button className="primary-action" disabled={busy} onClick={() => void decide(item, "approved")}>Approve & onboard</button>
                <button className="secondary-action" disabled={busy} onClick={() => void decide(item, "rejected")}>Reject</button>
              </div>
            </article>
          ))}
        </section>
        <section className="staff-card admin-member-section">
          <h2>Application history</h2>
          {applications.filter((item) => item.status !== "pending").map((item) => (
            <article className="admin-member-row" key={item.id}>
              <div className="admin-member-meta">
                <strong>{item.full_name}</strong>
                <span>{item.desired_position} · {item.status}</span>
                {item.reviewed_at && <small>Reviewed {new Date(item.reviewed_at).toLocaleString()}{item.reviewed_by ? ` · Reviewer ${item.reviewed_by}` : ""}</small>}
                {item.review_note && <p>{item.review_note}</p>}
              </div>
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}
