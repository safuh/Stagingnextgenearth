"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, clearSession, hasSession } from "@/lib/api";

interface Organization { id: string; name: string; country_code: string; }
interface Membership { role: string; status: string; }
interface Programme { id: string; title: string; summary: string | null; status: string; start_date: string | null; end_date: string | null; }
interface Indicator { indicator: { id: string; title: string; unit: string; direction: string; baseline_value: number | null; target_value: number | null }; latest_measurement: { value: number; period_start: string; period_end: string } | null; progress_percent: number | null; }
interface Participation { id: string; participant_group: string; group_name: string; participant_count: number; period_start: string; period_end: string; }

export default function PartnerWorkspacePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [indicators, setIndicators] = useState<Record<string, Indicator[]>>({});
  const [participation, setParticipation] = useState<Record<string, Participation[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hasSession()) { setError("Your sign-in session is unavailable. Please sign in again."); setLoading(false); return; }
    apiGet<Organization[]>("/organizations")
      .then((items) => { setOrganizations(items); if (items[0]) setOrganizationId(items[0].id); })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    let active = true;
    setMembership(null); setProgrammes([]); setIndicators({}); setParticipation({}); setError("");
    Promise.all([
      apiGet<Membership>(`/organizations/${organizationId}/memberships/me`),
      apiGet<Programme[]>(`/organizations/${organizationId}/programmes`),
    ]).then(async ([member, items]) => {
      if (!active) return;
      if (member.role !== "institutional_partner" || member.status !== "active") {
        setError("This portal is available to active institutional-partner members."); return;
      }
      setMembership(member); setProgrammes(items);
      const results = await Promise.all(items.map(async (programme) => {
        const [indicatorRows, participationRows] = await Promise.all([
          apiGet<Indicator[]>(`/organizations/${organizationId}/programmes/${programme.id}/indicators`),
          apiGet<Participation[]>(`/organizations/${organizationId}/programmes/${programme.id}/participation`),
        ]);
        return [programme.id, indicatorRows, participationRows] as const;
      }));
      if (!active) return;
      setIndicators(Object.fromEntries(results.map(([id, rows]) => [id, rows])));
      setParticipation(Object.fromEntries(results.map(([id, , rows]) => [id, rows])));
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load partner reporting.");
    });
    return () => { active = false; };
  }, [organizationId]);

  if (loading) return <main className="workspace-shell"><p>Loading partner workspace…</p></main>;
  const participationTotal = Object.values(participation).flat().reduce((sum, item) => sum + item.participant_count, 0);
  const indicatorCount = Object.values(indicators).reduce((sum, rows) => sum + rows.length, 0);

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">INSTITUTIONAL PARTNER PORTAL</p>
        <h1 className="workspace-title">Shared goals.<br /><em>Measured impact.</em></h1>
        <p className="workspace-intro">A read-only view of programme delivery, aggregate participation and reported indicators for your organisation.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {organizations.length > 0 && <>
          <label className="org-label" htmlFor="partner-organization">Active organisation</label>
          <select id="partner-organization" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
            {organizations.map((org) => <option key={org.id} value={org.id}>{org.name} · {org.country_code}</option>)}
          </select>
        </>}
        {membership && <>
          <section className="role-workspace"><div><span className="eyebrow">PARTNER ACCESS</span><h2>Institutional partner</h2><p>This dashboard presents programme-level and cohort-level reporting. It does not expose volunteer applications, learner records or individual attendance.</p></div><div className="role-workspace-links"><Link href="/workspace">Organisation workspace →</Link></div></section>
          <div className="research-metrics" aria-label="Partner reporting summary">
            <article><span>Programmes</span><strong>{programmes.length}</strong></article>
            <article><span>Reported indicators</span><strong>{indicatorCount}</strong></article>
            <article><span>Aggregate participants</span><strong>{participationTotal.toLocaleString()}</strong></article>
            <article><span>Reporting groups</span><strong>{Object.values(participation).flat().length}</strong></article>
          </div>
          <section className="research-section">
            <div className="section-heading"><div><p className="eyebrow">DELIVERY & OUTCOMES</p><h2>Programme reporting</h2></div></div>
            {programmes.length === 0 ? <p className="workspace-muted">No programmes are available in this organisation.</p> : <div className="research-record-grid">
              {programmes.map((programme) => <article className="research-record" key={programme.id}>
                <div className="research-record-top"><span className="status-chip">{programme.status}</span><span>{(participation[programme.id] || []).length} cohort reports</span></div>
                <h3>{programme.title}</h3><p>{programme.summary || "No programme summary has been published."}</p>
                <h4>Indicators</h4>
                {(indicators[programme.id] || []).length === 0 ? <p>No indicators have been reported.</p> : (indicators[programme.id] || []).map((row) => <div className="partner-indicator" key={row.indicator.id}>
                  <strong>{row.indicator.title}</strong><span>{row.latest_measurement ? `${row.latest_measurement.value.toLocaleString()} ${row.indicator.unit} · ${row.latest_measurement.period_start} to ${row.latest_measurement.period_end}` : "No measurement reported"}</span>
                  {row.indicator.target_value !== null && <small>Target: {row.indicator.target_value.toLocaleString()} {row.indicator.unit}{row.progress_percent !== null ? ` · ${row.progress_percent}% progress` : ""}</small>}
                </div>)}
                <h4>Aggregate participation</h4>
                {(participation[programme.id] || []).length === 0 ? <p>No cohort totals have been reported.</p> : <div className="partner-participation">{(participation[programme.id] || []).map((row) => <div key={row.id}><strong>{row.group_name}</strong><span>{row.participant_count.toLocaleString()} · {row.participant_group.replace(/_/g, " ")}</span><small>{row.period_start} to {row.period_end}</small></div>)}</div>}
              </article>)}
            </div>}
          </section>
          <p className="workspace-muted">Figures are reported by programme teams and are not independently verified by this dashboard. Corrections should be requested from the programme owner.</p>
        </>}
      </section>
    </main>
  );
}
