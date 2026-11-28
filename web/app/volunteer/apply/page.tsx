"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { apiGet, apiPost, restoreSession } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

type Programme = {
  id: string;
  organization_id: string;
  title: string;
  slug: string;
  summary: string | null;
  status: string;
};

export default function VolunteerApplyPage() {
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [selected, setSelected] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;

    restoreSession()
      .then((session) => {
        if (active) setSignedIn(Boolean(session));
      })
      .catch(() => {
        if (active) setSignedIn(false);
      });

    apiGet<Programme[]>(
      `/public/organizations/${ORGANIZATION_SLUG}/programmes`,
    )
      .then((items) => {
        if (!active) return;
        const openProgrammes = items.filter((item) => ["planned", "active"].includes(item.status));
        setProgrammes(openProgrammes);
        setSelected(openProgrammes[0]?.id ?? "");
        setError("");
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Unable to load current programmes. Please try again later.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const programme = programmes.find((item) => item.id === selected);

    if (!programme) {
      setError("Choose an available programme.");
      return;
    }
    if (!signedIn) {
      setError("Sign in or create an account before submitting an application.");
      return;
    }

    setBusy(true);
    setError("");
    setNotice("");

    try {
      const result = await apiPost<{ id: string; status: string }>(
        `/organizations/${programme.organization_id}/programmes/${programme.id}/volunteer-applications`,
        {
          participation_type: String(data.get("participation_type") || "volunteer"),
          interest: String(data.get("interest") || "").trim(),
          availability: String(data.get("availability") || "").trim() || null,
        },
      );
      setNotice(`Your application has been received. Status: ${result.status}.`);
      form.reset();
    } catch (cause: unknown) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to submit your application. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <Link className="secondary-action" href="/learners">Learner account access</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">GET INVOLVED</p>
        <h1 className="workspace-title">Volunteer with <em>NextGen.</em></h1>
        <p className="workspace-muted">
          Explore active programmes and submit an expression of interest.
          Programme teams review every application before membership is activated.
        </p>

        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}

        {loading ? (
          <section className="staff-card" aria-live="polite">
            <p>Loading current volunteer opportunities…</p>
          </section>
        ) : programmes.length === 0 ? (
          <section className="staff-card">
            <h2>No open applications</h2>
            <p>
              {error
                ? "We could not retrieve the current programme list. Please retry later."
                : "There are no programmes currently accepting volunteer applications. Please check again later."}
            </p>
          </section>
        ) : (
          <section className="staff-card">
            <form onSubmit={submit}>
              <label>
                Programme
                <select value={selected} onChange={(event) => setSelected(event.target.value)}>
                  {programmes.map((programme) => (
                    <option key={programme.id} value={programme.id}>{programme.title}</option>
                  ))}
                </select>
              </label>
              {programmes.find((programme) => programme.id === selected)?.summary && (
                <p>{programmes.find((programme) => programme.id === selected)?.summary}</p>
              )}
              <label>
                How would you like to participate?
                <select name="participation_type">
                  <option value="volunteer">Volunteer</option>
                  <option value="ambassador">Ambassador</option>
                </select>
              </label>
              <label>
                Why are you interested?
                <textarea
                  name="interest"
                  rows={5}
                  minLength={20}
                  maxLength={5000}
                  required
                  placeholder="Describe your interests and relevant experience. Do not include sensitive personal information."
                />
              </label>
              <label>
                Availability (optional)
                <input name="availability" maxLength={500} placeholder="For example, weekends or school holidays" />
              </label>
              <p className="workspace-muted">
                A portal account is required. Do not include private contact, health or other
                sensitive information in your application. If you are under 18, a parent or
                guardian must provide any consent required by the programme before participation.
              </p>
              {!signedIn && (
                <p>
                  <Link href="/learners">Create or access your learner account</Link> before submitting.
                </p>
              )}
              <button className="primary-action" disabled={busy || !signedIn}>
                {busy ? "Submitting…" : "Submit expression of interest"}
              </button>
            </form>
          </section>
        )}
        <p><Link href="/">Return to the main website</Link></p>
      </section>
    </main>
  );
}
