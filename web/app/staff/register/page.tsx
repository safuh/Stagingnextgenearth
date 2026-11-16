"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { login, register } from "@/lib/api";

export default function StaffAccountRegistrationPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(identifier.trim(), password);
      await login(identifier.trim(), password);
      setCreated(true);
      setPassword("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create your account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <Link className="secondary-action" href="/#access">Member sign in</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">STAFF & INSTITUTIONAL PARTNER ONBOARDING</p>
        <h1 className="workspace-title">Create your<br /><em>account identity.</em></h1>
        <p className="workspace-muted">Create a secure account before your organisation administrator invites you. Registration does not make you an employee, founder, executive, administrator, researcher or partner. Those permissions are assigned separately by an authorised organisation owner or administrator.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {created ? (
          <section className="staff-card">
            <h2>Account created</h2>
            <p>Your identity is registered and signed in. Send the administrator the exact email address you registered with. They must invite that account and assign your approved organisation role.</p>
            <p>When the invitation arrives, open its link and accept it while signed in to this account.</p>
            <Link className="primary-action" href="/#access">Continue to member sign in</Link>
          </section>
        ) : (
          <section className="staff-card">
            <h2>Register account</h2>
            <form onSubmit={submit}>
              <label htmlFor="staff-email">Email address</label>
              <input id="staff-email" type="email" autoComplete="username" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required />
              <label htmlFor="staff-password">Password (at least 12 characters)</label>
              <input id="staff-password" type="password" autoComplete="new-password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required />
              <button className="primary-action" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
            </form>
          </section>
        )}
        <p><Link href="/">Return to the public website</Link></p>
      </section>
    </main>
  );
}
