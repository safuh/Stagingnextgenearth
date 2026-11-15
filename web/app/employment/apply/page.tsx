"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { apiPost } from "@/lib/api";

export default function EmploymentApplyPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiPost<{ id: string; status: string }>(
        "/public/organizations/nextgen-for-earth/employment-applications",
        {
          full_name: String(data.get("full_name") ?? "").trim(),
          desired_position: String(data.get("desired_position") ?? "").trim(),
          qualifications: String(data.get("qualifications") ?? "").trim(),
          experience_summary: String(data.get("experience_summary") ?? "").trim() || null,
        },
      );
      setNotice(`Application received. Reference: ${result.id}. Status: ${result.status}.`);
      form.reset();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit your application.");
    } finally {
      setBusy(false);
    }
  }

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
        <section className="staff-card">
          <form onSubmit={submit}>
            <label>Full name<input name="full_name" minLength={2} maxLength={200} autoComplete="name" required /></label>
            <label>Position of interest<input name="desired_position" minLength={2} maxLength={160} required placeholder="For example, Climate Research Associate" /></label>
            <label>Qualifications and relevant skills<textarea name="qualifications" rows={5} minLength={20} maxLength={5000} required placeholder="Summarise relevant qualifications, skills and training. Do not include sensitive personal information." /></label>
            <label>Relevant experience (optional)<textarea name="experience_summary" rows={4} maxLength={5000} placeholder="Briefly describe relevant projects or work." /></label>
            <p className="workspace-muted">You must be signed in to apply. Do not include identity document numbers, health information, passwords or other sensitive data. An application remains private and pending until reviewed.</p>
            <button className="primary-action" disabled={busy}>{busy ? "Submitting…" : "Submit application"}</button>
          </form>
        </section>
        <p><Link href="/">Return to the main website</Link></p>
      </section>
    </main>
  );
}
