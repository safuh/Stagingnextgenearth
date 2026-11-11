"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiGet, apiPatch, apiPost, clearSession, hasSession } from "@/lib/api";

interface Organization { id: string; name: string; slug: string; country_code: string }
interface Membership {
  id: string; organization_id: string; user_id: string;
  role: "admin" | "programme_manager" | "researcher" | "youth_volunteer" | "institutional_partner";
  status: "invited" | "active" | "suspended";
}
interface AuditEvent {
  id: string; action: string; actor_user_id: string; subject_user_id: string | null;
  changes: Record<string, unknown>; created_at: string;
}
type InvitableRole = "programme_manager" | "researcher" | "youth_volunteer" | "institutional_partner";

export default function AdministrationPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [members, setMembers] = useState<Membership[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async (id: string) => {
    const [mine, memberRows, auditRows] = await Promise.all([
      apiGet<Membership>(`/organizations/${id}/memberships/me`),
      apiGet<Membership[]>(`/organizations/${id}/memberships`),
      apiGet<AuditEvent[]>(`/organizations/${id}/audit-events?limit=100`),
    ]);
    setMembership(mine);
    setMembers(memberRows);
    setEvents(auditRows);
  }, []);

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
        else setError("No active organisation membership was found.");
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    let active = true;
    setError("");
    refresh(organizationId).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load administration data.");
    });
    return () => { active = false; };
  }, [organizationId, refresh]);

  async function perform(key: string, message: string, work: () => Promise<unknown>) {
    setBusyId(key); setError(""); setNotice("");
    try {
      await work();
      await refresh(organizationId);
      setNotice(message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The administration action failed.");
    } finally {
      setBusyId("");
    }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const identifier = String(data.get("identifier") ?? "").trim();
    const role = String(data.get("role") ?? "") as InvitableRole;
    await perform("invite", "Invitation created. The invited account must accept it before access becomes active.", () =>
      apiPost(`/organizations/${organizationId}/memberships`, { identifier, role }));
    event.currentTarget.reset();
  }

  async function transferOwnership(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const userId = String(data.get("user_id") ?? "").trim();
    if (!window.confirm("Transfer organisation ownership to this active member? This changes both owners' roles.")) return;
    await perform("ownership", "Ownership transfer completed.", () =>
      apiPost(`/organizations/${organizationId}/ownership-transfer`, { new_owner_user_id: userId }));
    event.currentTarget.reset();
  }

  if (loading) return <main className="workspace-shell"><p>Loading organisation administration…</p></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/workspace"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">ORGANISATION GOVERNANCE</p>
        <h1 className="workspace-title">Administration <em>workspace.</em></h1>
        <p className="workspace-muted">Manage membership access, roles, ownership and the organisation audit trail.</p>
        {organizations.length > 1 && <label className="admin-org-picker">Organisation<select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>{organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label>}
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {membership?.role !== "admin" ? (
          <section className="staff-card"><h2>Administrator access required</h2><p>Your current organisation role does not permit membership administration. Ask an organisation administrator for access.</p><Link className="secondary-action" href="/workspace">Return to workspace</Link></section>
        ) : (
          <>
            <div className="workspace-stats admin-stats">
              <article><span>MEMBERSHIPS</span><strong>{members.length}</strong><p>Including invitations and suspended accounts</p></article>
              <article><span>ACTIVE MEMBERS</span><strong>{members.filter((item) => item.status === "active").length}</strong><p>Current organisation access</p></article>
              <article><span>PENDING INVITATIONS</span><strong>{members.filter((item) => item.status === "invited").length}</strong><p>Awaiting acceptance</p></article>
            </div>
            <div className="staff-grid admin-grid">
              <section className="staff-card">
                <h2>Invite an existing account</h2>
                <p>Invitations do not create accounts or grant access until the invited user accepts.</p>
                <form onSubmit={invite}>
                  <label>Account email / identifier<input name="identifier" type="email" maxLength={320} required /></label>
                  <label>Organisation role<select name="role" required><option value="programme_manager">Programme manager</option><option value="researcher">Researcher</option><option value="youth_volunteer">Youth volunteer</option><option value="institutional_partner">Institutional partner</option></select></label>
                  <button className="primary-action" disabled={busyId === "invite"}>{busyId === "invite" ? "Creating invitation…" : "Create invitation"}</button>
                </form>
              </section>
              <section className="staff-card">
                <h2>Transfer ownership</h2>
                <p>Only the current owner can transfer ownership. The new owner must already be an active member. Your role becomes programme manager.</p>
                <form onSubmit={transferOwnership}>
                  <label>New owner user ID<input name="user_id" minLength={1} maxLength={36} required /></label>
                  <button className="secondary-action" disabled={busyId === "ownership"}>Transfer ownership</button>
                </form>
              </section>
            </div>
            <section className="staff-card admin-member-section">
              <div className="section-heading"><div><p className="eyebrow">ACCESS CONTROL</p><h2>Organisation members</h2></div><span>{members.length} records</span></div>
              <div className="admin-member-list">
                {members.map((item) => (
                  <article className="admin-member-row" key={item.id}>
                    <div className="admin-member-meta"><strong>{item.user_id}</strong><span>{item.role.replaceAll("_", " ")} · {item.status}</span></div>
                    <div className="admin-member-actions">
                      <label>Role<select aria-label={`Role for ${item.user_id}`} value={item.role} disabled={busyId === item.id || item.status !== "active"} onChange={(event) => void perform(item.id, "Member role updated.", () => apiPatch(`/organizations/${organizationId}/memberships/${item.id}/role`, { role: event.target.value }))}>
                        <option value="admin">Administrator</option><option value="programme_manager">Programme manager</option><option value="researcher">Researcher</option><option value="youth_volunteer">Youth volunteer</option><option value="institutional_partner">Institutional partner</option>
                      </select></label>
                      <button className="secondary-action" disabled={busyId === item.id || item.role === "admin" && item.status === "active" && members.filter((m) => m.role === "admin" && m.status === "active").length <= 1 || item.user_id === membership.user_id && item.status === "active"} onClick={() => void perform(item.id, item.status === "suspended" ? "Membership reactivated." : "Membership suspended.", () => apiPatch(`/organizations/${organizationId}/memberships/${item.id}/status`, { status: item.status === "suspended" ? "active" : "suspended" }))}>
                        {item.status === "suspended" ? "Reactivate" : item.status === "invited" ? "Suspend invitation" : "Suspend"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
            <section className="staff-card admin-audit-section">
              <div className="section-heading"><div><p className="eyebrow">GOVERNANCE HISTORY</p><h2>Audit events</h2></div><span>Latest {events.length}</span></div>
              {events.length === 0 ? <p className="workspace-muted">No governance events have been recorded yet.</p> : events.map((item) => (
                <article className="admin-audit-row" key={item.id}><div><strong>{item.action.replaceAll(".", " ")}</strong><small>{new Date(item.created_at).toLocaleString()}</small></div><p>Actor: {item.actor_user_id}{item.subject_user_id ? ` · Subject: ${item.subject_user_id}` : ""}</p><pre>{JSON.stringify(item.changes, null, 2)}</pre></article>
              ))}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
