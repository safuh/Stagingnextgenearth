"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiPost, logout } from "@/lib/api";

export default function RecoverAccountPage() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setToken(new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "");
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }, []);
  async function requestReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { const result = await apiPost<{ message: string }>("/auth/password-reset/request", { email }); setNotice(result.message); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to request account recovery."); }
    finally { setBusy(false); }
  }
  async function confirmReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { const result = await apiPost<{ message: string }>("/auth/password-reset/confirm", { token, new_password: password }); setNotice(result.message); setPassword(""); await logout().catch(() => undefined); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to reset password."); }
    finally { setBusy(false); }
  }
  return <main className="workspace-shell"><header className="workspace-topbar"><Link className="brand" href="/">NextGen For Earth</Link></header><section className="workspace-content learner-auth-content"><p className="eyebrow">ACCOUNT SECURITY</p><h1 className="workspace-title">Recover your<br /><em>account.</em></h1>{error && <p className="workspace-error" role="alert">{error}</p>}{notice && <p className="workspace-notice" role="status">{notice}</p>}<section className="staff-card learner-auth-card">{token ? <><h2>Choose a new password</h2><form onSubmit={confirmReset}><label htmlFor="reset-password">New password</label><input id="reset-password" type="password" minLength={12} maxLength={256} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><button className="primary-action" disabled={busy}>{busy ? "Updating…" : "Reset password"}</button></form></> : <><h2>Send recovery instructions</h2><form onSubmit={requestReset}><label htmlFor="reset-email">Account email</label><input id="reset-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /><button className="primary-action" disabled={busy}>{busy ? "Sending…" : "Send recovery email"}</button></form></>}</section><p className="workspace-muted"><Link href="/staff/login">Return to sign in</Link></p></section></main>;
}
