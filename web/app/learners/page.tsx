"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost, clearSession, getAuthenticationContext, login, register, restoreSession } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";
import { resolvePortalDestination } from "@/lib/portal-routing";

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
type CurriculumPreview = {
  modules: Array<{
    id: string;
    title: string;
    description: string | null;
    lessons: Array<{
      id: string;
      title: string;
      content: string | null;
      resource_url: string | null;
      duration_minutes: number | null;
    }>;
  }>;
};

export default function LearnerPortalPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [creating, setCreating] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [courses, setCourses] = useState<Course[]>([]);
  const [curriculumPreviews, setCurriculumPreviews] = useState<Record<string, CurriculumPreview>>({});
  const [applications, setApplications] = useState<Application[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadLearnerData() {
    const organization = await apiGet<{ id: string; name: string; slug: string }>(
      `/public/organizations/${ORGANIZATION_SLUG}`,
    );
    const mine = await apiGet<Application[]>(
      `/organizations/${organization.id}/learning/my-enrollments`,
    );
    setApplications(mine);
  }

  useEffect(() => {
    let active = true;
    apiGet<Course[]>(`/public/organizations/${ORGANIZATION_SLUG}/courses`)
      .then(async (items) => {
        if (!active) return;
        setCourses(items);
        const previews = await Promise.all(items.map(async (course) => {
          try {
            const outline = await apiGet<CurriculumPreview>(
              `/public/organizations/${ORGANIZATION_SLUG}/courses/${course.slug}/curriculum`,
            );
            return [course.slug, outline] as const;
          } catch {
            return [course.slug, null] as const;
          }
        }));
        if (active) setCurriculumPreviews(Object.fromEntries(
          previews.filter((entry): entry is readonly [string, CurriculumPreview] => entry[1] !== null),
        ));
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "Unable to load published courses.");
      });
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
      const context = await getAuthenticationContext();
      const destination = resolvePortalDestination(context.memberships);
      if (destination === "/workspace") {
        window.location.assign(destination);
        return;
      }
      if (destination === "/workspace/accept-invitation") {
        window.location.assign(destination);
        return;
      }
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
        <nav className="learner-top-nav" aria-label="Learner navigation">
          <Link className="secondary-action" href="/">Public website</Link>
          {authenticated ? <button className="workspace-signout" type="button" onClick={() => { clearSession(); window.location.assign("/learners"); }}>Sign out</button> : <Link className="secondary-action" href="/#access">Staff & partner sign in</Link>}
        </nav>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">LEARNING COMMUNITY</p>
        <h1 className="workspace-title">Learn. Apply.<br /><em>Make a difference.</em></h1>
        <p className="workspace-muted">Create a learner account to apply for published courses. Course teams review applications before learning access is activated. A learner account does not grant staff or administrative permissions.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}

        {!authenticated ? (
          <>
          <section className="staff-card">
            <h2>Explore published courses</h2>
            {courses.length === 0 ? (
              <p className="workspace-muted">No courses are currently published. New learning opportunities will appear here when programme teams release them.</p>
            ) : (
              <div className="portal-grid">
                {courses.map((course) => (
                  <article className="portal-card" key={course.id}>
                    <p className="portal-tag">{course.category || "Learning"} · {course.delivery_mode.replaceAll("_", " ")}</p>
                    <h3>{course.title}</h3>
                    <p className="portal-description">{course.description}</p>
                    {curriculumPreviews[course.slug] && (
                      <details className="public-curriculum-preview">
                        <summary>
                          Explore curriculum · {curriculumPreviews[course.slug].modules.length} modules · {curriculumPreviews[course.slug].modules.reduce((count, module) => count + module.lessons.length, 0)} lessons
                        </summary>
                        {curriculumPreviews[course.slug].modules.map((module, moduleIndex) => (
                          <details key={module.id} className="public-curriculum-module">
                            <summary>Module {String(moduleIndex + 1).padStart(2, "0")} · {module.title} ({module.lessons.length} lessons)</summary>
                            {module.description && <p className="workspace-muted">{module.description}</p>}
                            {module.lessons.map((lesson, lessonIndex) => (
                              <article key={lesson.id} className="public-curriculum-lesson">
                                <p className="portal-tag">LESSON {String(lessonIndex + 1).padStart(2, "0")}{lesson.duration_minutes ? ` · ${lesson.duration_minutes} min` : ""}</p>
                                <h4>{lesson.title}</h4>
                                {lesson.content && <p className="learner-lesson-content">{lesson.content}</p>}
                                {lesson.resource_url && <a href={lesson.resource_url} target="_blank" rel="noreferrer">Further reading / source</a>}
                              </article>
                            ))}
                          </details>
                        ))}
                      </details>
                    )}
                    <Link className="primary-action" href="#learner-access">Sign in or register to apply</Link>
                  </article>
                ))}
              </div>
            )}
          </section>
          <section className="staff-card" id="learner-access">
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
          </>
        ) : (
          <>
            <section className="workspace-stats learner-stats" aria-label="Learning summary">
              <article><span>APPLICATIONS</span><strong>{applications.length}</strong><p>All course applications</p></article>
              <article><span>AWAITING REVIEW</span><strong>{applications.filter((item) => ["submitted", "pending", "under_review"].includes(item.status)).length}</strong><p>Applications not yet decided</p></article>
              <article><span>APPROVED / ACTIVE</span><strong>{applications.filter((item) => ["approved", "in_progress"].includes(item.status)).length}</strong><p>Courses available to start or continue</p></article>
              <article><span>COMPLETED</span><strong>{applications.filter((item) => item.status === "completed").length}</strong><p>Completed course enrolments</p></article>
            </section>
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
                        {curriculumPreviews[course.slug] && (
                          <details className="public-curriculum-preview">
                            <summary>
                              Explore curriculum · {curriculumPreviews[course.slug].modules.length} modules · {curriculumPreviews[course.slug].modules.reduce((count, module) => count + module.lessons.length, 0)} lessons
                            </summary>
                            {curriculumPreviews[course.slug].modules.map((module, moduleIndex) => (
                              <details key={module.id} className="public-curriculum-module">
                                <summary>Module {String(moduleIndex + 1).padStart(2, "0")} · {module.title} ({module.lessons.length} lessons)</summary>
                                {module.description && <p className="workspace-muted">{module.description}</p>}
                                {module.lessons.map((lesson, lessonIndex) => (
                                  <article key={lesson.id} className="public-curriculum-lesson">
                                    <p className="portal-tag">LESSON {String(lessonIndex + 1).padStart(2, "0")}{lesson.duration_minutes ? ` · ${lesson.duration_minutes} min` : ""}</p>
                                    <h4>{lesson.title}</h4>
                                    {lesson.content && <p className="learner-lesson-content">{lesson.content}</p>}
                                    {lesson.resource_url && <a href={lesson.resource_url} target="_blank" rel="noreferrer">Further reading / source</a>}
                                  </article>
                                ))}
                              </details>
                            ))}
                          </details>
                        )}
                        {application ? (
                          <>
                            <p className="workspace-muted">Application: {application.status.replaceAll("_", " ")} · Progress {application.progress_percent}%</p>
                            {(application.status === "approved" || application.status === "completed") && (
                              <Link className="primary-action" href={`/learners/courses/${course.id}`}>Open classroom</Link>
                            )}
                          </>
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
