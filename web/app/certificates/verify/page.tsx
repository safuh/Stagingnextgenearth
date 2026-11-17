"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { apiGet } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

interface VerificationResult {
  valid: boolean;
  certificate_number: string;
  course_title: string;
  issued_at: string;
  status: string;
}

export default function CertificateVerificationPage() {
  const [code, setCode] = useState("");
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const verificationCode = code.trim();
    if (!verificationCode) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const organization = await apiGet<{ id: string }>(
        `/public/organizations/${ORGANIZATION_SLUG}`,
      );
      const verified = await apiGet<VerificationResult>(
        `/organizations/${organization.id}/learning/certificates/verify/${encodeURIComponent(verificationCode)}`,
      );
      setResult(verified);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to verify this certificate.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <Link className="secondary-action" href="/learners">Learning portal</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">CREDENTIAL VALIDATION</p>
        <h1 className="workspace-title">Verify a <em>certificate.</em></h1>
        <p className="workspace-muted">Enter the verification code printed on a NextGen For Earth learning certificate. This public check confirms whether the credential is currently valid; it does not reveal the learner’s private account details.</p>
        <section className="staff-card">
          <form onSubmit={verify}>
            <label htmlFor="certificate-code">Certificate verification code</label>
            <input
              id="certificate-code"
              name="verification_code"
              autoComplete="off"
              spellCheck={false}
              maxLength={128}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
            />
            <button className="primary-action" disabled={busy || !code.trim()}>
              {busy ? "Checking…" : "Verify certificate"}
            </button>
          </form>
        </section>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {result && (
          <section className="staff-card" aria-live="polite">
            <p className="eyebrow">VERIFICATION RESULT</p>
            <h2>{result.valid ? "Certificate is valid" : "Certificate is not valid"}</h2>
            <p className="workspace-muted">Status: {result.status}</p>
            <dl>
              <dt>Certificate number</dt>
              <dd>{result.certificate_number}</dd>
              <dt>Course</dt>
              <dd>{result.course_title}</dd>
              <dt>Issued</dt>
              <dd>{new Date(result.issued_at).toLocaleDateString()}</dd>
            </dl>
          </section>
        )}
        <p><Link href="/">Return to the public website</Link></p>
      </section>
    </main>
  );
}
