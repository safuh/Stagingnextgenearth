"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPatch, apiPost, clearSession, hasSession } from "@/lib/api";

interface Organization {
  id: string;
  name: string;
  slug: string;
  country_code: string;
}
interface Membership {
  role: string;
}
interface Person {
  id: string;
  full_name: string;
  biography: string | null;
  positions: string[];
  person_types: string[];
  country_code: string;
  region: string | null;
  source_url: string | null;
  source_label: string | null;
  review_state: "pending" | "verified" | "rejected";
  visibility: "private" | "internal" | "public";
  status: "active" | "inactive";
}
interface PersonAudit {
  id: string;
  action: string;
  actor_user_id: string;
  changed_fields: string[];
  state: Record<string, unknown>;
  created_at: string;
}

const PERSON_TYPES = [
  "employee", "board_member", "executive", "volunteer", "ambassador",
  "researcher", "mentor", "advisor", "intern", "trainee", "consultant", "alumnus",
];

export default function PeopleDirectoryPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [organizationSlug, setOrganizationSlug] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [auditByPerson, setAuditByPerson] = useState<Record<string, PersonAudit[]>>({});

  async function loadPeople(id: string) {
    const rows = await apiGet<Person[]>(`/organizations/${id}/people`);
    setPeople(rows);
  }

  useEffect(() => {
    if (!hasSession()) {
      setError("Sign in to manage the organisation directory.");
      setLoading(false);
      return;
    }
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
    setPeople([]);
    Promise.all([
      apiGet<Membership>(`/organizations/${organizationId}/memberships/me`),
      loadPeople(organizationId),
    ]).then(([mine]) => {
      if (active) {
        setMembership(mine);
        const selected = organizations.find((item) => item.id === organizationId);
        setOrganizationSlug(selected?.slug ?? "");
      }
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load directory.");
    });
    return () => { active = false; };
  }, [organizationId, organizations]);

  async function createPerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const positions = String(data.get("positions") ?? "")
      .split("\n").map((item) => item.trim()).filter(Boolean);
    const personTypes = data.getAll("person_types").map(String);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiPost<Person>(`/organizations/${organizationId}/people`, {
        full_name: String(data.get("full_name") ?? "").trim(),
        biography: String(data.get("biography") ?? "").trim() || null,
        positions,
        person_types: personTypes,
        country_code: String(data.get("country_code") ?? "KE"),
        region: String(data.get("region") ?? "").trim() || null,
        source_url: String(data.get("source_url") ?? "").trim() || null,
        source_label: String(data.get("source_label") ?? "").trim() || null,
      });
      form.reset();
      await loadPeople(organizationId);
      setNotice("Directory profile created as private and pending review. No login account was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create directory profile.");
    } finally {
      setBusy(false);
    }
  }

  async function editPerson(event: FormEvent<HTMLFormElement>, person: Person) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const positions = String(data.get("positions") ?? "")
      .split("\n").map((item) => item.trim()).filter(Boolean);
    await updatePerson(person, {
      full_name: String(data.get("full_name") ?? "").trim(),
      biography: String(data.get("biography") ?? "").trim() || null,
      positions,
      region: String(data.get("region") ?? "").trim() || null,
    });
  }

  async function loadAudit(personId: string) {
    setError("");
    try {
      const events = await apiGet<PersonAudit[]>(
        `/organizations/${organizationId}/people/${personId}/audit-events`,
      );
      setAuditByPerson((current) => ({ ...current, [personId]: events }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load profile history.");
    }
  }

  async function updatePerson(person: Person, patch: Partial<Person>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiPatch<Person>(
        `/organizations/${organizationId}/people/${person.id}`,
        patch,
      );
      await loadPeople(organizationId);
      setNotice(`${person.full_name} updated.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update profile.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading people directory…</p></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/workspace"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">PEOPLE & GOVERNANCE</p>
        <h1 className="workspace-title">Organisation <em>directory.</em></h1>
        <p className="workspace-muted">Maintain staff, leadership, volunteers, ambassadors, mentors and researchers. Profiles are separate from login accounts and remain private until verified and published.</p>
        <p><Link className="secondary-action" href="/workspace/administration">← Administration workspace</Link></p>
        {organizations.length > 1 && <label className="admin-org-picker">Organisation<select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>{organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label>}
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {membership?.role !== "admin" ? (
          <section className="staff-card"><h2>Administrator access required</h2><p>Only organisation administrators can manage directory profiles.</p></section>
        ) : (
          <>
            <section className="staff-card">
              <p className="eyebrow">NEW DIRECTORY RECORD</p>
              <h2>Add a person</h2>
              <p className="workspace-muted">Use one position per line. Select all classifications that apply. A profile does not create a user account or grant portal access.</p>
              <form onSubmit={createPerson}>
                <label>Full name<input name="full_name" minLength={2} maxLength={200} required /></label>
                <label>Positions (one per line)<textarea name="positions" rows={3} maxLength={1500} /></label>
                <fieldset><legend>Person classifications</legend><div className="staff-grid">{PERSON_TYPES.map((type) => <label key={type}><input type="checkbox" name="person_types" value={type} /> {type.replaceAll("_", " ")}</label>)}</div></fieldset>
                <label>Biography<textarea name="biography" rows={3} maxLength={5000} /></label>
                <div className="staff-grid"><label>Country code<input name="country_code" defaultValue="KE" minLength={2} maxLength={2} pattern="[A-Za-z]{2}" /></label><label>County / region<input name="region" maxLength={120} /></label></div>
                <label>Source URL<input name="source_url" type="url" maxLength={1000} placeholder="https://" /></label>
                <label>Source label<input name="source_label" defaultValue="NextGen For Earth website" maxLength={160} /></label>
                <button className="primary-action" disabled={busy}>{busy ? "Saving…" : "Create private profile"}</button>
              </form>
            </section>
            <section className="staff-card admin-member-section">
              <div className="section-heading"><div><p className="eyebrow">REVIEW & PUBLICATION</p><h2>People directory</h2></div><span>{people.length} profiles</span></div>
              {people.length === 0 ? <p className="workspace-muted">No directory profiles yet.</p> : <div className="admin-member-list">
                {people.map((person) => (
                  <article className="admin-member-row" key={person.id}>
                    <div className="admin-member-meta">
                      <strong>{person.full_name}</strong>
                      <span>{person.positions.join(" · ") || "No position assigned"} · {person.person_types.join(", ") || "Unclassified"}</span>
                      <span>Review: {person.review_state} · Visibility: {person.visibility} · Status: {person.status}</span>
                      {person.source_url && <a href={person.source_url} target="_blank" rel="noreferrer">{person.source_label || "Source record"}</a>}
                      <details>
                        <summary>Change history</summary>
                        <button className="secondary-action" type="button" onClick={() => void loadAudit(person.id)}>Load audit history</button>
                        {(auditByPerson[person.id] ?? []).map((event) => (
                          <p key={event.id}>
                            <strong>{event.action}</strong> · {new Date(event.created_at).toLocaleString()}
                            <br />Fields: {event.changed_fields.join(", ")}
                          </p>
                        ))}
                        {auditByPerson[person.id]?.length === 0 && <p>No audit events recorded.</p>}
                      </details>
                      <details>
                        <summary>Edit profile</summary>
                        <form onSubmit={(event) => void editPerson(event, person)}>
                          <label>Name<input name="full_name" defaultValue={person.full_name} minLength={2} maxLength={200} required /></label>
                          <label>Positions (one per line)<textarea name="positions" defaultValue={person.positions.join("\n")} rows={3} /></label>
                          <label>Biography<textarea name="biography" defaultValue={person.biography ?? ""} rows={3} maxLength={5000} /></label>
                          <label>County / region<input name="region" defaultValue={person.region ?? ""} maxLength={120} /></label>
                          <button className="secondary-action" disabled={busy}>Save profile</button>
                        </form>
                      </details>
                    </div>
                    <div className="admin-member-actions">
                      <label>Review<select value={person.review_state} disabled={busy} onChange={(event) => void updatePerson(person, { review_state: event.target.value as Person["review_state"] })}><option value="pending">Pending</option><option value="verified">Verified</option><option value="rejected">Rejected</option></select></label>
                      <label>Visibility<select value={person.visibility} disabled={busy} onChange={(event) => void updatePerson(person, { visibility: event.target.value as Person["visibility"] })}><option value="private">Private</option><option value="internal">Internal</option><option value="public">Public</option></select></label>
                      <button className="secondary-action" disabled={busy} onClick={() => void updatePerson(person, { status: person.status === "active" ? "inactive" : "active" })}>{person.status === "active" ? "Archive" : "Reactivate"}</button>
                    </div>
                  </article>
                ))}
              </div>}
              {organizationSlug && <p className="workspace-muted">Public feed: <code>/api/public/organizations/{organizationSlug}/people</code>. Only active, verified, public profiles appear.</p>}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
