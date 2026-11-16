"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, clearSession, login, logout, register, restoreSession } from "@/lib/api";

type PublicContent = { id: string; content_type: string; title: string; summary: string | null; body: string | null; slug: string; source_url?: string | null; metadata_json?: { display_value?: string } };
type PublicPerson = { id: string; full_name: string; positions: string[]; biography: string | null };
type PublicPartner = { id: string; name: string; partner_type: string; description: string | null; website_url: string | null; country_code: string; region: string | null };
type PublicProgramme = { id: string; title: string; slug: string; summary: string | null; status: string; start_date: string | null; end_date: string | null };
type PublicCourse = { id: string; title: string; slug: string; description: string; category: string | null; delivery_mode: string; status: string; programme_id: string | null };

const portals = [
  {
    title: "Research & climate",
    description: "Research studies, governed datasets and climate intelligence.",
    tag: "Researcher portal",
    symbol: "⌁",
  },
  {
    title: "Youth & volunteers",
    description: "Learning programmes, mentorship and community participation.",
    tag: "Youth portal",
    symbol: "↗",
  },
  {
    title: "Programme operations",
    description: "Activities, delivery milestones, indicators and quality review.",
    tag: "Administrator portal",
    symbol: "▦",
  },
  {
    title: "Institutional partnerships",
    description: "Collaborative programmes, evidence and organisational reporting.",
    tag: "Partner portal",
    symbol: "◎",
  },
];

export default function HomePage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [subject, setSubject] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [catalogue, setCatalogue] = useState<PublicContent[]>([]);
  const [publicPeople, setPublicPeople] = useState<PublicPerson[]>([]);
  const [publicPartners, setPublicPartners] = useState<PublicPartner[]>([]);
  const [publicProgrammes, setPublicProgrammes] = useState<PublicProgramme[]>([]);
  const [publicCourses, setPublicCourses] = useState<PublicCourse[]>([]);

  useEffect(() => {
    let active = true;
    // Public feeds are independent: a temporary failure in one endpoint must not
    // suppress otherwise healthy programme, people, partner or CMS sections.
    Promise.all([
      apiGet<PublicContent[]>("/public/organizations/nextgen-for-earth/content").catch(() => []),
      apiGet<PublicPerson[]>("/public/organizations/nextgen-for-earth/people").catch(() => []),
      apiGet<PublicPartner[]>("/public/organizations/nextgen-for-earth/partners").catch(() => []),
      apiGet<PublicProgramme[]>("/public/organizations/nextgen-for-earth/programmes").catch(() => []),
      apiGet<PublicCourse[]>("/public/organizations/nextgen-for-earth/courses").catch(() => []),
    ]).then(([items, people, partners, programmes, courses]) => {
      if (!active) return;
      setCatalogue(items);
      setPublicPeople(people);
      setPublicPartners(partners);
      setPublicProgrammes(programmes);
      setPublicCourses(courses);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    restoreSession().then((session) => {
      if (!active || !session) return;
      setSubject(session.subject);
      setSignedIn(true);
    }).catch(() => {
      if (active) setSignedIn(false);
    });
    return () => { active = false; };
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (creatingAccount) await register(identifier.trim(), password);
      const result = await login(identifier.trim(), password);
      setSubject(result.subject);
      setSignedIn(true);
      setPassword("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      clearSession();
    }
    setSignedIn(false);
    setSubject("");
  }

  return (
    <main>
      <header className="topbar">
        <Link className="brand" href="/" aria-label="NextGen for Earth home">
          <span className="brand-mark">N</span>
          <span>nextgen<span className="brand-light">for</span>earth</span>
        </Link>
        <nav aria-label="Main navigation">
          <a href="#platform">Platform</a>
          <a href="#programmes">Programmes</a>\n          <a href="#research">Research</a>\n          <a href="#activities">Activities</a>
          <a href="/volunteer/apply">Volunteer</a>
          <a href="/employment/apply">Careers</a>
          <a href="#access">Sign in</a>
        </nav>
        <a className="nav-cta" href="#access">Access platform <span aria-hidden="true">↗</span></a>
      </header>

      <section className="hero" id="platform">
        <div className="hero-copy">
          <p className="eyebrow"><span /> RESEARCH · LEARNING · ENVIRONMENTAL ACTION</p>
          <h1>Evidence for a<br /><em>better</em> planet.</h1>
          <p className="hero-intro">
            One connected workspace for the people researching, restoring and
            building a more sustainable future.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href="#access">Enter the platform <span>→</span></a>
            <a className="text-link" href="#portals">Explore the portals <span>↓</span></a>
          </div>
          <div className="hero-note"><span className="pulse" /> A shared platform for measurable impact</div>
        </div>
        <div className="hero-art" aria-label="Abstract landscape illustration" role="img">
          <div className="sun" />
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="hill hill-back" />
          <div className="hill hill-front" />
          <div className="art-caption"><span>01 / 04</span><span>People · Planet · Progress</span></div>
        </div>
      </section>

      <section className="portals section-wrap" id="portals">
        <div className="section-heading">
          <div><p className="eyebrow">CONNECTED BY PURPOSE</p><h2>One mission.<br /><em>Four ways in.</em></h2></div>
          <p>Purpose-built spaces bring each community together while keeping
            organisational data and permissions protected.</p>
        </div>
        <div className="portal-grid">
          {portals.map((portal, index) => (
            <article className="portal-card" key={portal.title}>
              <div className="portal-card-top"><span className="portal-number">0{index + 1}</span><span className="portal-symbol">{portal.symbol}</span></div>
              <p className="portal-tag">{portal.tag}</p>
              <h3>{portal.title}</h3>
              <p className="portal-description">{portal.description}</p>
              <a href="#access" aria-label={`Sign in for ${portal.title}`}>Open portal <span>↗</span></a>
            </article>
          ))}
        </div>
      </section>

      <section className="portals section-wrap" id="programmes">
        <div className="section-heading"><div><p className="eyebrow">OUR WORK</p><h2>Programmes & <em>initiatives.</em></h2></div><p>Current organisational programmes and training opportunities.</p></div>
        <div className="portal-grid">
          {publicProgrammes.map((programme) => (
            <article className="portal-card" key={programme.id}><p className="portal-tag">Programme · {programme.status}</p><h3><Link href={`/programmes/${programme.slug}`}>{programme.title}</Link></h3><p className="portal-description">{programme.summary}</p>{(programme.start_date || programme.end_date) && <p className="portal-description">{programme.start_date ?? "Date to be announced"} – {programme.end_date ?? "Ongoing"}</p>}</article>
          ))}
          {publicCourses.map((course) => {
            const programme = publicProgrammes.find((item) => item.id === course.programme_id);
            return (
              <article className="portal-card" key={`course-${course.id}`}>
                <p className="portal-tag">Training course · {course.delivery_mode.replaceAll("_", " ")}</p>
                <h3>{course.title}</h3>
                <p className="portal-description">{course.description}</p>
                {programme && <p className="portal-description">Programme: {programme.title}</p>}
                {course.category && <p className="portal-description">Category: {course.category}</p>}
                <a href="#access">Sign in to access learning <span>↗</span></a>
              </article>
            );
          })}

        </div>
        {publicProgrammes.length === 0 && publicCourses.length === 0 && catalogue.length === 0 && <p className="muted">The public catalogue is being prepared. Approved entries will appear here.</p>}
      </section>
      <section className="portals section-wrap" id="activities">
        <div className="section-heading"><div><p className="eyebrow">ONGOING DELIVERY</p><h2>Work in <em>motion.</em></h2></div><p>Current activities connected to programme delivery, learning and community engagement.</p></div>
        <div className="portal-grid">
          {catalogue.filter((item) => item.content_type === "initiative").map((item) => (
            <article className="portal-card" key={item.id}><p className="portal-tag">Ongoing activity</p><h3>{item.title}</h3><p className="portal-description">{item.summary || item.body}</p></article>
          ))}
          {catalogue.filter((item) => item.content_type === "training_track").map((item) => (
            <article className="portal-card" key={item.id}><p className="portal-tag">Training track</p><h3>{item.title}</h3><p className="portal-description">{item.summary || item.body}</p></article>
          ))}
        </div>
        {catalogue.filter((item) => item.content_type === "initiative" || item.content_type === "training_track").length === 0 && <p className="muted">Activity and training information will appear here as it is published.</p>}
      </section>
      <section className="portals section-wrap" id="research">
        <div className="section-heading"><div><p className="eyebrow">EVIDENCE & KNOWLEDGE</p><h2>Research & <em>publications.</em></h2></div><p>Research outputs and knowledge products attributed to the organisation's published catalogue.</p></div>
        <div className="portal-grid">
          {catalogue.filter((item) => item.content_type === "publication" || item.content_type === "research_area").map((item) => (
            <article className="portal-card" key={item.id}><p className="portal-tag">{item.content_type === "publication" ? "Publication" : "Research area"}</p><h3>{item.title}</h3><p className="portal-description">{item.summary || item.body}</p>{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">View publication <span>↗</span></a>}</article>
          ))}
        </div>
        {catalogue.filter((item) => item.content_type === "publication" || item.content_type === "research_area").length === 0 && <p className="muted">Published research records will appear here.</p>}
      </section>
      <section className="portals section-wrap" id="impact">
        <div className="section-heading"><div><p className="eyebrow">ORGANISATIONAL IMPACT</p><h2>Evidence of <em>progress.</em></h2></div><p>Impact figures shown here are sourced from the organisation's published website and should be updated through reviewed reporting.</p></div>
        <div className="portal-grid">
          {catalogue.filter((item) => item.content_type === "impact_metric").map((item) => (
            <article className="portal-card" key={item.id}><p className="portal-tag">Published impact figure</p><h3>{item.metadata_json?.display_value || "—"}</h3><p className="portal-description">{item.title}</p></article>
          ))}
        </div>
        {catalogue.filter((item) => item.content_type === "impact_metric").length === 0 && <p className="muted">Reviewed impact figures will appear here.</p>}
      </section>
      <section className="portals section-wrap" id="people">
        <div className="section-heading"><div><p className="eyebrow">OUR COMMUNITY</p><h2>People & <em>partners.</em></h2></div><p>Publicly approved leadership, staff, volunteers, mentors and institutional partners.</p></div>
        <div className="portal-grid">
          {publicPeople.map((person) => <article className="portal-card" key={person.id}><p className="portal-tag">People</p><h3>{person.full_name}</h3><p className="portal-description">{person.positions.join(" · ")}</p>{person.biography && <p className="portal-description">{person.biography}</p>}</article>)}
          {publicPartners.map((partner) => <article className="portal-card" key={partner.id}><p className="portal-tag">Institutional partner</p><h3>{partner.name}</h3><p className="portal-description">{partner.partner_type.replaceAll("_", " ")}{partner.region ? ` · ${partner.region}` : ""}{partner.country_code ? ` · ${partner.country_code}` : ""}</p>{partner.description && <p className="portal-description">{partner.description}</p>}{partner.website_url && <a href={partner.website_url} target="_blank" rel="noreferrer">Partner website ↗</a>}</article>)}
        </div>
        {publicPeople.length === 0 && publicPartners.length === 0 && <p className="muted">Verified public profiles and partner relationships will appear here after approval.</p>}
      </section>

      <section className="access-section" id="access">
        <div className="access-copy">
          <p className="eyebrow">SECURE WORKSPACE</p>
          <h2>{signedIn ? "Welcome to the platform." : "Your work starts here."}</h2>
          <p>Sign in with your organisation account to access the workspaces and
            programmes available to your membership.</p>
          <div className="access-points"><span>✓ Organisation-scoped access</span><span>✓ Role-based permissions</span><span>✓ Research data governance</span></div>
        </div>
        <div className="login-panel">
          {signedIn ? (
            <div className="signed-in">
              <span className="login-icon">✓</span>
              <p className="eyebrow">SESSION ACTIVE</p>
              <h3>Signed in</h3>
              <p className="muted">{subject || "Your account"} is authenticated in this browser session.</p>
              <p className="session-note">Your active organisation memberships and published learning programmes are available in the workspace.</p>
              <Link className="button button-primary full" href="/workspace">Open organisation workspace <span>→</span></Link>
              <button className="button button-primary full" onClick={handleLogout}>Sign out</button>
            </div>
          ) : (
            <>
              <div className="login-heading"><span className="login-icon">↗</span><div><p className="eyebrow">MEMBER ACCESS</p><h3>{creatingAccount ? "Create account" : "Sign in"}</h3></div></div>
              <form onSubmit={handleLogin}>
                <label htmlFor="identifier">Email or account identifier</label>
                <input id="identifier" autoComplete="username" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required />
                <label htmlFor="password">Password</label>
                <input id="password" type="password" autoComplete={creatingAccount ? "new-password" : "current-password"} minLength={creatingAccount ? 12 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} required />
                {error && <p className="form-error" role="alert">{error}</p>}
                <button className="button button-primary full" type="submit" disabled={busy}>{busy ? (creatingAccount ? "Creating account…" : "Signing in…") : (creatingAccount ? "Create account securely" : "Continue securely")} <span>→</span></button>
              </form>
              <p className="login-footnote">{creatingAccount ? "After creating your account, submit a programme or employment application. Organisation access is granted only after review or invitation." : "Access is provided by your organisation administrator."}</p>
              <button className="text-link" type="button" onClick={() => { setCreatingAccount((value) => !value); setError(""); setPassword(""); }}>{creatingAccount ? "Already have an account? Sign in" : "New to NextGen? Create an account"}</button>
            </>
          )}
        </div>
      </section>

      <footer><Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link><span>Research with purpose. Action with evidence.</span><span>© {new Date().getFullYear()} NextGen for Earth</span></footer>
    </main>
  );
}
