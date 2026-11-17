"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiGet, clearSession, hasSession } from "@/lib/api";

type Org = { id: string; name: string };
type Membership = { id: string; user_id: string; role: string; roles?: string[]; status: string };
type Programme = { id: string; title: string; status: string; start_date: string | null; end_date: string | null };
type Partner = { id: string; name: string; relationship_status: string; verification_state: string; visibility: string };
type Content = { id: string; title: string; content_type: string; publication_state: string; source_url: string | null };
type Study = { id: string; title: string; status: string; study_type: string | null; lead_researcher_id: string };
type Course = { id: string; title: string; status: string };
type Summary = { organization_id: string; organization_name: string; owner_user_id: string; created_at: string };
type DeliverySummary = { programme_id: string; activities_total: number; activities_planned: number; activities_in_progress: number; activities_completed: number; volunteers_assigned: number; volunteers_completed: number; attendance_total: number; attendance_present: number };
type ResearchProposal = { id: string; title: string; status: string; version_number: number; submitted_at: string | null };
type ResearchMilestone = { id: string; title: string; status: string; progress_percent: number; due_date: string | null };
type ResearchGovernance = { study: Study; proposals: ResearchProposal[]; milestones: ResearchMilestone[] };

export default function ExecutiveOverviewPage() {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgId, setOrgId] = useState("");
  const [role, setRole] = useState("");
  const [members, setMembers] = useState<Membership[]>([]);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [content, setContent] = useState<Content[]>([]);
  const [studies, setStudies] = useState<Study[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [delivery, setDelivery] = useState<Record<string, DeliverySummary>>({});
  const [researchGovernance, setResearchGovernance] = useState<ResearchGovernance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(async (id: string) => {
    const mine = await apiGet<Membership>(`/organizations/${id}/memberships/me`);
    const assignedRoles = mine.roles?.length ? mine.roles : [mine.role];
    setRole(assignedRoles.join(" · "));
    if (!assignedRoles.some((item) => ["admin", "founder", "executive"].includes(item))) {
      throw new Error("The executive overview is restricted to administrators, founders and executives.");
    }
    const [memberRows, programmeRows, partnerRows, contentRows, studyRows, courseRows, orgSummary] = await Promise.all([
      apiGet<Membership[]>(`/organizations/${id}/memberships`),
      apiGet<Programme[]>(`/organizations/${id}/programmes`),
      apiGet<Partner[]>(`/organizations/${id}/partners`),
      apiGet<Content[]>(`/organizations/${id}/content`),
      apiGet<Study[]>(`/organizations/${id}/research-studies`),
      apiGet<Course[]>(`/organizations/${id}/learning/courses`),
      apiGet<Summary>(`/organizations/${id}/administration-summary`),
    ]);
    // Secondary governance and delivery panels must not take down the core
    // executive snapshot when a newly added endpoint is unavailable or one
    // record has incomplete data.
    const governanceRows = await Promise.all(studyRows.slice(0, 8).map(async study => {
      const base = `/organizations/${id}/research-studies/${study.id}`;
      const [proposalResult, milestoneResult] = await Promise.allSettled([
        apiGet<ResearchProposal[]>(`${base}/proposals`),
        apiGet<ResearchMilestone[]>(`${base}/milestones`),
      ]);
      return {
        study,
        proposals: proposalResult.status === "fulfilled" ? proposalResult.value : [],
        milestones: milestoneResult.status === "fulfilled" ? milestoneResult.value : [],
      };
    }));
    const deliveryResults = await Promise.allSettled(programmeRows.slice(0, 8).map(async programme => {
      const item = await apiGet<DeliverySummary>(`/organizations/${id}/programmes/${programme.id}/delivery-summary`);
      return [programme.id, item] as const;
    }));
    const deliveryRows = deliveryResults.flatMap(result =>
      result.status === "fulfilled" ? [result.value] : []
    );
    setMembers(memberRows); setProgrammes(programmeRows); setPartners(partnerRows);
    setContent(contentRows); setStudies(studyRows); setCourses(courseRows); setSummary(orgSummary);
    setDelivery(Object.fromEntries(deliveryRows));
    setResearchGovernance(governanceRows);
    setLastUpdated(new Date());
  }, []);

  useEffect(() => {
    if (!hasSession()) { setError("Your sign-in session is not available. Please sign in again."); setLoading(false); return; }
    apiGet<Org[]>("/organizations").then(items => {
      setOrgs(items);
      if (items[0]) setOrgId(items[0].id);
      else setError("No active organisation membership was found.");
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    let active = true;
    setError("");
    load(orgId).catch((e: unknown) => { if (active) setError(e instanceof Error ? e.message : "Unable to load executive overview."); });
    return () => { active = false; };
  }, [orgId, load]);

  const count = (state: string, rows = content) => rows.filter(row => row.publication_state === state).length;
  if (loading) return <main className="workspace-shell"><p>Loading executive overview…</p></main>;

  return <main className="workspace-shell">
    <header className="workspace-topbar">
      <Link className="brand" href="/workspace"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
      <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
    </header>
    <section className="workspace-content">
      <p className="eyebrow">ORGANISATION PERFORMANCE · {role.replaceAll("_", " ").toUpperCase()}</p>
      <h1 className="workspace-title">Executive <em>overview.</em></h1><button className="primary-action print-briefing" type="button" onClick={() => window.print()}>Print / save founder briefing</button>
      <p className="workspace-muted">A consolidated view of programme delivery, research, institutional relationships, people and public communications. Counts reflect records currently held in the portal; they are not independent impact verification.</p>
      <p><Link className="secondary-action" href="/workspace">← Workspace</Link> · <Link className="secondary-action" href="/workspace/administration">Administration</Link> · <Link className="secondary-action" href="/workspace/administration/content">CMS review queue</Link></p>
      {orgs.length > 1 && <label className="admin-org-picker">Organisation<select value={orgId} onChange={e => setOrgId(e.target.value)}>{orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>}
      {error && <p className="workspace-error" role="alert">{error}</p>}
      {summary && <>
        <p className="workspace-muted">{summary.organization_name} · Owner account: {summary.owner_user_id}</p>
        <div className="workspace-stats admin-stats">
          <article><span>ACTIVE MEMBERS</span><strong>{members.filter(m => m.status === "active").length}</strong><p>{members.filter(m => m.status === "invited").length} invitations pending</p></article>
          <article><span>ACTIVE PROGRAMMES</span><strong>{programmes.filter(p => p.status === "active").length}</strong><p>{programmes.length} total programme records</p></article>
          <article><span>RESEARCH STUDIES</span><strong>{studies.length}</strong><p>{studies.filter(s => s.status === "active").length} marked active</p></article>
          <article><span>TRAINING COURSES</span><strong>{courses.length}</strong><p>Course catalogue records</p></article>
          <article><span>PARTNER RECORDS</span><strong>{partners.length}</strong><p>{partners.filter(p => p.verification_state !== "verified").length} awaiting verification</p></article>
          <article><span>CMS REVIEW QUEUE</span><strong>{count("review")}</strong><p>{count("approved")} approved · {count("published")} published</p></article>
        </div>
        <div className="staff-grid admin-grid">
          <section className="staff-card">
            <div className="section-heading"><div><p className="eyebrow">PROGRAMME PORTFOLIO</p><h2>Programme status</h2></div><Link className="secondary-action" href="/workspace/programmes">Manage</Link></div>
            {programmes.length === 0 ? <p className="workspace-muted">No programme records yet.</p> : programmes.slice(0, 8).map(p => <article className="admin-member-row" key={p.id}><div className="admin-member-meta"><strong>{p.title}</strong><span>{p.status}{p.start_date ? " · starts "+p.start_date : ""}{p.end_date ? " · ends "+p.end_date : ""}</span></div></article>)}
          </section>
          <section className="staff-card">
            <div className="section-heading"><div><p className="eyebrow">PROGRAMME DELIVERY</p><h2>Operational activity</h2></div><Link className="secondary-action" href="/workspace/programmes">Open programmes</Link></div>
            {programmes.length === 0 ? <p className="workspace-muted">Delivery activity will appear when programmes are created.</p> : programmes.slice(0, 8).map(p => {
              const d = delivery[p.id];
              return <article className="admin-member-row" key={p.id}><div className="admin-member-meta"><strong>{p.title}</strong><span>{d ? d.activities_completed + "/" + d.activities_total + " activities completed · " + d.volunteers_completed + "/" + d.volunteers_assigned + " volunteer assignments completed · " + d.attendance_present + "/" + d.attendance_total + " present" : "No delivery records yet."}</span></div></article>;
            })}
            <p className="workspace-muted">Operational counts are taken from recorded activities, volunteer allocations and attendance registers. They are not estimates of environmental or social impact.</p>
          </section>
          <section className="staff-card">
            <div className="section-heading"><div><p className="eyebrow">RESEARCH PORTFOLIO</p><h2>Studies</h2></div></div>
            {studies.length === 0 ? <p className="workspace-muted">No research studies have been registered.</p> : studies.slice(0, 8).map(s => <article className="admin-member-row" key={s.id}><div className="admin-member-meta"><strong>{s.title}</strong><span>{s.study_type || "Study"} · {s.status} · Lead: {s.lead_researcher_id}</span></div></article>)}
          </section>
          <section className="staff-card">
            <div className="section-heading"><div><p className="eyebrow">RESEARCH GOVERNANCE</p><h2>Proposals & milestones</h2></div><Link className="secondary-action" href="/workspace/research">Research workspace</Link></div>
            {researchGovernance.length === 0 ? <p className="workspace-muted">No research governance records are available.</p> : researchGovernance.map(({ study, proposals, milestones }) => {
              const submitted = proposals.filter(item => item.status === "submitted").length;
              const completed = milestones.filter(item => item.status === "completed").length;
              const overdue = milestones.filter(item => item.due_date && item.due_date < new Date().toISOString().slice(0, 10) && item.status !== "completed" && item.status !== "cancelled").length;
              return <article className="admin-member-row" key={study.id}><div className="admin-member-meta"><strong>{study.title}</strong><span>{submitted} proposals awaiting review · {completed}/{milestones.length} milestones completed · {overdue} overdue milestones</span></div></article>;
            })}
            <p className="workspace-muted">Proposal and milestone counts reflect study governance records. Overdue means a due date before today with a status other than completed or cancelled.</p>
          </section>
          <section className="staff-card">
            <div className="section-heading"><div><p className="eyebrow">INSTITUTIONAL RELATIONSHIPS</p><h2>Partners</h2></div><Link className="secondary-action" href="/workspace/administration/partners">Manage</Link></div>
            {partners.length === 0 ? <p className="workspace-muted">No partner records yet.</p> : partners.slice(0, 8).map(p => <article className="admin-member-row" key={p.id}><div className="admin-member-meta"><strong>{p.name}</strong><span>{p.relationship_status} · {p.verification_state} · {p.visibility}</span></div></article>)}
          </section>
          <section className="staff-card">
            <div className="section-heading"><div><p className="eyebrow">PUBLIC COMMUNICATIONS</p><h2>CMS pipeline</h2></div><Link className="secondary-action" href="/workspace/administration/content">Review</Link></div>
            {["review","approved","published","draft"].map(state => <article className="admin-member-row" key={state}><div className="admin-member-meta"><strong>{state.replaceAll("_"," ")}</strong><span>{count(state)} records</span></div></article>)}
            <p className="workspace-muted">Only published CMS records are exposed through the public content feed.</p>
          </section>
        </div>
        <section className="staff-card admin-member-section">
          <div className="section-heading"><div><p className="eyebrow">PEOPLE & CAPACITY</p><h2>Organisation membership</h2></div><Link className="secondary-action" href="/workspace/administration">Manage access</Link></div>
          {members.slice(0, 12).map(m => <article className="admin-member-row" key={m.id}><div className="admin-member-meta"><strong>{m.user_id}</strong><span>{(m.roles?.length ? m.roles : [m.role]).map(item => item.replaceAll("_", " ")).join(" · ")} · {m.status}</span></div></article>)}
          <p className="workspace-muted">Public directory profiles are managed separately from login memberships; this panel reports only accounts with organisation access.</p>
        </section>
        <p className="workspace-muted">Last refreshed: {lastUpdated?.toLocaleString() ?? "—"}. Reload the page to refresh the snapshot.</p>
      </>}
    </section>
  </main>;
}
