"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function StaffSignInPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(identifier.trim(), password);
      setPassword("");
      router.replace("/workspace");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <Link className="secondary-action" href="/learners">Learner portal</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">EMPLOYEE & INSTITUTIONAL PARTNER ACCESS</p>
        <h1 className="workspace-title">Organisation<br /><em>sign in.</em></h1>
        <p className="workspace-muted">
          Use the account email invited by NextGen For Earth. Signing in authenticates
          your identity; organisation access still depends on an active membership
          and the roles assigned to that membership.
        </p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        <section className="staff-card">
          <h2>Sign in to your account</h2>
          <form onSubmit={submit}>
            <label htmlFor="staff-login-email">Email address</label>
            <input id="staff-login-email" type="email" autoComplete="username"
              value={identifier} onChange={(event) => setIdentifier(event.target.value)} required />
            <label htmlFor="staff-login-password">Password</label>
            <input id="staff-login-password" type="password" autoComplete="current-password"
              value={password} onChange={(event) => setPassword(event.target.value)} required />
            <button className="primary-action" disabled={busy}>
              {busy ? "Signing in…" : "Sign in securely"}
            </button>
          </form>
          <p className="workspace-muted">
            Have a pending invitation? <Link href="/workspace/accept-invitation">Accept invitation</Link>.
          </p>
          <p className="workspace-muted">
            New employee or partner? <Link href="/staff/register">Create an account identity</Link>,
            then ask an organisation administrator to invite that exact email address.
          </p>
          <p className="workspace-muted">
            Applying for training? Use the separate <Link href="/learners">learner portal</Link>.
          </p>
        </section>
        <p><Link href="/">Return to the public website</Link></p>
      </section>
    </main>
  );
}
