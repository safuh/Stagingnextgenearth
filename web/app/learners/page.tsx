"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost, login, register, restoreSession } from "@/lib/api";

type Course = {
  id: string;
  organization_id: string;
  title: string;
  slug: string;
  description: string;
  category: string | null;
  delivery_mode: string;
};
type Application = {
  id: string;
  course_id: string;
  course_title: string;
  status: string;
  progress_percent: number;
};

export default function LearnerPortalPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [creating, setCreating] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [courses, setCourses] = useState<Course[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadLearnerData() {
    const [organization, available] = await Promise.all([
      apiGet<{ id: string; name: string; slug: string }>(
        "/public/organizations/next-gen-for-earth",
      ),
      apiGet<Course[]>("/public/organizations/next-gen-for-earth/courses"),
    ]);
    setCourses(available);
    const mine = await apiGet<Application[]>(
      `/organizations/${organization.id}/learning/my-enrollments`,
    );
    setApplications(mine);
  }

  useEffect(() => {
    let active = true;
    restoreSession().then(async (session) => {
      if (!active || !session) return;
      setAuthenticated(true);
      try {
        await loadLearnerData();
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Unable to load learner data.");
      }
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  async function submitAccess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (creating) await register(identifier.trim(), password);
      await login(identifier.trim(), password);
      setAuthenticated(true);
      setPassword("");
      if (creating) setNotice("Your learner account is ready. You can now apply to a published course.");
      await loadLearnerData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to complete account access.");
    } finally {
      setBusy(false);
    }
  }

  async function apply(course: Course) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await apiPost<{ id: string; status: string }>(
        `/organizations/${course.organization_id}/learning/courses/${course.id}/enrollments`,
        {},
      );
      setNotice(`Application submitted for ${course.title}. Status: ${result.status}.`);
      await loadLearnerData();
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
        <Link className="secondary-action" href="/#access">Staff & partner sign in</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">LEARNING COMMUNITY</p>
        <h1 className="workspace-title">Learn. Apply.<br /><em>Make a difference.</em></h1>
        <p className="workspace-muted">Create a learner account to apply for published courses. Course teams review applications before learning access is activated. A learner account does not grant staff or administrative permissions.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}

        {!authenticated ? (
          <section className="staff-card">
            <h2>{creating ? "Create your learner account" : "Learner sign in"}</h2>
            <form onSubmit={submitAccess}>
              <label htmlFor="learner-email">Email address</label>
              <input id="learner-email" type="email" autoComplete="username" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required />
              <label htmlFor="learner-password">Password</label>
              <input id="learner-password" type="password" autoComplete={creating ? "new-password" : "current-password"} minLength={creating ? 12 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} required />
              <button className="primary-action" disabled={busy}>{busy ? "Please wait…" : creating ? "Create learner account" : "Sign in"}</button>
            </form>
            <button className="text-link" type="button" onClick={() => { setCreating((value) => !value); setError(""); setPassword(""); }}>
              {creating ? "Already registered? Sign in" : "New learner? Create an account"}
            </button>
            <p className="workspace-muted">Use an email address you control. Never share your password. Do not enter sensitive personal information in course applications.</p>
          </section>
        ) : (
          <>
            <section className="staff-card">
              <h2>Published learning opportunities</h2>
              {courses.length === 0 ? <p className="workspace-muted">No published courses are currently accepting applications.</p> : (
                <div className="portal-grid">
                  {courses.map((course) => {
                    const application = applications.find((item) => item.course_id === course.id);
                    return (
                      <article className="portal-card" key={course.id}>
                        <p className="portal-tag">{course.category || "Learning"} · {course.delivery_mode.replaceAll("_", " ")}</p>
                        <h3>{course.title}</h3>
                        <p className="portal-description">{course.description}</p>
                        {application ? (
                          <p className="workspace-muted">Application: {application.status.replaceAll("_", " ")} · Progress {application.progress_percent}%</p>
                        ) : (
                          <button className="primary-action" disabled={busy} onClick={() => void apply(course)}>Apply for this course</button>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
            <section className="staff-card">
              <h2>Your applications</h2>
              {applications.length === 0 ? <p className="workspace-muted">You have not applied to a course yet.</p> : applications.map((application) => (
                <p key={application.id}>{application.course_title} — {application.status.replaceAll("_", " ")} ({application.progress_percent}% complete)</p>
              ))}
            </section>
          </>
        )}
        <p><Link href="/">Return to the public website</Link></p>
      </section>
    </main>
  );
}
