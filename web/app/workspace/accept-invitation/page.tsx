"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiPost, getAuthenticationContext, login, logout, restoreSession } from "@/lib/api";

type Membership = { id: string; role: string; status: string };

export default function AcceptInvitationPage() {
  const [organizationId, setOrganizationId] = useState("");
  const [invitationId, setInvitationId] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [invitationMatchesAccount, setInvitationMatchesAccount] = useState<boolean | null>(null);
  const [accountIdentifier, setAccountIdentifier] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const orgId = params.get("organization_id") ?? "";
    const inviteId = params.get("invitation_id") ?? "";
    setOrganizationId(orgId);
    setInvitationId(inviteId);
    if (!orgId || !inviteId) setInvitationMatchesAccount(false);
    restoreSession().then(async (session) => {
      setAuthenticated(Boolean(session));
      if (!session || !orgId || !inviteId) return;
      try {
        const context = await getAuthenticationContext();
        setAccountIdentifier(context.identifier);
        setInvitationMatchesAccount(context.memberships.some((item) =>
          item.organization_id === orgId && item.membership_id === inviteId && item.status === "invited"
        ));
      } catch {
        setInvitationMatchesAccount(false);
      }
    }).catch(() => setAuthenticated(false));
  }, []);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await login(identifier.trim(), password);
      const context = await getAuthenticationContext();
      setAuthenticated(true);
      setPassword("");
      setAccountIdentifier(context.identifier);
      const matches = context.memberships.some((item) =>
        item.organization_id === organizationId && item.membership_id === invitationId && item.status === "invited"
      );
      setInvitationMatchesAccount(matches);
      setNotice(matches
        ? "Signed in with the invited account. Review the invitation and accept to activate your membership."
        : "This account does not own the invitation link. Sign out and use the exact account invited by the organisation.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  async function switchAccount() {
    setBusy(true);
    setError("");
    try {
      await logout();
      setAuthenticated(false);
      setInvitationMatchesAccount(null);
      setAccountIdentifier("");
      setNotice("Signed out. Sign in using the exact account email invited by the organisation.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to switch accounts.");
    } finally {
      setBusy(false);
    }
  }

  async function accept() {
    if (!organizationId || !invitationId) {
      setError("This invitation link is incomplete. Ask the organisation administrator to issue a new link.");
      return;
    }
    setBusy(true); setError("");
    try {
      const result = await apiPost<Membership>(
        `/organizations/${organizationId}/memberships/${invitationId}/accept`,
        {},
      );
      setNotice(`Invitation accepted. Your organisation role is ${result.role.replaceAll("_", " ")}.`);
      window.location.assign("/workspace");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to accept this invitation.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar"><Link className="brand" href="/">NextGen For Earth</Link></header>
      <section className="workspace-content">
        <p className="eyebrow">SECURE ORGANISATION ONBOARDING</p>
        <h1 className="workspace-title">Accept your <em>invitation.</em></h1>
        <p className="workspace-muted">Sign in with the same account email address that the administrator invited. An invitation does not activate access until you accept it.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {!authenticated ? (
          <section className="staff-card">
            <h2>Sign in to continue</h2>
            <form onSubmit={signIn}>
              <label>Account email<input type="email" autoComplete="username" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required /></label>
              <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
              <button className="primary-action" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
            </form>
            <p className="workspace-muted">No account yet? <Link href="/staff/register">Register a staff or partner account</Link>, then ask the administrator to invite that exact email address.</p>
          </section>
        ) : (
          <section className="staff-card">
            <h2>Invitation ready</h2>
            <p>Signed in as <strong>{accountIdentifier || "your account"}</strong>.</p>
            {invitationMatchesAccount === true ? (
              <>
                <p>The pending invitation is assigned to this account. Accepting activates the membership and its administrator-assigned role.</p>
                <button className="primary-action" onClick={() => void accept()} disabled={busy || !organizationId || !invitationId}>{busy ? "Accepting…" : "Accept organisation invitation"}</button>
              </>
            ) : invitationMatchesAccount === false ? (
              <p className="workspace-error" role="alert">This account is not the account named in this invitation. Sign out and use the exact invited email address. The server will also verify ownership before activation.</p>
            ) : (
              <p className="workspace-muted">Checking invitation ownership…</p>
            )}
            <button className="text-link" type="button" onClick={() => void switchAccount()} disabled={busy}>Not the invited account? Switch account</button>
          </section>
        )}
        <p><Link className="secondary-action" href="/">Return to public website</Link></p>
      </section>
    </main>
  );
}
