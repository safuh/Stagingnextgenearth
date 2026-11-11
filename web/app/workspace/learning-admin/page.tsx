"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost, clearSession, hasSession } from "@/lib/api";

interface Course {
  id: string;
  title: string;
  slug: string;
  description: string;
  status: string;
}
interface Enrollment {
  id: string;
  learner_id: string;
  status: string;
  progress_percent: number;
  applied_at: string;
}
interface Submission {
  id: string;
  assessment_id: string;
  assessment_title: string;
  learner_id: string;
  submission: Record<string, unknown>;
  score: number | null;
  feedback: string | null;
  submitted_at: string;
  evaluated_at: string | null;
}
interface Attendance {
  id: string;
  session_title: string;
  session_date: string;
  learner_id: string;
  attendance_status: string;
}
interface Mentorship {
  id: string;
  mentor_id: string;
  mentee_id: string;
  status: string;
  notes: string | null;
}

export default function LearningAdminPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [courseId, setCourseId] = useState("");
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [attendance, setAttendance] = useState<Attendance[]>([]);
  const [mentorships, setMentorships] = useState<Mentorship[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const base = courseId ? `/organizations/${organizationId}/learning` : "";
  const [organizationId, setOrganizationId] = useState("");

  useEffect(() => {
    if (!hasSession()) {
      setError("Your sign-in session is not available. Sign in again.");
      setLoading(false);
      return;
    }
    apiGet<Array<{ id: string }>>("/organizations")
      .then((items) => {
        if (items[0]) setOrganizationId(items[0].id);
        else setError("No active organisation membership was found.");
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    apiGet<Course[]>(`/organizations/${organizationId}/learning/courses?include_drafts=true`)
      .then((items) => {
        setCourses(items);
        if (items[0]) setCourseId(items[0].id);
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load courses."));
  }, [organizationId]);

  async function refreshReports(id = courseId) {
    if (!organizationId || !id) return;
    const root = `/organizations/${organizationId}/learning/courses/${id}`;
    const [applications, work, attendanceRows, mentoring] = await Promise.all([
      apiGet<Enrollment[]>(`${root}/enrollments`),
      apiGet<Submission[]>(`${root}/submissions`),
      apiGet<Attendance[]>(`${root}/attendance`),
      apiGet<Mentorship[]>(`${root}/mentorships`),
    ]);
    setEnrollments(applications);
    setSubmissions(work);
    setAttendance(attendanceRows);
    setMentorships(mentoring);
  }

  useEffect(() => {
    if (!courseId || !organizationId) return;
    setError("");
    refreshReports().catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Staff permissions are required to view learning operations."));
  }, [courseId, organizationId]);

  async function action(label: string, work: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      setNotice(label);
      await refreshReports();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The requested operation could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  async function createCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Course draft created.", async () => {
      const created = await apiPost<Course>(base + "/courses", {
        title: data.get("title"),
        slug: data.get("slug"),
        description: data.get("description"),
        category: data.get("category") || null,
        delivery_mode: data.get("delivery_mode"),
      });
      const next = [...courses, created];
      setCourses(next);
      setCourseId(created.id);
    });
    event.currentTarget.reset();
  }

  async function createModule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Module added to the selected course.", async () => {
      await apiPost(base + `/courses/${courseId}/modules`, {
        title: data.get("title"),
        description: data.get("description") || null,
        position: Number(data.get("position")),
      });
    });
    event.currentTarget.reset();
  }

  async function createLesson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Lesson added.", async () => {
      await apiPost(base + `/modules/${String(data.get("module_id"))}/lessons`, {
        title: data.get("title"),
        content_type: data.get("content_type"),
        content: data.get("content") || null,
        resource_url: data.get("resource_url") || null,
        duration_minutes: data.get("duration_minutes") ? Number(data.get("duration_minutes")) : null,
        position: Number(data.get("position")),
      });
    });
    event.currentTarget.reset();
  }

  async function decide(learnerId: string, decision: "approved" | "rejected") {
    await action(`Application ${decision}.`, () => apiPost(
      base + `/courses/${courseId}/enrollments/${learnerId}/decision`, { decision },
    ));
  }

  async function evaluate(event: FormEvent<HTMLFormElement>, attemptId: string) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Assessment evaluation saved.", () => apiPost(
      base + `/submissions/${attemptId}/evaluate`,
      { score: Number(data.get("score")), feedback: data.get("feedback") || null },
    ));
    event.currentTarget.reset();
  }

  async function createAssessment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Assessment created.", () => apiPost(base + `/courses/${courseId}/assessments`, {
      title: data.get("title"),
      assessment_type: data.get("assessment_type"),
      instructions: data.get("instructions"),
      pass_mark: Number(data.get("pass_mark")),
      configuration: {},
    }));
    event.currentTarget.reset();
  }

  async function recordAttendance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Attendance recorded.", () => apiPost(base + `/courses/${courseId}/attendance`, {
      session_key: data.get("session_key"),
      session_title: data.get("session_title"),
      session_date: data.get("session_date"),
      learner_id: data.get("learner_id"),
      attendance_status: data.get("attendance_status"),
    }));
    event.currentTarget.reset();
  }

  async function assignMentor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Mentorship assignment created.", () => apiPost(base + `/courses/${courseId}/mentorships`, {
      mentor_id: data.get("mentor_id"),
      mentee_id: data.get("mentee_id"),
      notes: data.get("notes") || null,
    }));
    event.currentTarget.reset();
  }

  if (loading) return <main className="workspace-shell"><p>Loading learning operations…</p></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/workspace"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">PROGRAMME OPERATIONS</p>
        <h1 className="workspace-title">Learning <em>management.</em></h1>
        <p className="workspace-muted">Course publishing, learner applications, assessment review, mentorship and attendance.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {courses.length > 0 && (
          <div className="staff-course-picker">
            <label htmlFor="staff-course">Manage course</label>
            <select id="staff-course" value={courseId} onChange={(event) => setCourseId(event.target.value)}>
              {courses.map((course) => <option key={course.id} value={course.id}>{course.title} · {course.status}</option>)}
            </select>
          </div>
        )}
        <div className="staff-grid">
          <section className="staff-card">
            <h2>Create course</h2>
            <form onSubmit={createCourse}>
              <label>Course title<input name="title" minLength={3} maxLength={240} required /></label>
              <label>URL slug<input name="slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" required /></label>
              <label>Description<textarea name="description" maxLength={12000} required /></label>
              <label>Category<input name="category" maxLength={100} /></label>
              <label>Delivery<select name="delivery_mode"><option value="blended">Blended</option><option value="online">Online</option><option value="in_person">In person</option></select></label>
              <button className="primary-action" disabled={busy}>Create draft</button>
            </form>
          </section>
          <section className="staff-card">
            <h2>Build curriculum</h2>
            <form onSubmit={createModule}>
              <h3>Add module</h3>
              <label>Module title<input name="title" minLength={2} required /></label>
              <label>Description<textarea name="description" /></label>
              <label>Position<input name="position" type="number" min="1" max="500" required /></label>
              <button className="primary-action" disabled={busy || !courseId}>Add module</button>
            </form>
            <form onSubmit={createLesson}>
              <h3>Add lesson</h3>
              <label>Module ID<input name="module_id" required /></label>
              <label>Lesson title<input name="title" minLength={2} required /></label>
              <label>Type<select name="content_type"><option value="text">Text</option><option value="video">Video</option><option value="document">Document</option><option value="link">Link</option><option value="workshop">Workshop</option></select></label>
              <label>Content<textarea name="content" /></label>
              <label>Resource URL<input name="resource_url" type="url" /></label>
              <label>Duration (minutes)<input name="duration_minutes" type="number" min="1" max="1440" /></label>
              <label>Position<input name="position" type="number" min="1" max="500" required /></label>
              <button className="primary-action" disabled={busy || !courseId}>Add lesson</button>
            </form>
            <button className="secondary-action" disabled={busy || !courseId || courses.find((course) => course.id === courseId)?.status === "published"} onClick={() => action("Course published.", () => apiPost(base + `/courses/${courseId}/publish`, {}))}>Publish selected course</button>
          </section>
          <section className="staff-card">
            <h2>Enrollment applications <span>{enrollments.filter((item) => item.status === "applied").length} pending</span></h2>
            {enrollments.length === 0 ? <p className="workspace-muted">No learner applications yet.</p> : enrollments.map((item) => (
              <article className="staff-record" key={item.id}>
                <strong>{item.learner_id}</strong><small>{item.status} · {item.progress_percent}% progress</small>
                {item.status === "applied" && <div className="staff-actions"><button onClick={() => decide(item.learner_id, "approved")} disabled={busy}>Approve</button><button onClick={() => decide(item.learner_id, "rejected")} disabled={busy}>Reject</button></div>}
              </article>
            ))}
          </section>
          <section className="staff-card">
            <h2>Assessments</h2>
            <form onSubmit={createAssessment}>
              <label>Title<input name="title" required /></label>
              <label>Type<select name="assessment_type"><option value="quiz">Quiz</option><option value="assignment">Assignment</option><option value="evaluation">Evaluation</option></select></label>
              <label>Instructions<textarea name="instructions" required /></label>
              <label>Pass mark (%)<input name="pass_mark" type="number" min="0" max="100" defaultValue="50" /></label>
              <button className="primary-action" disabled={busy || !courseId}>Create assessment</button>
            </form>
            <h3>Submitted work</h3>
            {submissions.length === 0 ? <p className="workspace-muted">No submissions to review.</p> : submissions.map((item) => (
              <article className="staff-record" key={item.id}>
                <strong>{item.assessment_title}</strong><small>Learner {item.learner_id} · submitted {new Date(item.submitted_at).toLocaleString()}</small>
                <pre>{JSON.stringify(item.submission, null, 2)}</pre>
                {item.score === null ? <form onSubmit={(event) => evaluate(event, item.id)}>
                  <label>Score (%)<input name="score" type="number" min="0" max="100" required /></label>
                  <label>Feedback<textarea name="feedback" /></label>
                  <button className="primary-action" disabled={busy}>Save evaluation</button>
                </form> : <p>Score: {item.score}% · {item.feedback || "No feedback"}</p>}
              </article>
            ))}
          </section>
          <section className="staff-card">
            <h2>Mentorship assignments</h2>
            <form onSubmit={assignMentor}>
              <label>Mentor user ID<input name="mentor_id" required /></label>
              <label>Mentee user ID<input name="mentee_id" required /></label>
              <label>Notes<textarea name="notes" /></label>
              <button className="primary-action" disabled={busy || !courseId}>Assign mentor</button>
            </form>
            {mentorships.map((item) => <article className="staff-record" key={item.id}><strong>{item.mentor_id} → {item.mentee_id}</strong><small>{item.status} · {item.notes || "No notes"}</small></article>)}
          </section>
          <section className="staff-card">
            <h2>Attendance</h2>
            <form onSubmit={recordAttendance}>
              <label>Session key<input name="session_key" required /></label>
              <label>Session title<input name="session_title" required /></label>
              <label>Date<input name="session_date" type="date" required /></label>
              <label>Learner user ID<input name="learner_id" required /></label>
              <label>Status<select name="attendance_status"><option value="present">Present</option><option value="late">Late</option><option value="excused">Excused</option><option value="absent">Absent</option></select></label>
              <button className="primary-action" disabled={busy || !courseId}>Record attendance</button>
            </form>
            {attendance.map((item) => <article className="staff-record" key={item.id}><strong>{item.session_title}</strong><small>{item.session_date} · {item.learner_id} · {item.attendance_status}</small></article>)}
          </section>
        </div>
      </section>
    </main>
  );
}
