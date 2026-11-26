"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost, clearSession, restoreSession } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

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
  lessons: Lesson[];
}
interface Curriculum {
  course_id: string;
  title: string;
  description: string;
  modules: Module[];
}
interface Progress {
  enrollment_status: string;
  progress_percent: number;
  certificate_id: string | null;
  certificate_number: string | null;
  certificate_status: string | null;
  completed_lesson_ids: string[];
  assessments: Array<{
    assessment_id: string;
    score: number | null;
    feedback: string | null;
    evaluated_at: string | null;
  }>;
}
interface Assessment {
  id: string;
  title: string;
  assessment_type: string;
  instructions: string;
  pass_mark: number;
  due_at: string | null;
  automated: boolean;
}
interface QuizOption { id: string; text: string }
interface QuizQuestion { id: string; prompt: string; points: number; options: QuizOption[] }
interface Quiz { id: string; title: string; instructions: string; pass_mark: number; questions: QuizQuestion[] }
interface QuizResult { id: string; score: number; passed: boolean; pass_mark: number; earned_points: number; total_points: number }
interface Resource {
  id: string;
  title: string;
  resource_type: string;
  description: string | null;
  resource_url: string | null;
}

export default function LearnerClassroomPage() {
  const params = useParams<{ course_id: string }>();
  const courseId = params.course_id;
  const [organizationId, setOrganizationId] = useState("");
  const [curriculum, setCurriculum] = useState<Curriculum | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [certificateCode, setCertificateCode] = useState("");
  const [quizzes, setQuizzes] = useState<Record<string, Quiz>>({});
  const [quizAnswers, setQuizAnswers] = useState<Record<string, Record<string, string>>>({});
  const [quizResults, setQuizResults] = useState<Record<string, QuizResult>>({});

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const session = await restoreSession();
        if (!session) throw new Error("Sign in through the learner portal to access your classroom.");
        const organization = await apiGet<{ id: string }>(
          `/public/organizations/${ORGANIZATION_SLUG}`,
        );
        if (!active) return;
        setOrganizationId(organization.id);
        const root = `/organizations/${organization.id}/learning`;
        const [outline, learnerProgress, courseAssessments, courseResources] = await Promise.all([
          apiGet<Curriculum>(`${root}/courses/${courseId}/curriculum`),
          apiGet<Progress>(`${root}/courses/${courseId}/my-progress`),
          apiGet<Assessment[]>(`${root}/courses/${courseId}/assessments`),
          apiGet<Resource[]>(`${root}/courses/${courseId}/resources`),
        ]);
        if (!active) return;
        setCurriculum(outline);
        setProgress(learnerProgress);
        setAssessments(courseAssessments);
        setResources(courseResources);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Unable to load this classroom.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [courseId]);

  async function refreshProgress() {
    if (!organizationId) return;
    const updated = await apiGet<Progress>(
      `/organizations/${organizationId}/learning/courses/${courseId}/my-progress`,
    );
    setProgress(updated);
  }

  async function completeLesson(lesson: Lesson) {
    if (!organizationId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await apiPost<{
        status: string;
        progress_percent: number;
        verification_code: string | null;
      }>(`/organizations/${organizationId}/learning/lessons/${lesson.id}/complete`, {});
      await refreshProgress();
      if (result.verification_code) setCertificateCode(result.verification_code);
      setNotice(`“${lesson.title}” marked complete. Your progress has been updated.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record lesson completion.");
    } finally {
      setBusy(false);
    }
  }

  async function loadQuiz(assessment: Assessment) {
    if (!organizationId) return;
    setBusy(true);
    setError("");
    try {
      const quiz = await apiGet<Quiz>(
        `/organizations/${organizationId}/learning/assessments/${assessment.id}/quiz`,
      );
      setQuizzes((current) => ({ ...current, [assessment.id]: quiz }));
      setQuizAnswers((current) => ({ ...current, [assessment.id]: {} }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load this quiz.");
    } finally {
      setBusy(false);
    }
  }

  function setQuizAnswer(assessmentId: string, questionId: string, optionId: string) {
    setQuizAnswers((current) => ({
      ...current,
      [assessmentId]: { ...(current[assessmentId] ?? {}), [questionId]: optionId },
    }));
  }

  async function submitQuiz(event: FormEvent<HTMLFormElement>, assessment: Assessment) {
    event.preventDefault();
    if (!organizationId) return;
    const quiz = quizzes[assessment.id];
    const answers = quizAnswers[assessment.id] ?? {};
    if (!quiz || quiz.questions.some((question) => !answers[question.id])) {
      setError("Choose an answer for every question before submitting.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await apiPost<QuizResult>(
        `/organizations/${organizationId}/learning/assessments/${assessment.id}/quiz-attempts`,
        { answers },
      );
      setQuizResults((current) => ({ ...current, [assessment.id]: result }));
      setNotice(`Quiz submitted: ${result.score}% — ${result.passed ? "pass" : "not yet passed"}.`);
      await refreshProgress();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit this quiz.");
    } finally {
      setBusy(false);
    }
  }

  async function submitAssessment(event: FormEvent<HTMLFormElement>, assessment: Assessment) {
    event.preventDefault();
    if (!organizationId) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const response = String(data.get("response") ?? "").trim();
    if (!response) {
      setError("Enter your response before submitting.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiPost(
        `/organizations/${organizationId}/learning/assessments/${assessment.id}/submissions`,
        { submission: { response } },
      );
      setNotice(`Your response to “${assessment.title}” has been submitted for review.`);
      form.reset();
      await refreshProgress();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit this assessment.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="workspace-shell"><section className="workspace-content"><p>Loading your classroom…</p></section></main>;

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <nav className="learner-top-nav" aria-label="Classroom navigation">
          <Link className="secondary-action" href="/learners">My learning</Link>
          <button className="workspace-signout" type="button" onClick={() => { clearSession(); window.location.assign("/learners"); }}>Sign out</button>
        </nav>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">LEARNER CLASSROOM</p>
        <h1 className="workspace-title">{curriculum?.title ?? "Course classroom"}</h1>
        {curriculum && (
          <section className="learner-course-intro">
            <div>
              <p className="eyebrow">NEXTGEN LEARNING / PILOT TRACK</p>
              <p>{curriculum.description}</p>
            </div>
            <div className="learner-course-intro-stats">
              <span><strong>{curriculum.modules.length}</strong> modules</span>
              <span><strong>{curriculum.modules.reduce((sum, module) => sum + module.lessons.length, 0)}</strong> lessons</span>
              <span><strong>{curriculum.modules.reduce((sum, module) => sum + module.lessons.reduce((minutes, lesson) => minutes + (lesson.duration_minutes ?? 0), 0), 0)}</strong> guided minutes</span>
            </div>
          </section>
        )}
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {!curriculum || !progress ? (
          <section className="staff-card">
            <h2>Classroom access unavailable</h2>
            <p className="workspace-muted">This course requires an approved application and an active learner membership. If your application was just approved, return to your learning dashboard and try again.</p>
            <Link href="/learners">Return to learner portal</Link>
          </section>
        ) : (
          <>
            <section className="staff-card">
              <h2>Your course progress</h2>
              <p className="workspace-muted">{progress.enrollment_status.replaceAll("_", " ")} · {progress.progress_percent}% complete</p>
              <progress value={progress.progress_percent} max={100} aria-label="Course completion" />
              {progress.certificate_id && progress.certificate_status === "valid" && (
                <p role="status">
                  Certificate {progress.certificate_number} is ready. {" "}
                  <a
                    className="primary-action"
                    href={`/api/backend/organizations/${organizationId}/learning/certificates/${progress.certificate_id}/download`}
                  >Download certificate PDF</a>{" "}
                  <Link href={certificateCode ? `/certificates/verify?code=${encodeURIComponent(certificateCode)}` : "/certificates/verify"}>
                    Verify credential
                  </Link>
                </p>
              )}
            </section>
            <section className="staff-card learner-curriculum-section">
              <div className="section-heading"><h2>Course curriculum</h2><span>{curriculum.modules.length} modules · {curriculum.modules.reduce((sum, module) => sum + module.lessons.length, 0)} lessons</span></div>
              {curriculum.modules.length === 0 ? <p className="workspace-muted">Course materials are being prepared.</p> : curriculum.modules.map((module, moduleIndex) => {
                const completedInModule = module.lessons.filter((lesson) =>
                  progress.completed_lesson_ids.includes(lesson.id)
                ).length;
                return (
                  <article className="learner-module-card" key={module.id}>
                    <div className="learner-module-heading">
                      <p className="eyebrow">MODULE {String(moduleIndex + 1).padStart(2, "0")} / {module.lessons.length} LESSONS</p>
                      <span>{completedInModule}/{module.lessons.length} complete</span>
                    </div>
                    <h3>{module.title}</h3>
                    {module.description && <p className="portal-description">{module.description}</p>}
                    <progress value={completedInModule} max={Math.max(1, module.lessons.length)} aria-label={`${module.title} progress`} />
                    {module.lessons.map((lesson, lessonIndex) => {
                      const completed = progress.completed_lesson_ids.includes(lesson.id);
                      return (
                        <div className="learner-lesson-card" key={lesson.id}>
                          <p className="portal-tag">LESSON {String(lessonIndex + 1).padStart(2, "0")} · {lesson.content_type.replaceAll("_", " ")}{lesson.duration_minutes ? ` · ${lesson.duration_minutes} min` : ""}</p>
                          <h4>{lesson.title}</h4>
                          {lesson.content && <p className="learner-lesson-content">{lesson.content}</p>}
                          {lesson.resource_url && <p><a href={lesson.resource_url} target="_blank" rel="noreferrer">Open lesson resource</a></p>}
                          <button className="primary-action" disabled={busy || completed} onClick={() => void completeLesson(lesson)}>
                            {completed ? "Completed" : busy ? "Saving…" : "Mark lesson complete"}
                          </button>
                        </div>
                      );
                    })}
                  </article>
                );
              })}
            </section>
            <section className="staff-card">
              <h2>Assessments</h2>
              {assessments.length === 0 ? <p className="workspace-muted">There are no assessments for this course yet.</p> : assessments.map((assessment) => (
                <article className="portal-card" key={assessment.id}>
                  <p className="portal-tag">{assessment.assessment_type.replaceAll("_", " ")} · Pass mark {assessment.pass_mark}%</p>
                  <h3>{assessment.title}</h3>
                  <p className="portal-description">{assessment.instructions}</p>
                  {assessment.due_at && <p className="workspace-muted">Due {new Date(assessment.due_at).toLocaleString()}</p>}
                  {assessment.automated ? (
                    <>
                      {!quizzes[assessment.id] && !quizResults[assessment.id] && (
                        <button className="primary-action" disabled={busy} onClick={() => void loadQuiz(assessment)}>
                          {busy ? "Loading…" : "Start quiz"}
                        </button>
                      )}
                      {quizzes[assessment.id] && !quizResults[assessment.id] && (
                        <form onSubmit={(event) => void submitQuiz(event, assessment)}>
                          {quizzes[assessment.id].questions.map((question, questionIndex) => (
                            <fieldset key={question.id} className="portal-card">
                              <legend><strong>{questionIndex + 1}. {question.prompt}</strong> · {question.points} point(s)</legend>
                              {question.options.map((option) => (
                                <label key={option.id}>
                                  <input
                                    type="radio"
                                    name={`${assessment.id}-${question.id}`}
                                    value={option.id}
                                    checked={quizAnswers[assessment.id]?.[question.id] === option.id}
                                    onChange={() => setQuizAnswer(assessment.id, question.id, option.id)}
                                  />
                                  {option.text}
                                </label>
                              ))}
                            </fieldset>
                          ))}
                          <button className="primary-action" disabled={busy}>
                            {busy ? "Submitting…" : "Submit quiz"}
                          </button>
                        </form>
                      )}
                      {quizResults[assessment.id] && (
                        <p className="workspace-notice" role="status">
                          Result: {quizResults[assessment.id].score}% · {quizResults[assessment.id].passed ? "Passed" : "Not passed"}
                        </p>
                      )}
                    </>
                  ) : (
                    <form onSubmit={(event) => void submitAssessment(event, assessment)}>
                      <label htmlFor={`response-${assessment.id}`}>Your response</label>
                      <textarea id={`response-${assessment.id}`} name="response" rows={5} maxLength={20000} required />
                      <button className="primary-action" disabled={busy}>{busy ? "Submitting…" : "Submit for review"}</button>
                    </form>
                  )}
                </article>
              ))}
              {progress.assessments.map((attempt, index) => (
                <p className="workspace-muted" key={`${attempt.assessment_id}-${index}`}>
                  Assessment result: {attempt.score === null ? "Awaiting review" : `${attempt.score}%`}
                  {attempt.feedback ? ` · ${attempt.feedback}` : ""}
                </p>
              ))}
            </section>
            <section className="staff-card">
              <h2>Learning resources</h2>
              {resources.length === 0 ? <p className="workspace-muted">No additional resources have been attached.</p> : resources.map((resource) => (
                <article className="portal-card" key={resource.id}>
                  <p className="portal-tag">{resource.resource_type.replaceAll("_", " ")}</p>
                  <h3>{resource.title}</h3>
                  {resource.description && <p className="portal-description">{resource.description}</p>}
                  {resource.resource_url && <a href={resource.resource_url} target="_blank" rel="noreferrer">Open resource</a>}
                </article>
              ))}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
