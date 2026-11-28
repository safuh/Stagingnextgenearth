"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function AcceptInvitationPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
    setToken(value);
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!token) { setError("This invitation link is incomplete. Ask your programme or organisation administrator to resend it."); return; }
    if (password !== confirmation) { setError("The passwords do not match."); return; }
    setBusy(true);
    try {
      const response = await fetch("/api/session/invitations/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "same-origin",
        cache: "no-store",
        body: JSON.stringify({ token, password }),
      });
      const payload = await response.json().catch(() => ({})) as { detail?: string; roles?: string[] };
      if (!response.ok) throw new Error(payload.detail ?? `Invitation acceptance failed (${response.status})`);
      setPassword("");
      setConfirmation("");
      setNotice("Your account and assigned organisation access are now active.");
      const roles = payload.roles ?? [];
      router.replace(roles.length === 1 && roles[0] === "learner" ? "/learners" : "/workspace");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to accept this invitation.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar"><Link className="brand" href="/">NextGen For Earth</Link><Link className="secondary-action" href="/staff/login">Sign in</Link></header>
      <section className="workspace-content learner-auth-content">
        <p className="eyebrow">SECURE ORGANISATION ONBOARDING</p>
        <h1 className="workspace-title">Your invitation.<br /><em>Your access.</em></h1>
        <p className="workspace-muted">Create your password to verify the invited email address and activate only the organisation roles and programme access assigned by your administrator.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        <section className="staff-card learner-auth-card">
          <h2>Set up your account</h2>
          <form onSubmit={submit}>
            <label htmlFor="invite-password">Account password (new accounts: at least 12 characters)</label>
            <input id="invite-password" type="password" autoComplete="new-password" minLength={1} maxLength={256} value={password} onChange={(event) => setPassword(event.target.value)} required />
            <label htmlFor="invite-password-confirm">Confirm password</label>
            <input id="invite-password-confirm" type="password" autoComplete="new-password" minLength={1} maxLength={256} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required />
            <button className="primary-action" disabled={busy || !token}>{busy ? "Activating account…" : "Create account and accept invitation"}</button>
          </form>
          <p className="workspace-muted">Already have a platform account? Sign in with that account password when accepting the invitation. Invitation links are single-use and expire automatically.</p>
        </section>
      </section>
    </main>
  );
}
