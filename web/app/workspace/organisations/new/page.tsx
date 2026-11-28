"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { ApiRequestError, apiPost, clearSession } from "@/lib/api";
import { slugifyOrganisationName } from "@/lib/organisation-onboarding";

interface Organisation {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  country_code: string;
}

const countries = [
  ["KE", "Kenya"], ["UG", "Uganda"], ["TZ", "Tanzania"], ["RW", "Rwanda"],
  ["ET", "Ethiopia"], ["SS", "South Sudan"], ["SO", "Somalia"], ["CD", "Democratic Republic of the Congo"],
  ["NG", "Nigeria"], ["GH", "Ghana"], ["ZA", "South Africa"], ["ZM", "Zambia"],
  ["MW", "Malawi"], ["MZ", "Mozambique"], ["SN", "Senegal"], ["CI", "Côte d’Ivoire"], ["IN", "India"], ["GB", "United Kingdom"], ["US", "United States"],
] as const;

export default function NewOrganisationPage() {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [countryCode, setCountryCode] = useState("KE");
  const [description, setDescription] = useState("");
  const [created, setCreated] = useState<Organisation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const suggestedSlug = useMemo(() => slugifyOrganisationName(name), [name]);
  const activeSlug = slugEdited ? slug : suggestedSlug;
  const slugValid = /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(activeSlug) && activeSlug.length >= 2 && activeSlug.length <= 120;

  function updateName(value: string) {
    setName(value);
    if (!slugEdited) setSlug(slugifyOrganisationName(value));
  }

  function updateSlug(value: string) {
    setSlugEdited(true);
    setSlug(slugifyOrganisationName(value));
  }

  async function createOrganisation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (name.trim().length < 2) {
      setError("Enter an organisation name with at least two characters.");
      return;
    }
    if (!slugValid) {
      setError("Use a unique workspace address with at least two lowercase letters or numbers, separated by single hyphens.");
      return;
    }
    setBusy(true);
    try {
      const organisation = await apiPost<Organisation>("/organizations", {
        name: name.trim(),
        slug: activeSlug,
        country_code: countryCode,
        description: description.trim() || null,
      });
      setCreated(organisation);
    } catch (cause) {
      if (cause instanceof ApiRequestError && cause.status === 409) {
        setError("That workspace address is already in use. Choose another address and try again.");
      } else if (cause instanceof ApiRequestError && cause.status === 401) {
        setError("Your sign-in session has expired. Sign in again, then return to organisation setup.");
      } else {
        setError(cause instanceof Error ? cause.message : "We could not create the organisation. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell organisation-onboarding-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/workspace"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <div className="workspace-topbar-actions">
          <Link className="secondary-action" href="/workspace">Workspace</Link>
          <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
        </div>
      </header>

      <section className="workspace-content admin-workspace-content organisation-onboarding-content">
        <div className="admin-page-heading organisation-onboarding-heading">
          <div>
            <p className="eyebrow">ORGANISATION SETUP · 01 / 03</p>
            <h1 className="workspace-title">Build your <em>workspace.</em></h1>
            <p className="workspace-muted">Create a dedicated organisation space for your people, research, programmes and climate work. Your account becomes its first administrator.</p>
          </div>
          <Link className="admin-back-link" href="/workspace">← Back to workspace</Link>
        </div>

        <div className="organisation-setup-progress" aria-label="Organisation setup stages">
          <div className="is-current"><span>01</span><strong>Create workspace</strong></div>
          <div><span>02</span><strong>Set up your team</strong></div>
          <div><span>03</span><strong>Start your work</strong></div>
        </div>

        {created ? (
          <section className="organisation-created-panel" aria-live="polite">
            <div className="organisation-created-mark" aria-hidden="true">✓</div>
            <p className="eyebrow">WORKSPACE CREATED</p>
            <h2>{created.name}</h2>
            <p className="workspace-muted">Your organisation is ready. Your account has been granted active administrator membership. The next steps below are operator tasks; legal, governance and research approvals are not automatically verified.</p>
            <div className="organisation-created-meta"><span>WORKSPACE ADDRESS</span><strong>{created.slug}</strong><span>COUNTRY</span><strong>{created.country_code}</strong><span>YOUR ACCESS</span><strong>Administrator · Active</strong></div>
            <div className="organisation-next-actions">
              <Link className="primary-action" href={`/workspace?organization_id=${encodeURIComponent(created.id)}`}>Open organisation workspace →</Link>
              <Link className="secondary-action" href={`/workspace/administration?organization_id=${encodeURIComponent(created.id)}`}>Invite your team</Link>
              <Link className="secondary-action" href={`/workspace/research?organization_id=${encodeURIComponent(created.id)}`}>Create a research study</Link>
            </div>
            <div className="organisation-first-run-checklist">
              <h3>Your first-run checklist</h3>
              <ul>
                <li>Confirm the organisation profile, mandate and accountable contacts.</li>
                <li>Invite individual team members and assign least-privilege roles.</li>
                <li>Set up programmes and appoint delivery owners.</li>
                <li>Start research in concept status, then complete protocol, ethics and data-governance reviews before fieldwork.</li>
                <li>Configure climate and learning operations where they are part of your mandate.</li>
              </ul>
            </div>
          </section>
        ) : (
          <div className="organisation-onboarding-grid">
            <section className="staff-card organisation-creation-card">
              <div className="organisation-card-heading">
                <div><p className="eyebrow">NEW TENANT</p><h2>Organisation details</h2></div>
                <span className="status-pill">Private workspace</span>
              </div>
              <p className="workspace-muted">Start with the core identity. You can configure people, programmes and research after creation.</p>
              {error && <p className="workspace-error" role="alert">{error}</p>}
              <form onSubmit={createOrganisation} noValidate>
                <label htmlFor="organisation-name">Organisation name <span aria-hidden="true">*</span>
                  <input id="organisation-name" name="name" value={name} onChange={(event) => updateName(event.target.value)} minLength={2} maxLength={200} autoComplete="organization" required placeholder="e.g. East Africa Climate Research Network" />
                </label>
                <label htmlFor="organisation-slug">Workspace address <span aria-hidden="true">*</span>
                  <div className="organisation-slug-input"><span>nextgenfor.earth/</span><input id="organisation-slug" name="slug" value={activeSlug} onChange={(event) => updateSlug(event.target.value)} minLength={2} maxLength={120} autoCapitalize="none" autoCorrect="off" spellCheck={false} required aria-describedby="organisation-slug-help" /></div>
                  <small id="organisation-slug-help">Lowercase letters, numbers and hyphens. This address must be unique.</small>
                  {!slugValid && activeSlug.length > 0 && <small className="organisation-field-error">Use at least two characters and single hyphens between words.</small>}
                </label>
                <label htmlFor="organisation-country">Primary country <span aria-hidden="true">*</span>
                  <select id="organisation-country" value={countryCode} onChange={(event) => setCountryCode(event.target.value)} required>
                    {countries.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
                  </select>
                </label>
                <label htmlFor="organisation-description">What does your organisation work on? <span className="organisation-optional">Optional</span>
                  <textarea id="organisation-description" name="description" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={5000} rows={5} placeholder="A short description of your mission, communities and areas of work." />
                  <small>{description.length.toLocaleString()} / 5,000 characters</small>
                </label>
                <button className="primary-action organisation-submit" type="submit" disabled={busy || !name.trim() || !slugValid}>{busy ? "Creating secure workspace…" : "Create organisation workspace →"}</button>
                <p className="organisation-form-footnote">By creating this workspace, you become its first administrator. You are responsible for confirming your organisation&apos;s mandate and governing access.</p>
              </form>
            </section>

            <aside className="organisation-onboarding-aside">
              <section className="organisation-aside-card organisation-aside-dark">
                <p className="eyebrow">ONE WORKSPACE · MANY CAPABILITIES</p>
                <h2>Everything connected. Governance built in.</h2>
                <p>Bring your teams, programmes and evidence into one organisation-scoped environment.</p>
                <div className="organisation-capability-list">
                  <div><span>01</span><strong>People & access</strong><small>Invite staff, partners and learners with defined roles.</small></div>
                  <div><span>02</span><strong>Research & evidence</strong><small>Create studies, manage datasets and govern publication.</small></div>
                  <div><span>03</span><strong>Climate intelligence</strong><small>Work with observations, analysis and reviewed releases.</small></div>
                  <div><span>04</span><strong>Programmes & learning</strong><small>Manage delivery, curriculum, cohorts and outcomes.</small></div>
                </div>
              </section>
              <section className="organisation-aside-card">
                <p className="eyebrow">IMPORTANT</p>
                <h3>Creation is not verification.</h3>
                <p>Creating a tenant does not verify legal registration, institutional mandate, ethics approval, community consent, safeguarding capacity or data rights. Record and complete those checks through your organisation&apos;s governance process.</p>
              </section>
              <p className="organisation-invitation-note">Joining an existing organisation instead? Ask its administrator to invite the email address linked to your platform account. <Link href="/workspace/accept-invitation">Accept an invitation →</Link></p>
            </aside>
          </div>
        )}
      </section>
    </main>
  );
}
