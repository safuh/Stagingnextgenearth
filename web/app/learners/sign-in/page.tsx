"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { getAuthenticationContext, login } from "@/lib/api";

export default function LearnerSignInPage() {
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
      const context = await getAuthenticationContext();
      const hasLearnerAccess = context.memberships.some(
        (membership) => membership.status === "active" && membership.roles.includes("learner"),
      );
      if (!hasLearnerAccess) {
        setError("This account does not yet have an active learner enrolment. Use the invitation link sent by your programme team, or contact your learning coordinator.");
        return;
      }
      setPassword("");
      router.replace("/learners");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to sign in to the learner portal.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell learner-auth-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <nav className="learner-top-nav" aria-label="Portal navigation">
          <Link className="secondary-action" href="/learners">Explore learning</Link>
          <Link className="secondary-action" href="/staff/login">Staff & partner access</Link>
        </nav>
      </header>
      <section className="workspace-content learner-auth-content">
        <p className="eyebrow">NEXTGEN LEARNING COMMUNITY · SECURE ACCESS</p>
        <h1 className="workspace-title">Your learning.<br /><em>Your next chapter.</em></h1>
        <p className="workspace-muted learner-auth-intro">
          Sign in to continue your courses, assessments and learning record. Learner access is issued by an authorised programme team; your account only receives the role and curriculum specified in your invitation.
        </p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        <section className="staff-card learner-auth-card">
          <p className="eyebrow">LEARNER ACCOUNT</p>
          <h2>Sign in to your classroom</h2>
          <form onSubmit={submit}>
            <label htmlFor="learner-signin-email">Email address</label>
            <input id="learner-signin-email" type="email" autoComplete="username" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required />
            <label htmlFor="learner-signin-password">Password</label>
            <input id="learner-signin-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
            <button className="primary-action" disabled={busy}>{busy ? "Signing in…" : "Continue to learning"}</button>
          </form>
          <p className="workspace-muted">New to a programme? Your coordinator will email you a secure invitation link to create your password and activate your assigned learner access. There is no open self-registration.</p>
        </section>
        <p className="workspace-muted"><Link href="/learners">Browse published learning pathways</Link> · <Link href="/">Return to NextGen For Earth</Link></p>
      </section>
    </main>
  );
}
