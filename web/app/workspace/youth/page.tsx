"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { apiGet, apiPost, clearSession, hasSession } from "@/lib/api";

interface Organization { id: string; name: string; country_code: string; }
interface Membership { role: string; status: string; }
interface Programme { id: string; title: string; summary: string | null; status: string; start_date: string | null; end_date: string | null; }
interface Course { id: string; title: string; description: string; category: string | null; delivery_mode: string; status: string; }
interface Progress { course_id: string; enrollment_status: string; progress_percent: number; completed_lesson_ids: string[]; assessments: Array<{ assessment_id: string; score: number | null; feedback: string | null }>; }
interface Application { id: string; programme_id: string; participation_type: string; status: string; availability: string | null; review_note: string | null; }
interface Allocation { id: string; programme_title: string; activity_title: string; activity_description: string | null; location: string | null; start_at: string; end_at: string | null; activity_status: string; allocation_status: string; }
interface Mentorship { id: string; course_title: string; relationship: string; status: string; notes: string | null; }
interface Attendance { id: string; course_title: string; session_title: string; session_date: string; attendance_status: string; }

export default function YouthWorkspacePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [progress, setProgress] = useState<Progress[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [mentorships, setMentorships] = useState<Mentorship[]>([]);
  const [attendance, setAttendance] = useState<Attendance[]>([]);
  const [applicationProgrammeId, setApplicationProgrammeId] = useState("");
  const [participationType, setParticipationType] = useState<"volunteer" | "ambassador">("volunteer");
  const [interest, setInterest] = useState("");
  const [availabilityText, setAvailabilityText] = useState("");
  const [applicationBusy, setApplicationBusy] = useState(false);
  const [applicationNotice, setApplicationNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hasSession()) {
      setError("Your sign-in session is unavailable. Please sign in again.");
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
    setMembership(null);
    setProgress([]);
    Promise.all([
      apiGet<Membership>(`/organizations/${organizationId}/memberships/me`),
      apiGet<Programme[]>(`/organizations/${organizationId}/programmes`),
      apiGet<Course[]>(`/organizations/${organizationId}/learning/courses`),
      apiGet<Application[]>(`/organizations/${organizationId}/my-volunteer-applications`),
      apiGet<Allocation[]>(`/organizations/${organizationId}/my-volunteer-allocations`),
      apiGet<Mentorship[]>(`/organizations/${organizationId}/learning/my-mentorships`),
      apiGet<Attendance[]>(`/organizations/${organizationId}/learning/my-attendance`),
    ]).then(async ([member, programmeItems, courseItems, applicationItems, allocationItems, mentorshipItems, attendanceItems]) => {
      if (!active) return;
      if (member.role !== "youth_volunteer" || member.status !== "active") {
        setError("This workspace is available to active youth-volunteer members.");
        return;
      }
      setMembership(member);
      setProgrammes(programmeItems);
      setCourses(courseItems);
      setApplications(applicationItems);
      setAllocations(allocationItems);
      setMentorships(mentorshipItems);
      setAttendance(attendanceItems);
      const results = await Promise.all(courseItems.map(async (course) => {
        try {
          return await apiGet<Progress>(`/organizations/${organizationId}/learning/courses/${course.id}/my-progress`);
        } catch {
          return null;
        }
      }));
      if (active) setProgress(results.filter((item): item is Progress => item !== null));
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load your volunteer workspace.");
    });
    return () => { active = false; };
  }, [organizationId]);

  async function submitProgrammeApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationProgrammeId || interest.trim().length < 20) return;
    setApplicationBusy(true);
    setError("");
    setApplicationNotice("");
    try {
      const result = await apiPost<Application>(
        `/organizations/${organizationId}/programmes/${applicationProgrammeId}/volunteer-applications`,
        { participation_type: participationType, interest: interest.trim(), availability: availabilityText.trim() || null },
      );
      setApplications((current) => [result, ...current]);
      setApplicationProgrammeId("");
      setInterest("");
      setAvailabilityText("");
      setApplicationNotice("Your programme application has been submitted. Its status will appear in your application history.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit this programme application.");
    } finally {
      setApplicationBusy(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading your volunteer workspace…</p></main>;

  const completedCourses = progress.filter((item) => item.enrollment_status === "completed").length;
  const enrolledCourses = progress.filter((item) => ["approved", "completed"].includes(item.enrollment_status)).length;
  const averageProgress = progress.length ? Math.round(progress.reduce((sum, item) => sum + item.progress_percent, 0) / progress.length) : 0;
  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">YOUTH & VOLUNTEER PORTAL</p>
        <h1 className="workspace-title">Your learning.<br /><em>Your contribution.</em></h1>
        <p className="workspace-intro">A private view of your course progress, volunteer assignments and programme application history.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {organizations.length === 0 && !error ? (
          <div className="workspace-empty"><h2>No organisation access yet</h2><p>Ask an organisation administrator about membership and programme applications.</p></div>
        ) : (
          <>
            <label className="org-label" htmlFor="youth-organization">Active organisation</label>
            <select id="youth-organization" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
              {organizations.map((org) => <option value={org.id} key={org.id}>{org.name} · {org.country_code}</option>)}
            </select>
            {membership && (
              <>
                <section className="role-workspace">
                  <div><span className="eyebrow">YOUR MEMBERSHIP</span><h2>Youth volunteer</h2><p>Your personal records are loaded using your authenticated account. Other members&apos; application, learning and attendance records are not returned.</p></div>
                  <div className="role-workspace-links"><Link href="/workspace">Organisation workspace →</Link></div>
                </section>
                <div className="research-metrics" aria-label="Your learning summary">
                  <article><span>Available courses</span><strong>{courses.length}</strong></article>
                  <article><span>Approved enrolments</span><strong>{enrolledCourses}</strong></article>
                  <article><span>Completed courses</span><strong>{completedCourses}</strong></article>
                  <article><span>Average progress</span><strong>{averageProgress}%</strong></article>
                </div>
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">LEARNING</p><h2>Courses and progress</h2></div><Link href="/workspace#learning">Open learning catalogue →</Link></div>
                  {courses.length === 0 ? <p className="workspace-muted">No published courses are currently available.</p> : (
                    <div className="research-record-grid">{courses.map((course) => {
                      const item = progress.find((record) => record.course_id === course.id);
                      return <article className="research-record" key={course.id}>
                        <div className="research-record-top"><span className="status-chip">{item?.enrollment_status || "not enrolled"}</span><span>{course.delivery_mode.replace(/_/g, " ")}</span></div>
                        <h3>{course.title}</h3><p>{course.description}</p>
                        <div className="progress-track" role="progressbar" aria-label={`${course.title} progress`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={item?.progress_percent || 0}><span style={{ width: `${item?.progress_percent || 0}%` }} /></div>
                        <small>{item?.progress_percent ?? 0}% complete · {item?.completed_lesson_ids.length ?? 0} lessons completed</small>
                      </article>;
                    })}</div>
                  )}
                </section>
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">PROGRAMME PARTICIPATION</p><h2>Volunteer assignments</h2></div><span>{allocations.length} assignments</span></div>
                  {allocations.length === 0 ? <p className="workspace-muted">You have no activity assignments yet. Your programme team will add assignments when activities are scheduled.</p> : (
                    <div className="research-record-grid">{allocations.map((item) => <article className="research-record" key={item.id}>
                      <div className="research-record-top"><span className="status-chip">{item.allocation_status}</span><span>{item.activity_status.replace(/_/g, " ")}</span></div>
                      <h3>{item.activity_title}</h3><p>{item.activity_description || item.programme_title}</p>
                      <dl><div><dt>Programme</dt><dd>{item.programme_title}</dd></div><div><dt>When</dt><dd>{new Date(item.start_at).toLocaleString()}</dd></div><div><dt>Location</dt><dd>{item.location || "To be confirmed"}</dd></div></dl>
                    </article>)}</div>
                  )}
                </section>
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">APPLICATION HISTORY</p><h2>Volunteer applications</h2></div><span>{applications.length} records</span></div>
                  {applications.length === 0 ? <p className="workspace-muted">No volunteer applications are recorded for this organisation.</p> : (
                    <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Participation</th><th>Status</th><th>Availability</th><th>Review note</th></tr></thead><tbody>{applications.map((item) => <tr key={item.id}><td>{item.participation_type}</td><td><span className="status-chip">{item.status}</span></td><td>{item.availability || "—"}</td><td>{item.review_note || "—"}</td></tr>)}</tbody></table></div>
                  )}
                </section>
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">SUPPORT & ATTENDANCE</p><h2>Mentorship and sessions</h2></div></div>
                  <div className="research-record-grid">
                    <article className="research-record"><h3>Mentorship</h3>{mentorships.length === 0 ? <p>No mentorship assignments yet.</p> : mentorships.map((item) => <p key={item.id}><strong>{item.course_title}</strong> · {item.relationship} · {item.status}{item.notes ? ` — ${item.notes}` : ""}</p>)}</article>
                    <article className="research-record"><h3>Attendance</h3>{attendance.length === 0 ? <p>No attendance records yet.</p> : attendance.map((item) => <p key={item.id}><strong>{item.session_title}</strong> · {item.course_title} · {item.session_date} · {item.attendance_status}</p>)}</article>
                  </div>
                </section>
                <section className="research-section"><div className="section-heading"><div><p className="eyebrow">PROGRAMMES</p><h2>Organisation programmes</h2></div><span>{programmes.length} records</span></div>
                  <div className="research-record-grid">{programmes.map((programme) => <article className="research-record" key={programme.id}><span className="status-chip">{programme.status}</span><h3>{programme.title}</h3><p>{programme.summary || "Programme details have not been published."}</p>
                      {applications.some((item) => item.programme_id === programme.id && ["pending", "approved"].includes(item.status)) ? <small>You already have an active application for this programme.</small> : applicationProgrammeId === programme.id ? (
                        <form className="volunteer-application-form" onSubmit={submitProgrammeApplication}>
                          <label>Participation type<select value={participationType} onChange={(event) => setParticipationType(event.target.value as "volunteer" | "ambassador")}><option value="volunteer">Volunteer</option><option value="ambassador">Ambassador</option></select></label>
                          <label>Why are you interested?<textarea required minLength={20} maxLength={5000} value={interest} onChange={(event) => setInterest(event.target.value)} placeholder="Describe the contribution you would like to make (at least 20 characters)." /></label>
                          <label>Availability (optional)<input maxLength={500} value={availabilityText} onChange={(event) => setAvailabilityText(event.target.value)} placeholder="e.g. Weekends or school holidays" /></label>
                          <div className="staff-actions"><button type="submit" disabled={applicationBusy || interest.trim().length < 20}>{applicationBusy ? "Submitting…" : "Submit application"}</button><button type="button" onClick={() => setApplicationProgrammeId("")}>Cancel</button></div>
                        </form>
                      ) : <button className="secondary-action" type="button" onClick={() => { setApplicationProgrammeId(programme.id); setApplicationNotice(""); }}>Apply to participate</button>}</article>)}</div>
                  {applicationNotice && <p className="workspace-notice" role="status">{applicationNotice}</p>}
                </section>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}
