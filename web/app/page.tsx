"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { clearSession, hasSession, login, logout } from "@/lib/api";

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
  const [signedIn, setSignedIn] = useState(hasSession());
  const [subject, setSubject] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
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
          <a href="#portals">Portals</a>
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
              <div className="login-heading"><span className="login-icon">↗</span><div><p className="eyebrow">MEMBER ACCESS</p><h3>Sign in</h3></div></div>
              <form onSubmit={handleLogin}>
                <label htmlFor="identifier">Email or account identifier</label>
                <input id="identifier" autoComplete="username" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required />
                <label htmlFor="password">Password</label>
                <input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
                {error && <p className="form-error" role="alert">{error}</p>}
                <button className="button button-primary full" type="submit" disabled={busy}>{busy ? "Signing in…" : "Continue securely"} <span>→</span></button>
              </form>
              <p className="login-footnote">Access is provided by your organisation administrator.</p>
            </>
          )}
        </div>
      </section>

      <footer><Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link><span>Research with purpose. Action with evidence.</span><span>© {new Date().getFullYear()} NextGen for Earth</span></footer>
    </main>
  );
}
