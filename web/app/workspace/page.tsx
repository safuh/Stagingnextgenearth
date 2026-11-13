"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, apiPost, clearSession, hasSession } from "@/lib/api";

interface Organization {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  country_code: string;
}
interface MyMembership {
  id: string;
  organization_id: string;
  user_id: string;
  role: "admin" | "programme_manager" | "researcher" | "youth_volunteer" | "institutional_partner";
  status: string;
}
interface Programme {
  id: string;
  title: string;
  summary: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
}
interface Course {
  id: string;
  title: string;
  slug: string;
  description: string;
  category: string | null;
  delivery_mode: string;
  status: string;
}
interface Lesson {
  id: string;
  title: string;
  content_type: string;
  content: string | null;
  resource_url: string | null;
  duration_minutes: number | null;
  position: number;
}
interface Module {
  id: string;
  title: string;
  description: string | null;
  position: number;
  lessons: Lesson[];
}
interface Curriculum {
  course_id: string;
  title: string;
  modules: Module[];
}
interface Assessment {
  id: string;
  title: string;
  assessment_type: "quiz" | "assignment" | "evaluation";
  instructions: string;
  pass_mark: number;
  due_at: string | null;
}
interface CourseProgress {
  course_id: string;
  enrollment_status: string;
  progress_percent: number;
  completed_lesson_ids: string[];
  assessments: Array<{ assessment_id: string; score: number | null; feedback: string | null }>;
}
interface LearnerMentorship {
  id: string;
  course_title: string;
  relationship: "mentor" | "mentee";
  status: string;
  notes: string | null;
  created_at: string;
}
interface LearnerAttendance {
  id: string;
  course_title: string;
  session_title: string;
  session_date: string;
  attendance_status: string;
}
type Panel = "overview" | "programmes" | "learning";

export default function WorkspacePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [membership, setMembership] = useState<MyMembership | null>(null);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [mentorships, setMentorships] = useState<LearnerMentorship[]>([]);
  const [attendance, setAttendance] = useState<LearnerAttendance[]>([]);
  const [panel, setPanel] = useState<Panel>("overview");
  const [selectedCourse, setSelectedCourse] = useState<Course | null>(null);
  const [curriculum, setCurriculum] = useState<Curriculum | null>(null);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [assessmentResponses, setAssessmentResponses] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!hasSession()) {
      setError("Your sign-in session is not available. Please sign in again.");
      setLoading(false);
      return;
    }
    apiGet<Organization[]>("/organizations")
      .then((items) => {
        setOrganizations(items);
        if (items[0]) setOrganizationId(items[0].id);
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    let active = true;
    setError("");
    setSelectedCourse(null);
    setCurriculum(null);
    setProgress(null);
    Promise.all([
      apiGet<MyMembership>(`/organizations/${organizationId}/memberships/me`),
      apiGet<Programme[]>(`/organizations/${organizationId}/programmes`),
      apiGet<Course[]>(`/organizations/${organizationId}/learning/courses`),
      apiGet<LearnerMentorship[]>(`/organizations/${organizationId}/learning/my-mentorships`),
      apiGet<LearnerAttendance[]>(`/organizations/${organizationId}/learning/my-attendance`),
    ]).then(([myMembership, programmeItems, courseItems, mentorshipItems, attendanceItems]) => {
      if (!active) return;
      setMembership(myMembership);
      setProgrammes(programmeItems);
      setCourses(courseItems);
      setMentorships(mentorshipItems);
      setAttendance(attendanceItems);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load workspace data.");
    });
    return () => { active = false; };
  }, [organizationId]);

  async function openCourse(course: Course) {
    setSelectedCourse(course);
    setCurriculum(null);
    setProgress(null);
    setAssessments([]);
    setAssessmentResponses({});
    setNotice("");
    setError("");
    setDetailLoading(true);
    try {
      const outline = await apiGet<Curriculum>(
        `/organizations/${organizationId}/learning/courses/${course.id}/curriculum`,
      );
      setCurriculum(outline);
      try {
        const learnerProgress = await apiGet<CourseProgress>(
          `/organizations/${organizationId}/learning/courses/${course.id}/my-progress`,
        );
        setProgress(learnerProgress);
        if (["approved", "completed"].includes(learnerProgress.enrollment_status)) {
          const items = await apiGet<Assessment[]>(
            `/organizations/${organizationId}/learning/courses/${course.id}/assessments`,
          );
          setAssessments(items);
        }
      } catch {
        // A learner without an application has no progress record yet.
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load this course.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function applyToCourse() {
    if (!selectedCourse) return;
    setActionLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await apiPost<{ id: string; status: string }>(
        `/organizations/${organizationId}/learning/courses/${selectedCourse.id}/enrollments`,
        {},
      );
      setNotice(`Application submitted. Current status: ${result.status}.`);
      setProgress({
        course_id: selectedCourse.id,
        enrollment_status: result.status,
        progress_percent: 0,
        completed_lesson_ids: [],
        assessments: [],
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit your application.");
    } finally {
      setActionLoading(false);
    }
  }

  async function submitAssessment(assessmentId: string) {
    if (!selectedCourse) return;
    const response = assessmentResponses[assessmentId]?.trim();
    if (!response) {
      setError("Add your response before submitting the assessment.");
      return;
    }
    setActionLoading(true);
    setError("");
    setNotice("");
    try {
      await apiPost<{ id: string; status: string }>(
        `/organizations/${organizationId}/learning/assessments/${assessmentId}/submissions`,
        { submission: { response } },
      );
      setNotice("Assessment submitted successfully. Your course team can now review it.");
      setAssessmentResponses((current) => ({ ...current, [assessmentId]: "" }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit this assessment.");
    } finally {
      setActionLoading(false);
    }
  }

  async function completeLesson(lessonId: string) {
    if (!selectedCourse) return;
    setActionLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await apiPost<{
        status: string;
        progress_percent: number;
        certificate_number: string | null;
      }>(`/organizations/${organizationId}/learning/lessons/${lessonId}/complete`, {});
      setProgress((current) => current ? {
        ...current,
        enrollment_status: result.status,
        progress_percent: result.progress_percent,
        completed_lesson_ids: [...new Set([...current.completed_lesson_ids, lessonId])],
      } : current);
      setNotice(result.certificate_number
        ? `Course completed. Certificate ${result.certificate_number} has been issued.`
        : `Lesson marked complete. Course progress: ${result.progress_percent}%.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update lesson progress.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading your workspace…</p></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">MEMBER WORKSPACE</p>
        <h1 className="workspace-title">Your organisation.<br /><em>Your impact.</em></h1>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {organizations.length === 0 && !error ? (
          <div className="workspace-empty"><h2>No organisation access yet</h2><p>Ask your organisation administrator to invite your account to a workspace.</p></div>
        ) : (
          <>
            <label className="org-label" htmlFor="organization">Active organisation</label>
            <select id="organization" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
              {organizations.map((org) => <option value={org.id} key={org.id}>{org.name} · {org.country_code}</option>)}
            </select>
            {membership && (
              <section className="role-workspace" aria-label="Role-specific workspace">
                <div>
                  <span className="eyebrow">YOUR ACCESS</span>
                  <h2>{membership.role.replaceAll("_", " ")}</h2>
                  <p>Workspace sections are shown according to your active organisation role. The API independently enforces every permission.</p>
                </div>
                <div className="role-workspace-links">
                  {(membership.role === "admin" || membership.role === "programme_manager") && (
                    <Link href="/workspace/learning-admin">Learning operations →</Link>
                  )}
                  {["admin", "programme_manager", "researcher", "institutional_partner"].includes(membership.role) && (
                    <Link href="/workspace/research">Research workspace →</Link>
                  )}
                  {membership.role === "youth_volunteer" && (
                    <Link href="/workspace/youth">Youth & volunteer portal →</Link>
                  )}
                  {membership.role === "institutional_partner" && (
                    <Link href="/workspace/partner">Institutional partner portal →</Link>
                  )}
                  {membership.role === "admin" && (
                    <Link href="/workspace/administration">Organisation administration →</Link>
                  )}
                </div>
              </section>
            )}
            <nav className="workspace-tabs" aria-label="Workspace sections">
              {(["overview", "programmes", "learning"] as Panel[]).map((item) => (
                <button key={item} className={panel === item ? "active" : ""} onClick={() => { setPanel(item); setSelectedCourse(null); }}>{item}</button>
              ))}
            </nav>
            {(membership?.role === "admin" || membership?.role === "programme_manager") && (
              <Link className="staff-portal-link" href="/workspace/learning-admin">Learning operations · staff workspace →</Link>
            )}
            {panel === "overview" && (
              <div className="workspace-stats">
                <article><span>PROGRAMMES</span><strong>{programmes.length}</strong><p>Organisation programmes</p></article>
                <article><span>COURSES</span><strong>{courses.length}</strong><p>Published learning courses</p></article>
                <article><span>COUNTRY</span><strong>{organizations.find((org) => org.id === organizationId)?.country_code ?? "—"}</strong><p>Organisation registration</p></article>
              </div>
            )}
            {panel === "programmes" && (
              <section className="workspace-list"><h2>Programmes</h2>
                {programmes.length === 0 ? <p className="workspace-muted">No programmes are available in this organisation yet.</p> : programmes.map((item) => (
                  <article className="workspace-item" key={item.id}><div><h3>{item.title}</h3><p>{item.summary || "No programme summary provided."}</p></div><span className="status-pill">{item.status}</span></article>
                ))}
              </section>
            )}
            {panel === "learning" && (
              <section className="workspace-list">
                {!selectedCourse && (
                  <div className="learner-history-grid">
                    <section className="history-panel">
                      <h3>Mentorship</h3>
                      {mentorships.length === 0 ? <p className="workspace-muted">No mentorship relationships are recorded yet.</p> : mentorships.map((item) => (
                        <article className="history-row" key={item.id}>
                          <strong>{item.course_title}</strong>
                          <span>{item.relationship === "mentee" ? "Your mentor relationship" : "You are a mentor"}</span>
                          <small>{item.status}{item.notes ? ` · ${item.notes}` : ""}</small>
                        </article>
                      ))}
                    </section>
                    <section className="history-panel">
                      <h3>Attendance history</h3>
                      {attendance.length === 0 ? <p className="workspace-muted">No attendance records are available yet.</p> : attendance.map((item) => (
                        <article className="history-row" key={item.id}>
                          <strong>{item.session_title}</strong>
                          <span>{item.course_title} · {item.session_date}</span>
                          <small>Attendance: {item.attendance_status}</small>
                        </article>
                      ))}
                    </section>
                  </div>
                )}
                {selectedCourse ? (
                  <>
                    <button className="course-back" onClick={() => { setSelectedCourse(null); setCurriculum(null); setProgress(null); }}>← All courses</button>
                    <div className="course-heading"><div><p className="eyebrow">COURSE CURRICULUM</p><h2>{selectedCourse.title}</h2><p>{selectedCourse.description}</p></div><span className="status-pill">{selectedCourse.delivery_mode.replace("_", " ")}</span></div>
                    {progress && <div className="course-progress"><div><span>Your progress</span><strong>{progress.progress_percent}%</strong></div><div className="progress-track"><span style={{ width: `${progress.progress_percent}%` }} /></div><small>Enrollment: {progress.enrollment_status}</small></div>}
                    {!progress && selectedCourse.status === "published" && <button className="primary-action" onClick={applyToCourse} disabled={actionLoading}>{actionLoading ? "Submitting…" : "Apply for this course"}</button>}
                    {assessments.length > 0 && (
                      <section className="assessment-list">
                        <h3>Course assessments</h3>
                        {assessments.map((assessment) => (
                          <article className="assessment-card" key={assessment.id}>
                            <div className="assessment-meta"><strong>{assessment.title}</strong><span>{assessment.assessment_type} · pass mark {assessment.pass_mark}%</span></div>
                            <p>{assessment.instructions}</p>
                            {assessment.due_at && <small>Due {new Date(assessment.due_at).toLocaleString()}</small>}
                            {progress?.enrollment_status === "approved" && (
                              <div className="assessment-submit">
                                <label htmlFor={`assessment-${assessment.id}`}>Your response</label>
                                <textarea id={`assessment-${assessment.id}`} rows={4} value={assessmentResponses[assessment.id] ?? ""} onChange={(event) => setAssessmentResponses((current) => ({ ...current, [assessment.id]: event.target.value }))} placeholder="Write your response…" />
                                <button className="lesson-action" disabled={actionLoading} onClick={() => submitAssessment(assessment.id)}>Submit assessment</button>
                              </div>
                            )}
                          </article>
                        ))}
                      </section>
                    )}
                    {detailLoading ? <p className="workspace-muted">Loading curriculum…</p> : curriculum?.modules.length ? curriculum.modules.map((module) => (
                      <article className="module-card" key={module.id}>
                        <div className="module-title"><span>MODULE {module.position}</span><h3>{module.title}</h3>{module.description && <p>{module.description}</p>}</div>
                        {module.lessons.map((lesson) => {
                          const complete = progress?.completed_lesson_ids.includes(lesson.id) ?? false;
                          const canComplete = progress?.enrollment_status === "approved";
                          return <div className="lesson-row" key={lesson.id}>
                            <div><strong>{lesson.title}</strong><small>{lesson.content_type}{lesson.duration_minutes ? ` · ${lesson.duration_minutes} min` : ""}</small>
                              {lesson.content && <p>{lesson.content}</p>}
                              {lesson.resource_url && <a href={lesson.resource_url} target="_blank" rel="noreferrer">Open lesson resource ↗</a>}
                            </div>
                            {complete ? <span className="lesson-complete">Completed</span> : canComplete ? <button className="lesson-action" disabled={actionLoading} onClick={() => completeLesson(lesson.id)}>Mark complete</button> : null}
                          </div>;
                        })}
                      </article>
                    )) : !detailLoading && <p className="workspace-muted">This course has no published lessons yet.</p>}
                  </>
                ) : (
                  <>
                    <h2>Learning programmes</h2>
                    <p className="workspace-muted">Explore published courses, review the curriculum and track your learning progress.</p>
                    {courses.length === 0 ? <p className="workspace-muted">No published courses are available yet.</p> : courses.map((item) => (
                      <button className="course-item" key={item.id} onClick={() => openCourse(item)}>
                        <span><strong>{item.title}</strong><small>{item.category || "General"} · {item.delivery_mode.replace("_", " ")}</small><span>{item.description}</span></span>
                        <span className="course-open">View course →</span>
                      </button>
                    ))}
                  </>
                )}
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}
