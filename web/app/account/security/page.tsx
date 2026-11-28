"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost, getAuthenticationContext, logout } from "@/lib/api";

export default function AccountSecurityPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [verified, setVerified] = useState(false);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    Promise.all([
      getAuthenticationContext(),
      fetch("/api/backend/auth/connections", { credentials: "same-origin", cache: "no-store" })
        .then(async (response) => {
          if (!response.ok) throw new Error("Unable to load connected identity providers.");
          return response.json() as Promise<{ providers: string[] }>;
        }),
    ]).then(([context, connections]) => {
      setEmail(context.identifier);
      setVerified(context.email_verified);
      setGoogleConnected(connections.providers.includes("google"));
    }).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "Your account session could not be loaded.");
    });
  }, []);

  async function run(key: string, action: () => Promise<{ message: string }>) {
    setBusy(key); setError(""); setNotice("");
    try { const result = await action(); setNotice(result.message); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "The account security action failed."); }
    finally { setBusy(""); }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run("password", async () => {
      const result = await apiPost<{ message: string }>("/auth/change-password", {
        current_password: currentPassword, new_password: newPassword,
      });
      setCurrentPassword(""); setNewPassword("");
      await logout().catch(() => undefined);
      router.replace("/staff/login");
      return result;
    });
  }

  async function changeEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run("email", async () => {
      const result = await apiPost<{ message: string }>("/auth/email-change/request", {
        new_email: newEmail, current_password: currentPassword,
      });
      setCurrentPassword(""); setNewEmail("");
      return result;
    });
  }

  async function revokeSessions() {
    await run("sessions", async () => {
      const result = await apiPost<{ message: string }>("/auth/sessions/revoke-all", {});
      await logout().catch(() => undefined);
      router.replace("/staff/login");
      return result;
    });
  }

  return <main className="workspace-shell"><header className="workspace-topbar"><Link className="brand" href="/workspace">NextGen For Earth</Link><Link className="secondary-action" href="/workspace">Workspace</Link></header><section className="workspace-content"><p className="eyebrow">IDENTITY & ACCESS MANAGEMENT</p><h1 className="workspace-title">Account <em>security.</em></h1><p className="workspace-muted">Manage your verified email, password, connected identity providers and active sign-in sessions.</p>{error && <p className="workspace-error" role="alert">{error}</p>}{notice && <p className="workspace-notice" role="status">{notice}</p>}
    <div className="staff-grid admin-grid">
      <section className="staff-card"><p className="eyebrow">PRIMARY IDENTITY</p><h2>Email address</h2><p><strong>{email || "Loading account…"}</strong></p><p className="workspace-muted">{verified ? "Verified mailbox" : "Not yet verified"}</p>{!verified && <button className="primary-action" disabled={busy === "verify"} onClick={() => void run("verify", () => apiPost("/auth/email-verification/request", {}))}>{busy === "verify" ? "Sending…" : "Send verification link"}</button>}</section>
      <section className="staff-card"><p className="eyebrow">CONNECTED SIGN-IN</p><h2>Google account</h2><p className="workspace-muted">{googleConnected ? "A Google identity is connected to this account." : "Connect Google using the same verified email address as this account."}</p><a className="secondary-action" href="/api/session/google/start?portal=staff">{googleConnected ? "Sign in with Google" : "Connect with Google"}</a></section>
      <section className="staff-card"><p className="eyebrow">CREDENTIALS</p><h2>Change password</h2><form onSubmit={changePassword}><label htmlFor="security-current-password">Current password</label><input id="security-current-password" type="password" autoComplete="current-password" minLength={1} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /><label htmlFor="security-new-password">New password</label><input id="security-new-password" type="password" autoComplete="new-password" minLength={12} maxLength={256} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /><button className="primary-action" disabled={busy === "password"}>{busy === "password" ? "Updating…" : "Change password"}</button></form></section>
      <section className="staff-card"><p className="eyebrow">IDENTITY UPDATE</p><h2>Change email address</h2><form onSubmit={changeEmail}><label htmlFor="security-email-current-password">Confirm current password</label><input id="security-email-current-password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /><label htmlFor="security-new-email">New email address</label><input id="security-new-email" type="email" autoComplete="email" value={newEmail} onChange={(event) => setNewEmail(event.target.value)} required /><button className="primary-action" disabled={busy === "email"}>{busy === "email" ? "Sending confirmation…" : "Send email change link"}</button></form><p className="workspace-muted">Your current email remains active until the new mailbox is confirmed.</p></section>
      <section className="staff-card"><p className="eyebrow">SESSION CONTROL</p><h2>Sign out everywhere</h2><p className="workspace-muted">Revoke all refresh sessions and invalidate existing access tokens across your devices.</p><button className="secondary-action" disabled={busy === "sessions"} onClick={() => void revokeSessions()}>{busy === "sessions" ? "Revoking…" : "Revoke all sessions"}</button></section>
    </div><p className="workspace-muted"><Link href="/staff/login">Return to sign in</Link></p></section></main>;
}
