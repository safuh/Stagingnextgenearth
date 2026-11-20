"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost, logout } from "@/lib/api";

interface PasswordChangeResult {
  message: string;
  revoked_refresh_sessions: number;
}

export default function AccountSecurityPage() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (newPassword !== confirmation) {
      setError("The new password and confirmation do not match.");
      return;
    }
    setBusy(true);
    try {
      await apiPost<PasswordChangeResult>("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      await logout();
      router.replace("/staff/login");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to change your password.");
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <Link className="secondary-action" href="/workspace">Return to workspace</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">ACCOUNT SECURITY</p>
        <h1 className="workspace-title">Protect your<br /><em>account access.</em></h1>
        <p className="workspace-muted">
          Change your password using your current password. A successful change revokes
          all outstanding refresh sessions, then signs this browser out. Other access
          tokens expire within their configured short lifetime.
        </p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        <section className="staff-card">
          <h2>Change password</h2>
          <form onSubmit={submit}>
            <label htmlFor="current-password">Current password</label>
            <input id="current-password" type="password" autoComplete="current-password"
              value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required />
            <label htmlFor="new-password">New password (12–256 characters)</label>
            <input id="new-password" type="password" autoComplete="new-password" minLength={12} maxLength={256}
              value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required />
            <label htmlFor="confirm-password">Confirm new password</label>
            <input id="confirm-password" type="password" autoComplete="new-password"
              value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required />
            <button className="primary-action" disabled={busy}>
              {busy ? "Updating password…" : "Change password and sign out"}
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}
