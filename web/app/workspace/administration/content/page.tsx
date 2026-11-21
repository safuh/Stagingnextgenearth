"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiGet, apiPatch, apiPost, clearSession } from "@/lib/api";

interface Organization { id: string; name: string }
interface Membership { role: string; roles: string[]; user_id: string }
interface ContentEntry {
  id: string;
  content_type: string;
  slug: string;
  title: string;
  summary: string | null;
  body: string | null;
  metadata_json: Record<string, unknown>;
  publication_state: "draft" | "review" | "approved" | "published" | "archived";
  source_url: string | null;
  published_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_by: string;
}

const states = ["all", "review", "approved", "draft", "published", "archived"] as const;
type StateFilter = (typeof states)[number];

export default function ContentReviewPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [entries, setEntries] = useState<ContentEntry[]>([]);
  const [filter, setFilter] = useState<StateFilter>("review");
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async (id: string) => {
    const [mine, rows] = await Promise.all([
      apiGet<Membership>(`/organizations/${id}/memberships/me`),
      apiGet<ContentEntry[]>(`/organizations/${id}/content`),
    ]);
    setMembership(mine);
    setEntries(rows);
  }, []);

  useEffect(() => {
    apiGet<Organization[]>("/organizations")
      .then((items) => {
        setOrganizations(items);
        if (items[0]) setOrganizationId(items[0].id);
        else setError("No active organisation membership was found.");
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    let active = true;
    setError("");
    load(organizationId).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load content review records.");
    });
    return () => { active = false; };
  }, [organizationId, load]);

  async function transition(entry: ContentEntry, state: ContentEntry["publication_state"]) {
    setBusyId(entry.id); setError(""); setNotice("");
    try {
      await apiPatch(`/organizations/${organizationId}/content/${entry.id}`, { publication_state: state });
      await load(organizationId);
      setNotice(`“${entry.title}” moved to ${state}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The moderation action failed.");
    } finally {
      setBusyId("");
    }
  }

  async function saveEdits(event: FormEvent<HTMLFormElement>, entry: ContentEntry) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusyId(entry.id); setError(""); setNotice("");
    try {
      await apiPatch(`/organizations/${organizationId}/content/${entry.id}`, {
        title: String(data.get("title") ?? "").trim(),
        summary: String(data.get("summary") ?? "").trim() || null,
        body: String(data.get("body") ?? "").trim() || null,
      });
      await load(organizationId);
      setNotice("Content saved as draft. Changes to reviewed or published content require a fresh review.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save content.");
    } finally {
      setBusyId("");
    }
  }

  const visible = entries.filter((entry) => filter === "all" || entry.publication_state === filter);
  const assignedRoles = membership?.roles ?? [membership?.role ?? ""];
  const canReview = assignedRoles.some((role) => ["admin", "founder", "executive"].includes(role));
  const canContribute = assignedRoles.some((role) => ["admin", "founder", "executive", "employee", "researcher"].includes(role));

  async function createDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setCreating(true); setError(""); setNotice("");
    try {
      const entry = await apiPost<ContentEntry>(`/organizations/${organizationId}/content`, {
        content_type: String(data.get("content_type") ?? "page"),
        slug: String(data.get("slug") ?? "").trim(),
        title: String(data.get("title") ?? "").trim(),
        summary: String(data.get("summary") ?? "").trim() || null,
        body: String(data.get("body") ?? "").trim() || null,
      });
      await load(organizationId);
      form.reset();
      setNotice(`“${entry.title}” saved as a draft. Submit it for review when it is ready.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create content draft.");
    } finally {
      setCreating(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading CMS review queue…</p></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/workspace"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">PUBLIC WEBSITE · CONTENT GOVERNANCE</p>
        <h1 className="workspace-title">CMS review <em>queue.</em></h1>
        <p className="workspace-muted">Review imported and newly authored website content before it becomes public. Approval and publication are separate, audited actions.</p>
        <p className="workspace-muted">Review permissions are intentionally limited to administrators, founders and executives. An employee account can contribute content but cannot approve or publish it. The content author also cannot approve their own submission; invite a separate authorised reviewer.</p>
        <p><Link className="secondary-action" href="/workspace/administration">← Administration</Link></p>
        {organizations.length > 1 && <label className="admin-org-picker">Organisation<select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>{organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label>}
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {!canReview && !canContribute ? <section className="staff-card"><h2>Content workspace access required</h2><p>Your organisation membership does not include a content contributor or reviewer role.</p></section> : !canReview ? (
          <section className="staff-card admin-member-section">
            <p className="eyebrow">CONTENT CONTRIBUTOR WORKSPACE</p>
            <h2>Create a website draft</h2>
            <p className="workspace-muted">Your drafts are private to your account and organisation reviewers. Submitting for review does not publish content; a different authorised reviewer must approve it before an administrator publishes it.</p>
            <form className="content-review-detail" onSubmit={(event) => void createDraft(event)}>
              <label>Content type<select name="content_type" defaultValue="page"><option value="page">Page</option><option value="programme">Programme</option><option value="training_track">Training track</option><option value="initiative">Initiative</option><option value="research_area">Research area</option><option value="impact_metric">Impact metric</option><option value="publication">Publication</option></select></label>
              <label>URL slug<input name="slug" minLength={2} maxLength={160} pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="community-climate-research" required /></label>
              <label>Title<input name="title" minLength={2} maxLength={240} required /></label>
              <label>Summary<textarea name="summary" rows={3} maxLength={5000} /></label>
              <label>Body<textarea name="body" rows={8} maxLength={30000} /></label>
              <button className="primary-action" disabled={creating}>{creating ? "Saving…" : "Save draft"}</button>
            </form>
            <div className="section-heading"><h2>Your submissions</h2><span>{entries.length} records</span></div>
            {entries.length === 0 ? <p className="workspace-muted">You have not created any content drafts yet.</p> : entries.map((entry) => (
              <article className="admin-member-row" key={entry.id}>
                <div className="admin-member-meta"><strong>{entry.title}</strong><span>{entry.content_type.replaceAll("_", " ")} · {entry.slug}</span><span>Status: {entry.publication_state}</span></div>
              </article>
            ))}
          </section>
        ) : (
          <>
            {canContribute && (
              <section className="staff-card admin-member-section">
                <p className="eyebrow">CONTENT AUTHORING</p>
                <h2>Create a website draft</h2>
                <p className="workspace-muted">Drafts remain private until a separate authorised reviewer approves them and an administrator publishes them.</p>
                <form className="content-review-detail" onSubmit={(event) => void createDraft(event)}>
                  <label>Content type<select name="content_type" defaultValue="page"><option value="page">Page</option><option value="programme">Programme</option><option value="training_track">Training track</option><option value="initiative">Initiative</option><option value="research_area">Research area</option><option value="impact_metric">Impact metric</option><option value="publication">Publication</option></select></label>
                  <label>URL slug<input name="slug" minLength={2} maxLength={160} pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="community-climate-research" required /></label>
                  <label>Title<input name="title" minLength={2} maxLength={240} required /></label>
                  <label>Summary<textarea name="summary" rows={3} maxLength={5000} /></label>
                  <label>Body<textarea name="body" rows={8} maxLength={30000} /></label>
                  <button className="primary-action" disabled={creating}>{creating ? "Saving…" : "Save draft"}</button>
                </form>
              </section>
            )}
            <div className="workspace-stats admin-stats">
              <article><span>AWAITING REVIEW</span><strong>{entries.filter((item) => item.publication_state === "review").length}</strong><p>Requires an authorised reviewer</p></article>
              <article><span>APPROVED</span><strong>{entries.filter((item) => item.publication_state === "approved").length}</strong><p>Ready for publication</p></article>
              <article><span>PUBLISHED</span><strong>{entries.filter((item) => item.publication_state === "published").length}</strong><p>Visible on the public site</p></article>
            </div>
            <section className="staff-card admin-member-section">
              <div className="section-heading"><div><p className="eyebrow">MODERATION WORKFLOW</p><h2>Content records</h2></div><span>{visible.length} records</span></div>
              <label>Filter by status<select value={filter} onChange={(event) => setFilter(event.target.value as StateFilter)}>{states.map((state) => <option key={state} value={state}>{state === "all" ? "All statuses" : state}</option>)}</select></label>
              {visible.length === 0 ? <p className="workspace-muted">No content records match this status.</p> : visible.map((entry) => {
                const ownEntry = entry.created_by === membership?.user_id;
                const busy = busyId === entry.id;
                return (
                  <article className="admin-member-row" key={entry.id}>
                    <div className="admin-member-meta">
                      <strong>{entry.title}</strong>
                      <span>{entry.content_type.replaceAll("_", " ")} · {entry.publication_state} · {entry.slug}</span>
                      <span>{ownEntry ? "Created by your account" : "Created by another account"}{entry.approved_at ? ` · Approved ${new Date(entry.approved_at).toLocaleString()}` : ""}</span>
                      {entry.source_url && <a href={entry.source_url} target="_blank" rel="noreferrer">Open source record ↗</a>}
                      {entry.summary && <p>{entry.summary}</p>}
                      <button className="secondary-action" type="button" onClick={() => setSelectedId(selectedId === entry.id ? "" : entry.id)}>{selectedId === entry.id ? "Close details" : "Review / edit details"}</button>
                      {selectedId === entry.id && (
                        <div className="content-review-detail">
                          <form onSubmit={(event) => void saveEdits(event, entry)}>
                            <label>Title<input name="title" defaultValue={entry.title} minLength={2} maxLength={240} required /></label>
                            <label>Summary<textarea name="summary" defaultValue={entry.summary ?? ""} rows={3} maxLength={5000} /></label>
                            <label>Body<textarea name="body" defaultValue={entry.body ?? ""} rows={7} maxLength={30000} /></label>
                            <button className="secondary-action" disabled={busy}>Save edits (returns to draft)</button>
                          </form>
                          <details><summary>Structured metadata</summary><pre>{JSON.stringify(entry.metadata_json, null, 2)}</pre></details>
                          <p className="workspace-muted">Saving edits to content already in review, approved or published state invalidates that state and returns the record to draft.</p>
                        </div>
                      )}
                    </div>
                    <div className="admin-member-actions">
                      {entry.publication_state === "review" && <>
                        <button className="primary-action" disabled={busy || ownEntry} title={ownEntry ? "A different authorised reviewer must approve your content." : "Approve this content"} onClick={() => void transition(entry, "approved")}>Approve</button>
                        <button className="secondary-action" disabled={busy} onClick={() => void transition(entry, "draft")}>Return to draft</button>
                      </>}
                      {entry.publication_state === "approved" && <button className="primary-action" disabled={busy} onClick={() => void transition(entry, "published")}>Publish</button>}
                      {entry.publication_state === "published" && <button className="secondary-action" disabled={busy} onClick={() => void transition(entry, "draft")}>Unpublish</button>}
                      {entry.publication_state !== "archived" && <button className="secondary-action" disabled={busy} onClick={() => void transition(entry, "archived")}>Archive</button>}
                      {busy && <span className="workspace-muted">Saving…</span>}
                    </div>
                  </article>
                );
              })}
            </section>
            <p className="workspace-muted">Public website feed includes published records only. Seeded website content remains in review until a different authorised reviewer approves it and an authorised administrator publishes it.</p>
          </>
        )}
      </section>
    </main>
  );
}
