"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiGet, apiPatch, apiPost, clearSession, hasSession } from "@/lib/api";

interface MemberChoice {
  user_id: string;
  role: string;
  roles: string[];
}
interface LessonChoice {
  id: string;
  title: string;
  content_type: "text" | "video" | "document" | "link" | "workshop";
  content: string | null;
  resource_url: string | null;
  duration_minutes: number | null;
  position: number;
}
interface ModuleChoice {
  id: string;
  title: string;
  description?: string | null;
  position: number;
  lessons?: LessonChoice[];
}
interface ProgrammeChoice {
  id: string;
  title: string;
  status: string;
}
interface Course {
  id: string;
  title: string;
  slug: string;
  description: string;
  category?: string | null;
  delivery_mode?: "online" | "in_person" | "blended";
  programme_id: string | null;
  status: string;
}
interface Enrollment {
  id: string;
  learner_id: string;
  status: string;
  progress_percent: number;
  applied_at: string;
}
interface EvaluationHistory {
  id: string;
  score: number;
  feedback: string | null;
  previous_score: number | null;
  previous_feedback: string | null;
  evaluated_by: string;
  evaluated_at: string;
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
  evaluation_history: EvaluationHistory[];
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
interface ProgrammeOutcomes {
  programme_id: string;
  programme_title: string;
  course_count: number;
  average_progress: number;
  totals: {
    learners: number;
    approved: number;
    completed: number;
    attendance_records: number;
    attendance_sessions: number;
    mentorship_assignments: number;
    active_mentorships: number;
    assessment_submissions: number;
    evaluated_submissions: number;
    pending_evaluations: number;
  };
  courses: Array<{
    course_id: string;
    title: string;
    status: string;
    learners: number;
    completed: number;
    average_progress: number;
    pending_evaluations: number;
  }>;
}
interface CourseReport {
  learners: number;
  approved: number;
  completed: number;
  average_progress: number;
  attendance_records: number;
  attendance_by_status: Record<string, number>;
  attendance_sessions: number;
  mentorship_assignments: number;
  active_mentorships: number;
  assessment_submissions: number;
  evaluated_submissions: number;
  pending_evaluations: number;
}

export default function LearningAdminPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [programmes, setProgrammes] = useState<ProgrammeChoice[]>([]);
  const [courseId, setCourseId] = useState("");
  const [modules, setModules] = useState<ModuleChoice[]>([]);
  const [curriculum, setCurriculum] = useState<{
    title: string;
    description: string;
    modules: ModuleChoice[];
  } | null>(null);
  const [members, setMembers] = useState<MemberChoice[]>([]);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [attendance, setAttendance] = useState<Attendance[]>([]);
  const [mentorships, setMentorships] = useState<Mentorship[]>([]);
  const [report, setReport] = useState<CourseReport | null>(null);
  const [programmeOutcomes, setProgrammeOutcomes] = useState<ProgrammeOutcomes | null>(null);
  const [selectedProgrammeId, setSelectedProgrammeId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [organizationId, setOrganizationId] = useState("");
  const base = `/organizations/${organizationId}/learning`;

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
    Promise.all([
      apiGet<Course[]>(`/organizations/${organizationId}/learning/courses?include_drafts=true`),
      apiGet<MemberChoice[]>(`/organizations/${organizationId}/memberships/directory`),
      apiGet<ProgrammeChoice[]>(`/organizations/${organizationId}/programmes`),
    ])
      .then(([items, memberItems, programmeItems]) => {
        setCourses(items);
        setMembers(memberItems);
        setProgrammes(programmeItems);
        if (items[0]) setCourseId(items[0].id);
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load staff workspace data."));
  }, [organizationId]);

  const refreshReports = useCallback(async (id = courseId) => {
    if (!organizationId || !id) return;
    const root = `/organizations/${organizationId}/learning/courses/${id}`;
    const [applications, work, attendanceRows, mentoring, courseReport] = await Promise.all([
      apiGet<Enrollment[]>(`${root}/enrollments`),
      apiGet<Submission[]>(`${root}/submissions`),
      apiGet<Attendance[]>(`${root}/attendance`),
      apiGet<Mentorship[]>(`${root}/mentorships`),
      apiGet<CourseReport>(`${root}/progress`),
    ]);
    setEnrollments(applications);
    setSubmissions(work);
    setAttendance(attendanceRows);
    setMentorships(mentoring);
    setReport(courseReport);
  }, [courseId, organizationId]);

  useEffect(() => {
    if (!courseId || !organizationId) return;
    setError("");
    refreshReports().catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Staff permissions are required to view learning operations."));
    apiGet<{
      title: string;
      description: string;
      modules: ModuleChoice[];
    }>(
      `/organizations/${organizationId}/learning/courses/${courseId}/curriculum`,
    ).then((outline) => {
      setCurriculum(outline);
      setModules(outline.modules);
    }).catch(() => {
      setCurriculum(null);
      setModules([]);
    });
  }, [courseId, organizationId, refreshReports]);

  async function exportProgrammeOutcomes() {
    if (!organizationId || !selectedProgrammeId) return;
    setError("");
    try {
      const response = await fetch(
        `/api/backend/organizations/${organizationId}/learning/programmes/${selectedProgrammeId}/outcomes/export`,
        { credentials: "same-origin", cache: "no-store" },
      );
      if (!response.ok) {
        throw new Error(`Unable to export programme outcomes (${response.status}).`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `programme-${selectedProgrammeId}-outcomes.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to export programme outcomes.");
    }
  }

  async function loadProgrammeOutcomes() {
    if (!organizationId || !selectedProgrammeId) return;
    setError("");
    setProgrammeOutcomes(null);
    try {
      const result = await apiGet<ProgrammeOutcomes>(
        `/organizations/${organizationId}/learning/programmes/${selectedProgrammeId}/outcomes`,
      );
      setProgrammeOutcomes(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load programme outcomes.");
    }
  }

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
        programme_id: data.get("programme_id") || null,
        delivery_mode: data.get("delivery_mode"),
      });
      const next = [...courses, created];
      setCourses(next);
      setCourseId(created.id);
    });
  }

  async function updateCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!courseId) return;
    const data = new FormData(event.currentTarget);
    await action("Draft course details updated.", async () => {
      const updated = await apiPatch<Course>(base + `/courses/${courseId}`, {
        title: data.get("title"),
        slug: data.get("slug"),
        description: data.get("description"),
        category: data.get("category") || null,
        programme_id: data.get("programme_id") || null,
        delivery_mode: data.get("delivery_mode"),
      });
      setCourses((current) => current.map((item) => item.id === updated.id ? updated : item));
    });
  }

  async function updateModule(moduleId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Draft module updated.", async () => {
      const updated = await apiPatch<ModuleChoice>(
        base + `/courses/${courseId}/modules/${moduleId}`,
        {
          title: data.get("title"),
          description: data.get("description") || null,
          position: Number(data.get("position")),
        },
      );
      setModules((current) => current.map((item) => item.id === moduleId ? updated : item)
        .sort((a, b) => a.position - b.position));
      setCurriculum((current) => current ? {
        ...current,
        modules: current.modules.map((item) => item.id === moduleId ? {
          ...item,
          ...updated,
        } : item).sort((a, b) => a.position - b.position),
      } : current);
    });
  }

  async function updateLesson(
    moduleId: string,
    lessonId: string,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Draft lesson updated.", async () => {
      const updated = await apiPatch<LessonChoice>(
        base + `/courses/${courseId}/lessons/${lessonId}`,
        {
          title: data.get("title"),
          content_type: data.get("content_type"),
          content: data.get("content") || null,
          resource_url: data.get("resource_url") || null,
          duration_minutes: data.get("duration_minutes")
            ? Number(data.get("duration_minutes"))
            : null,
          position: Number(data.get("position")),
        },
      );
      setCurriculum((current) => current ? {
        ...current,
        modules: current.modules.map((module) => ({
          ...module,
          lessons: module.lessons?.map((lesson) =>
            lesson.id === lessonId ? updated : lesson
          ).sort((a, b) => a.position - b.position),
        })),
      } : current);
    });
  }

  async function createModule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await action("Module added to the selected course.", async () => {
      const created = await apiPost<ModuleChoice & { course_id: string }>(
        base + `/courses/${courseId}/modules`,
        {
          title: data.get("title"),
          description: data.get("description") || null,
          position: Number(data.get("position")),
        },
      );
      setModules((current) => [...current, created].sort((a, b) => a.position - b.position));
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
    const form = event.currentTarget;
    const data = new FormData(form);
    await action("Assessment evaluation saved.", () => apiPost(
      base + `/submissions/${attemptId}/evaluate`,
      { score: Number(data.get("score")), feedback: data.get("feedback") || null },
    ));
    form.reset();
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

  async function recordBulkAttendance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const learnerIds = String(data.get("learner_ids") ?? "")
      .split(/[\\n,]+/)
      .map((value) => value.trim())
      .filter(Boolean);
    if (learnerIds.length === 0) {
      setError("Enter at least one learner ID.");
      return;
    }
    if (new Set(learnerIds).size !== learnerIds.length) {
      setError("Each learner ID must appear only once.");
      return;
    }
    await action("Bulk attendance recorded for " + learnerIds.length + " learners.", () =>
      apiPost(base + "/courses/" + courseId + "/attendance/bulk", {
        session_key: data.get("session_key"),
        session_title: data.get("session_title"),
        session_date: data.get("session_date"),
        learners: learnerIds.map((learner_id) => ({
          learner_id,
          attendance_status: data.get("attendance_status"),
        })),
      }),
    );
    event.currentTarget.reset();
  }
  async function closeMentorship(id: string, status: "completed" | "ended") {
    await action("Mentorship marked " + status + ".", () => apiPatch(
      base + "/courses/" + courseId + "/mentorships/" + id + "/status",
      { status },
    ));
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
              {courses.map((course) => <option key={course.id} value={course.id}>{course.title}{course.programme_id ? ` · ${programmes.find((item) => item.id === course.programme_id)?.title ?? "Linked programme"}` : ""} · {course.status}</option>)}
            </select>
          </div>
        )}
        <section className="staff-card" aria-labelledby="programme-outcomes-heading">
          <p className="eyebrow">PROGRAMME PERFORMANCE</p>
          <h2 id="programme-outcomes-heading">Programme outcomes</h2>
          <div className="staff-actions">
            <label>Programme
              <select value={selectedProgrammeId} onChange={(event) => setSelectedProgrammeId(event.target.value)}>
                <option value="">Choose a programme</option>
                {programmes.map((programme) => (
                  <option key={programme.id} value={programme.id}>{programme.title}</option>
                ))}
              </select>
            </label>
            <button className="secondary-action" disabled={!selectedProgrammeId} onClick={loadProgrammeOutcomes}>Load outcomes</button>
            <button className="secondary-action" disabled={!selectedProgrammeId} onClick={exportProgrammeOutcomes}>Export CSV</button>
          </div>
          {programmeOutcomes && (
            <>
              <div className="staff-grid">
                <article><strong>{programmeOutcomes.course_count}</strong><span>Courses</span></article>
                <article><strong>{programmeOutcomes.totals.learners}</strong><span>Enrolments</span></article>
                <article><strong>{programmeOutcomes.totals.completed}</strong><span>Completions</span></article>
                <article><strong>{programmeOutcomes.average_progress}%</strong><span>Average progress</span></article>
                <article><strong>{programmeOutcomes.totals.attendance_sessions}</strong><span>Workshop sessions</span></article>
                <article><strong>{programmeOutcomes.totals.active_mentorships}/{programmeOutcomes.totals.mentorship_assignments}</strong><span>Active mentorships</span></article>
                <article><strong>{programmeOutcomes.totals.pending_evaluations}</strong><span>Pending evaluations</span></article>
                <article><strong>{programmeOutcomes.totals.assessment_submissions}</strong><span>Assessment submissions</span></article>
              </div>
              {programmeOutcomes.courses.map((course) => (
                <article className="staff-record" key={course.course_id}>
                  <strong>{course.title}</strong>
                  <small>{course.status} · {course.learners} learners · {course.completed} completed · {course.average_progress}% average progress · {course.pending_evaluations} pending evaluations</small>
                </article>
              ))}
            </>
          )}
        </section>
        {report && (
          <section className="staff-card" aria-labelledby="course-report-heading">
            <p className="eyebrow">COURSE PERFORMANCE</p>
            <h2 id="course-report-heading">Delivery overview</h2>
            <div className="staff-grid">
              <article><strong>{report.learners}</strong><span>Applicants / learners</span></article>
              <article><strong>{report.approved}</strong><span>Approved enrolments</span></article>
              <article><strong>{report.completed}</strong><span>Completed learners</span></article>
              <article><strong>{report.average_progress}%</strong><span>Average progress</span></article>
              <article><strong>{report.attendance_sessions}</strong><span>Recorded sessions</span></article>
              <article><strong>{report.attendance_records}</strong><span>Attendance records</span></article>
              <article><strong>{report.active_mentorships}/{report.mentorship_assignments}</strong><span>Active mentorships</span></article>
              <article><strong>{report.pending_evaluations}</strong><span>Pending evaluations</span></article>
            </div>
            <h3>Attendance breakdown</h3>
            <p className="workspace-muted">Present: {report.attendance_by_status.present ?? 0} · Late: {report.attendance_by_status.late ?? 0} · Absent: {report.attendance_by_status.absent ?? 0} · Excused: {report.attendance_by_status.excused ?? 0}</p>
            <p className="workspace-muted">Assessment submissions: {report.assessment_submissions} · Evaluated: {report.evaluated_submissions}</p>
          </section>
        )}
        <div className="staff-grid">
          <section className="staff-card">
            <h2>Create course</h2>
            <form onSubmit={createCourse}>
              <label>Course title<input name="title" minLength={3} maxLength={240} required /></label>
              <label>URL slug<input name="slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" required /></label>
              <label>Description<textarea name="description" maxLength={12000} required /></label>
              <label>Category<input name="category" maxLength={100} /></label>
              <label>Programme<select name="programme_id" defaultValue=""><option value="">Standalone course</option>{programmes.map((programme) => <option key={programme.id} value={programme.id}>{programme.title} · {programme.status}</option>)}</select></label>
              <label>Delivery<select name="delivery_mode"><option value="blended">Blended</option><option value="online">Online</option><option value="in_person">In person</option></select></label>
              <button className="primary-action" disabled={busy}>Create draft</button>
            </form>
          </section>
          <section className="staff-card">
            <h2>Edit draft course</h2>
            {courses.find((course) => course.id === courseId)?.status !== "draft" ? (
              <p className="workspace-muted">Select a draft course to edit. Published courses are read-only.</p>
            ) : (
              <form onSubmit={updateCourse}>
                <label>Title<input name="title" minLength={3} maxLength={240} defaultValue={courses.find((course) => course.id === courseId)?.title ?? ""} required /></label>
                <label>Slug<input name="slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" defaultValue={courses.find((course) => course.id === courseId)?.slug ?? ""} required /></label>
                <label>Description<textarea name="description" maxLength={12000} defaultValue={courses.find((course) => course.id === courseId)?.description ?? ""} required /></label>
                <label>Category<input name="category" maxLength={100} defaultValue={courses.find((course) => course.id === courseId)?.category ?? ""} /></label>
                <label>Programme<select name="programme_id" defaultValue={courses.find((course) => course.id === courseId)?.programme_id ?? ""}><option value="">Standalone course</option>{programmes.map((programme) => <option key={programme.id} value={programme.id}>{programme.title}</option>)}</select></label>
                <label>Delivery<select name="delivery_mode" defaultValue={courses.find((course) => course.id === courseId)?.delivery_mode ?? "blended"}><option value="blended">Blended</option><option value="online">Online</option><option value="in_person">In person</option></select></label>
                <button className="primary-action" disabled={busy}>Save course changes</button>
              </form>
            )}
            {curriculum?.modules.map((module) => (
              <article className="staff-record" key={module.id}>
                <h3>Module {module.position}: {module.title}</h3>
                <form onSubmit={(event) => updateModule(module.id, event)}>
                  <label>Module title<input name="title" minLength={2} defaultValue={module.title} required /></label>
                  <label>Description<textarea name="description" defaultValue={module.description ?? ""} /></label>
                  <label>Position<input name="position" type="number" min="1" max="500" defaultValue={module.position} required /></label>
                  <button className="secondary-action" disabled={busy || courses.find((course) => course.id === courseId)?.status !== "draft"}>Save module</button>
                </form>
                {module.lessons?.map((lesson) => (
                  <form key={lesson.id} onSubmit={(event) => updateLesson(module.id, lesson.id, event)}>
                    <h4>Lesson {lesson.position}: {lesson.title}</h4>
                    <label>Title<input name="title" minLength={2} defaultValue={lesson.title} required /></label>
                    <label>Type<select name="content_type" defaultValue={lesson.content_type}><option value="text">Text</option><option value="video">Video</option><option value="document">Document</option><option value="link">Link</option><option value="workshop">Workshop</option></select></label>
                    <label>Content<textarea name="content" defaultValue={lesson.content ?? ""} /></label>
                    <label>Resource URL<input name="resource_url" type="url" defaultValue={lesson.resource_url ?? ""} /></label>
                    <label>Duration (minutes)<input name="duration_minutes" type="number" min="1" max="1440" defaultValue={lesson.duration_minutes ?? ""} /></label>
                    <label>Position<input name="position" type="number" min="1" max="500" defaultValue={lesson.position} required /></label>
                    <button className="secondary-action" disabled={busy || courses.find((course) => course.id === courseId)?.status !== "draft"}>Save lesson</button>
                  </form>
                ))}
              </article>
            ))}
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
              <label>Module<select name="module_id" required disabled={modules.length === 0}><option value="">Choose a module</option>{modules.map((module) => <option key={module.id} value={module.id}>{module.position}. {module.title}</option>)}</select></label>
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
                </form> : (
                  <>
                    <p>Latest score: {item.score}% · {item.feedback || "No feedback"}</p>
                    <details>
                      <summary>Revise evaluation</summary>
                      <form onSubmit={(event) => evaluate(event, item.id)}>
                        <label>Revised score (%)<input name="score" type="number" min="0" max="100" defaultValue={item.score ?? 0} required /></label>
                        <label>Updated feedback<textarea name="feedback" defaultValue={item.feedback ?? ""} /></label>
                        <button className="primary-action" disabled={busy}>Save revision</button>
                      </form>
                    </details>
                    {item.evaluation_history.length > 0 && (
                      <details>
                        <summary>Evaluation history ({item.evaluation_history.length})</summary>
                        <ol>
                          {item.evaluation_history.map((evaluation) => (
                            <li key={evaluation.id}>
                              <strong>{evaluation.score}%</strong>
                              <small>
                                {new Date(evaluation.evaluated_at).toLocaleString()} ·
                                reviewer {evaluation.evaluated_by}
                              </small>
                              <p>{evaluation.feedback || "No feedback recorded."}</p>
                              {evaluation.previous_score !== null && (
                                <small>Revised from {evaluation.previous_score}%</small>
                              )}
                            </li>
                          ))}
                        </ol>
                      </details>
                    )}
                  </>
                )}
              </article>
            ))}
          </section>
          <section className="staff-card">
            <h2>Mentorship assignments</h2>
            <form onSubmit={assignMentor}>
              <label>Mentor<select name="mentor_id" required defaultValue="">
                <option value="" disabled>Select an active mentor</option>
                {members.filter((member) => (member.roles ?? [member.role]).some((role) => ["admin", "founder", "executive", "programme_manager", "researcher"].includes(role))).map((member) => (
                  <option key={member.user_id} value={member.user_id}>{(member.roles ?? [member.role]).join(", ")} · {member.user_id}</option>
                ))}
              </select></label>
              <label>Mentee<select name="mentee_id" required defaultValue="">
                <option value="" disabled>Select an active mentee</option>
                {members.map((member) => (
                  <option key={member.user_id} value={member.user_id}>{member.role} · {member.user_id}</option>
                ))}
              </select></label>
              <label>Notes<textarea name="notes" /></label>
              <button className="primary-action" disabled={busy || !courseId}>Assign mentor</button>
            </form>
            {mentorships.map((item) => <article className="staff-record" key={item.id}><strong>{item.mentor_id} → {item.mentee_id}</strong><small>{item.status} · {item.notes || "No notes"}</small>{item.status === "active" && <div className="staff-actions"><button disabled={busy} onClick={() => closeMentorship(item.id, "completed")}>Complete</button><button disabled={busy} onClick={() => closeMentorship(item.id, "ended")}>End assignment</button></div>}</article>)}
          </section>
          <section className="staff-card">
            <h2>Attendance</h2>
            <a className="secondary-action" href={"/api/backend" + base + "/courses/" + courseId + "/attendance/export"}>Export attendance CSV</a>
            <form onSubmit={recordAttendance}>
              <label>Session key<input name="session_key" required /></label>
              <label>Session title<input name="session_title" required /></label>
              <label>Date<input name="session_date" type="date" required /></label>
              <label>Enrolled learner<select name="learner_id" required defaultValue="">
                <option value="" disabled>Select a learner</option>
                {enrollments.filter((item) => ["approved", "completed"].includes(item.status)).map((item) => (
                  <option key={item.learner_id} value={item.learner_id}>{item.learner_id} · {item.status}</option>
                ))}
              </select></label>
              <label>Status<select name="attendance_status"><option value="present">Present</option><option value="late">Late</option><option value="excused">Excused</option><option value="absent">Absent</option></select></label>
              <button className="primary-action" disabled={busy || !courseId}>Record attendance</button>
            </form>
            {attendance.map((item) => <article className="staff-record" key={item.id}><strong>{item.session_title}</strong><small>{item.session_date} · {item.learner_id} · {item.attendance_status}</small></article>)}            <h3>Workshop roll call</h3>
            <p className="workspace-muted">Record one session for multiple approved learners. Enter one learner ID per line or separate IDs with commas.</p>
            <form onSubmit={recordBulkAttendance}>
              <label>Session key<input name="session_key" required /></label>
              <label>Session title<input name="session_title" required /></label>
              <label>Date<input name="session_date" type="date" required /></label>
              <label>Learner IDs<textarea name="learner_ids" rows={6} placeholder="Paste learner IDs, one per line" required /></label>
              <label>Attendance status<select name="attendance_status"><option value="present">Present</option><option value="late">Late</option><option value="excused">Excused</option><option value="absent">Absent</option></select></label>
              <button className="primary-action" disabled={busy || !courseId}>Record workshop roll call</button>
            </form>
          </section>
        </div>
      </section>
    </main>
  );
}
