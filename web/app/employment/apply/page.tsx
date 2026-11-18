"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost, restoreSession } from "@/lib/api";

type EmploymentApplication = {
  id: string;
  desired_position: string;
  status: string;
  review_note: string | null;
};

const organizationSlug = "nextgen-for-earth";

export default function EmploymentApplyPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [applications, setApplications] = useState<EmploymentApplication[]>([]);

  async function loadApplications() {
    const rows = await apiGet<EmploymentApplication[]>(
      `/public/organizations/${organizationSlug}/my-employment-applications`,
    );
    setApplications(rows);
  }

  useEffect(() => {
    let active = true;
    async function initialise() {
      try {
        const session = await restoreSession();
        if (!active) return;
        setSignedIn(Boolean(session));
        if (!session) return;
        const rows = await apiGet<EmploymentApplication[]>(
          `/public/organizations/${organizationSlug}/my-employment-applications`,
        );
        if (active) setApplications(rows);
      } catch (cause) {
        if (active) {
          setSignedIn(false);
          setError(cause instanceof Error ? cause.message : "Unable to load your applications.");
        }
      }
    }
    void initialise();
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!signedIn) {
      setError("Sign in or create an account before submitting an application.");
      return;
    }
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiPost<EmploymentApplication>(
        `/public/organizations/${organizationSlug}/employment-applications`,
        {
          full_name: String(data.get("full_name") ?? "").trim(),
          desired_position: String(data.get("desired_position") ?? "").trim(),
          qualifications: String(data.get("qualifications") ?? "").trim(),
          experience_summary: String(data.get("experience_summary") ?? "").trim() || null,
        },
      );
      setNotice(`Application received. Reference: ${result.id}. Status: ${result.status}.`);
      form.reset();
      await loadApplications();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit your application.");
    } finally {
      setBusy(false);
    }
  }

  async function withdraw(application: EmploymentApplication) {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost<EmploymentApplication>(
        `/public/organizations/${organizationSlug}/employment-applications/${application.id}/withdraw`,
        {},
      );
      setNotice("Your pending application has been withdrawn. You may submit a new application when ready.");
      await loadApplications();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to withdraw your application.");
    } finally {
      setBusy(false);
    }
  }

  const pendingApplication = applications.find((application) => application.status === "pending");
  const approvedApplication = applications.find((application) => application.status === "approved");
  const applicationHistory = applications.filter((application) => application.status !== "pending");
  const canSubmit = signedIn && !pendingApplication && !approvedApplication;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <Link className="secondary-action" href="/#access">Sign in / create account</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">CAREERS & OPPORTUNITIES</p>
        <h1 className="workspace-title">Work with <em>NextGen.</em></h1>
        <p className="workspace-muted">Submit an expression of interest for an employee position. Every application is reviewed by an authorised organisation administrator. Approval does not automatically publish your profile.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {pendingApplication && <section className="staff-card">
          <h2>Your pending application</h2>
          <p><strong>{pendingApplication.desired_position}</strong> · Status: {pendingApplication.status}</p>
          <p className="workspace-muted">Only you and authorised reviewers can see this application. Withdrawing keeps a private record and prevents it from being approved.</p>
          <button className="secondary-action" disabled={busy} onClick={() => void withdraw(pendingApplication)}>{busy ? "Withdrawing…" : "Withdraw application"}</button>
        </section>}
        {applicationHistory.length > 0 && <section className="staff-card">
          <h2>Your application history</h2>
          {applicationHistory.map((application) => <p key={application.id}><strong>{application.desired_position}</strong> · {application.status}{application.review_note ? ` · ${application.review_note}` : ""}</p>)}
        </section>}
        {approvedApplication && <section className="staff-card">
          <h2>Application approved</h2>
          <p className="workspace-muted">Your employee access is active. Sign in to the platform to continue.</p>
        </section>}
        {!signedIn && <p className="workspace-muted"><Link href="/#access">Sign in or create an account</Link> to submit and track an application.</p>}
        {canSubmit && <section className="staff-card">
          <form onSubmit={submit}>
            <label>Full name<input name="full_name" minLength={2} maxLength={200} autoComplete="name" required /></label>
            <label>Position of interest<input name="desired_position" minLength={2} maxLength={160} required placeholder="For example, Climate Research Associate" /></label>
            <label>Qualifications and relevant skills<textarea name="qualifications" rows={5} minLength={20} maxLength={5000} required placeholder="Summarise relevant qualifications, skills and training. Do not include sensitive personal information." /></label>
            <label>Relevant experience (optional)<textarea name="experience_summary" rows={4} maxLength={5000} placeholder="Briefly describe relevant projects or work." /></label>
            <p className="workspace-muted">Do not include identity document numbers, health information, passwords or other sensitive data. An application remains private and pending until reviewed.</p>
            <button className="primary-action" disabled={busy}>{busy ? "Submitting…" : "Submit application"}</button>
          </form>
        </section>}
        <p><Link href="/">Return to the main website</Link></p>
      </section>
    </main>
  );
}
