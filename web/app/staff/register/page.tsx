import Link from "next/link";

export default function StaffAccountRegistrationPage() {
  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <Link className="secondary-action" href="/staff/login">Member sign in</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">STAFF & INSTITUTIONAL PARTNER ONBOARDING</p>
        <h1 className="workspace-title">Access by<br /><em>invitation.</em></h1>
        <section className="staff-card">
          <h2>Account creation is invitation-only</h2>
          <p className="workspace-muted">An authorised organisation administrator must assign your organisation and role. Open self-registration is disabled in the production environment so that accounts cannot acquire access outside the approved onboarding process.</p>
          <p className="workspace-muted">The new-user email invitation and password-setup workflow is being completed. Existing account holders can sign in and accept a membership invitation from their workspace.</p>
          <Link className="primary-action" href="/staff/login">Sign in to an existing account</Link>
        </section>
        <p><Link href="/">Return to the public website</Link></p>
      </section>
    </main>
  );
}
