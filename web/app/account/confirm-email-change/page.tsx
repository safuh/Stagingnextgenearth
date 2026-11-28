"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiPost, logout } from "@/lib/api";

export default function ConfirmEmailChangePage() {
  const [message, setMessage] = useState("Checking your confirmation link…");
  const [error, setError] = useState("");
  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    if (!token) { setMessage(""); setError("This email change link is incomplete."); return; }
    apiPost<{ message: string }>("/auth/email-change/confirm", { token })
      .then(async (result) => { setMessage(result.message); await logout().catch(() => undefined); })
      .catch((cause: unknown) => { setMessage(""); setError(cause instanceof Error ? cause.message : "Unable to confirm this email change."); });
  }, []);
  return <main className="workspace-shell"><header className="workspace-topbar"><Link className="brand" href="/">NextGen For Earth</Link></header><section className="workspace-content learner-auth-content"><p className="eyebrow">ACCOUNT SECURITY</p><h1 className="workspace-title">Confirm your<br /><em>new email.</em></h1>{message && <p className="workspace-notice" role="status">{message}</p>}{error && <p className="workspace-error" role="alert">{error}</p>}<p><Link href="/staff/login">Continue to sign in</Link></p></section></main>;
}
