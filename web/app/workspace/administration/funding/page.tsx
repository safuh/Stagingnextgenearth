"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiGet, apiPatch, apiPost, clearSession } from "@/lib/api";

type Org = { id: string; name: string };
type Membership = { role: string; roles?: string[] };
type Opportunity = { id: string; title: string; donor_name: string; status: string; deadline: string | null; expected_amount: string | null; currency: string };
type Award = { id: string; title: string; donor_name: string; award_amount: string; currency: string; status: string; reporting_deadline: string | null; restrictions: string | null };
type BudgetLine = { id: string; name: string; budget_amount: string };
type Entry = { id: string; entry_type: string; amount: string; occurred_on: string; description: string; reference: string | null };
type Summary = { award_id: string; title: string; donor_name: string; currency: string; award_amount: string; budgeted_amount: string; pledged_amount: string; committed_amount: string; expenditure_amount: string; unallocated_amount: string; reporting_deadline: string | null; status: string };
type Programme = { id: string; title: string };
const roles = ["admin", "founder", "executive"];
const money = (amount: string, currency: string) => new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(amount));

export default function FundingWorkspacePage() {
  const [orgs, setOrgs] = useState<Org[]>([]), [orgId, setOrgId] = useState("");
  const [allowed, setAllowed] = useState(false), [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [awards, setAwards] = useState<Award[]>([]), [summary, setSummary] = useState<Summary[]>([]);
  const [programmes, setProgrammes] = useState<Programme[]>([]), [awardId, setAwardId] = useState("");
  const [budgets, setBudgets] = useState<BudgetLine[]>([]), [entries, setEntries] = useState<Entry[]>([]);
  const [error, setError] = useState(""), [notice, setNotice] = useState(""), [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);

  const load = useCallback(async (id: string) => {
    const mine = await apiGet<Membership>(`/organizations/${id}/memberships/me`);
    const permitted = (mine.roles?.length ? mine.roles : [mine.role]).some((role) => roles.includes(role));
    setAllowed(permitted);
    if (!permitted) return;
    const [o, a, r, p] = await Promise.all([
      apiGet<Opportunity[]>(`/organizations/${id}/funding/opportunities`),
      apiGet<Award[]>(`/organizations/${id}/funding/awards`),
      apiGet<Summary[]>(`/organizations/${id}/funding/report`),
      apiGet<Programme[]>(`/organizations/${id}/programmes`),
    ]);
    setOpportunities(o); setAwards(a); setSummary(r); setProgrammes(p);
    setAwardId((current) => a.some((item) => item.id === current) ? current : a[0]?.id ?? "");
  }, []);
  const loadAward = useCallback(async (id: string, selected: string) => {
    if (!selected) { setBudgets([]); setEntries([]); return; }
    const [b, e] = await Promise.all([
      apiGet<BudgetLine[]>(`/organizations/${id}/funding/awards/${selected}/budget-lines`),
      apiGet<Entry[]>(`/organizations/${id}/funding/awards/${selected}/ledger`),
    ]);
    setBudgets(b); setEntries(e);
  }, []);

  useEffect(() => { apiGet<Org[]>("/organizations").then((items) => { setOrgs(items); if (items[0]) setOrgId(items[0].id); else setError("No active organisation membership was found."); }).catch((e: unknown) => setError(e instanceof Error ? e.message : "Unable to load organisations.")).finally(() => setLoading(false)); }, []);
  useEffect(() => { if (orgId) load(orgId).catch((e: unknown) => setError(e instanceof Error ? e.message : "Unable to load funding records.")); }, [orgId, load]);
  useEffect(() => { if (orgId && awardId && allowed) loadAward(orgId, awardId).catch((e: unknown) => setError(e instanceof Error ? e.message : "Unable to load award details.")); }, [orgId, awardId, allowed, loadAward]);

  async function submit(event: FormEvent<HTMLFormElement>, path: string, message: string) {
    event.preventDefault(); const form = event.currentTarget, data = new FormData(form), payload: Record<string, string | null> = {};
    data.forEach((value, key) => { const valueText = String(value).trim(); payload[key] = valueText || null; });
    setBusy(true); setError(""); setNotice("");
    try { await apiPost(path, payload); form.reset(); await load(orgId); if (awardId) await loadAward(orgId, awardId); setNotice(message); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to save funding record."); }
    finally { setBusy(false); }
  }
  async function updateOpportunityStatus(item: Opportunity, status: string) {
    setBusy(true); setError("");
    try {
      await apiPatch(`/organizations/${orgId}/funding/opportunities/${item.id}`, { status });
      await load(orgId); setNotice("Opportunity stage updated.");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to update opportunity."); }
    finally { setBusy(false); }
  }
  async function updateAwardStatus(item: Award, status: string) {
    setBusy(true); setError("");
    try {
      await apiPatch(`/organizations/${orgId}/funding/awards/${item.id}`, { status });
      await load(orgId); setNotice("Award status updated.");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to update award."); }
    finally { setBusy(false); }
  }
  async function exportCsv() {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/backend/organizations/${orgId}/funding/report.csv`, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error(`Report export failed (${response.status}).`);
      const url = URL.createObjectURL(await response.blob()), anchor = document.createElement("a");
      anchor.href = url; anchor.download = "funding-report.csv"; anchor.click(); URL.revokeObjectURL(url); setNotice("Funding report exported.");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to export report."); }
    finally { setBusy(false); }
  }
  const selected = awards.find((item) => item.id === awardId);
  if (loading) return <main className="workspace-shell"><p>Loading funding workspace…</p></main>;
  return <main className="workspace-shell">
    <header className="workspace-topbar"><Link className="brand" href="/workspace">NextGen For Earth</Link><button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button></header>
    <section className="workspace-content">
      <p className="eyebrow">GRANTS, DONORS & FINANCIAL STEWARDSHIP</p><h1 className="workspace-title">Funding <em>management.</em></h1>
      <p className="workspace-muted">Track opportunities, awards, restricted budgets, pledges, commitments, expenditure and reporting deadlines. This is a financial register only: it does not process or move money.</p>
      <p><Link className="secondary-action" href="/workspace/administration">← Administration</Link></p>
      {orgs.length > 1 && <label>Organisation<select value={orgId} onChange={(e) => setOrgId(e.target.value)}>{orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>}
      {error && <p className="workspace-error" role="alert">{error}</p>}{notice && <p className="workspace-notice" role="status">{notice}</p>}
      {!allowed ? <section className="staff-card"><h2>Administrator access required</h2><p>Funding records are restricted to administrators, founders and executives.</p></section> : <>
        <div className="workspace-stats admin-stats"><article><span>OPEN OPPORTUNITIES</span><strong>{opportunities.filter((x) => !["declined", "closed", "awarded"].includes(x.status)).length}</strong><p>Prospects and applications</p></article><article><span>ACTIVE AWARDS</span><strong>{awards.filter((x) => x.status === "active").length}</strong><p>Current grant agreements</p></article><article><span>UPCOMING REPORTS</span><strong>{awards.filter((x) => x.reporting_deadline && new Date(x.reporting_deadline) >= new Date()).length}</strong><p>Reporting deadlines recorded</p></article></div>
        <div className="staff-grid admin-grid">
          <section className="staff-card"><h2>Register an opportunity</h2><form onSubmit={(e) => void submit(e, `/organizations/${orgId}/funding/opportunities`, "Opportunity saved.")}>
            <label>Opportunity title<input name="title" minLength={2} required /></label><label>Donor / funder<input name="donor_name" minLength={2} required /></label><label>Deadline<input name="deadline" type="date" /></label><label>Expected amount<input name="expected_amount" type="number" min="0" step="0.01" /></label><label>Currency<input name="currency" defaultValue="KES" minLength={3} maxLength={3} pattern="[A-Za-z]{3}" required /></label><label>Stage<select name="status">{["identified", "reviewing", "submitted", "awarded", "declined", "closed"].map((x) => <option key={x} value={x}>{x}</option>)}</select></label><label>Reference URL<input name="reference_url" type="url" /></label><label>Notes<textarea name="description" rows={3} /></label><button className="primary-action" disabled={busy}>Save opportunity</button>
          </form></section>
          <section className="staff-card"><h2>Register an award</h2><form onSubmit={(e) => void submit(e, `/organizations/${orgId}/funding/awards`, "Award saved.")}>
            <label>Award title<input name="title" minLength={2} required /></label><label>Donor / funder<input name="donor_name" minLength={2} required /></label><label>Opportunity<select name="opportunity_id"><option value="">Not linked</option>{opportunities.map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}</select></label><label>Award amount<input name="award_amount" type="number" min="0.01" step="0.01" required /></label><label>Currency<input name="currency" defaultValue="KES" minLength={3} maxLength={3} pattern="[A-Za-z]{3}" required /></label><label>Start date<input name="start_date" type="date" /></label><label>End date<input name="end_date" type="date" /></label><label>Reporting deadline<input name="reporting_deadline" type="date" /></label><label>Status<select name="status">{["draft", "active", "suspended", "completed", "closed"].map((x) => <option key={x} value={x}>{x}</option>)}</select></label><label>Restrictions<textarea name="restrictions" rows={3} /></label><button className="primary-action" disabled={busy}>Save award</button>
          </form></section>
        </div>
        <section className="staff-card admin-member-section"><h2>Funding opportunities ({opportunities.length})</h2>{opportunities.length ? opportunities.map((item) => <article className="admin-member-row" key={item.id}><div className="admin-member-meta"><strong>{item.title}</strong><span>{item.donor_name} · {item.expected_amount ? money(item.expected_amount, item.currency) : "Amount not estimated"} · Deadline: {item.deadline ?? "Not set"}</span></div><label>Stage<select value={item.status} disabled={busy} onChange={(event) => void updateOpportunityStatus(item, event.target.value)}>{["identified", "reviewing", "submitted", "awarded", "declined", "closed"].map((status) => <option key={status} value={status}>{status}</option>)}</select></label></article>) : <p className="workspace-muted">No funding opportunities registered.</p>}</section>
        <section className="staff-card admin-member-section"><div className="section-heading"><div><p className="eyebrow">GRANT PORTFOLIO</p><h2>Funding awards</h2></div><button className="secondary-action" disabled={busy || !summary.length} onClick={() => void exportCsv()}>Export CSV</button></div>
          {summary.length === 0 ? <p className="workspace-muted">No awards have been registered yet.</p> : summary.map((row) => <article className="admin-member-row" key={row.award_id}><div className="admin-member-meta"><strong>{row.title}</strong><span>{row.donor_name} · {row.status} · Report due: {row.reporting_deadline ?? "Not set"}</span><span>Award {money(row.award_amount, row.currency)} · Budgeted {money(row.budgeted_amount, row.currency)} · Pledged {money(row.pledged_amount, row.currency)} · Committed {money(row.committed_amount, row.currency)} · Spent {money(row.expenditure_amount, row.currency)}</span></div><label>Award status<select value={row.status} disabled={busy} onChange={(event) => { const item = awards.find((award) => award.id === row.award_id); if (item) void updateAwardStatus(item, event.target.value); }}>{["draft", "active", "suspended", "completed", "closed"].map((status) => <option key={status} value={status}>{status}</option>)}</select></label><button className="secondary-action" onClick={() => setAwardId(row.award_id)}>Manage budget & ledger</button></article>)}
        </section>
        {selected && <section className="staff-card admin-member-section"><p className="eyebrow">AWARD MANAGEMENT</p><h2>{selected.title}</h2><p className="workspace-muted">{selected.donor_name} · {money(selected.award_amount, selected.currency)} · {selected.restrictions || "No restrictions recorded"}</p>
          <div className="staff-grid admin-grid"><section><h3>Allocate budget line</h3><form onSubmit={(e) => void submit(e, `/organizations/${orgId}/funding/awards/${awardId}/budget-lines`, "Budget line saved.")}><label>Category<input name="name" minLength={2} required /></label><label>Amount<input name="budget_amount" type="number" min="0" step="0.01" required /></label><label>Programme<select name="programme_id"><option value="">Organisation-wide</option>{programmes.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></label><label>Description<textarea name="description" rows={2} /></label><button className="primary-action" disabled={busy}>Add budget line</button></form></section>
            <section><h3>Record financial entry</h3><form onSubmit={(e) => void submit(e, `/organizations/${orgId}/funding/awards/${awardId}/ledger`, "Funding entry recorded.")}><label>Type<select name="entry_type"><option value="pledge">Pledge</option><option value="commitment">Commitment</option><option value="expenditure">Expenditure</option></select></label><label>Amount<input name="amount" type="number" min="0.01" step="0.01" required /></label><label>Date<input name="occurred_on" type="date" required /></label><label>Budget line<select name="budget_line_id"><option value="">Not allocated</option>{budgets.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label><label>Reference<input name="reference" maxLength={120} /></label><label>Description<textarea name="description" rows={2} minLength={2} required /></label><button className="primary-action" disabled={busy}>Record entry</button></form></section></div>
          <h3>Budget lines</h3>{budgets.length ? budgets.map((b) => <p key={b.id}>{b.name} — {money(b.budget_amount, selected.currency)}</p>) : <p className="workspace-muted">No budget allocations recorded.</p>}
          <h3>Ledger history</h3>{entries.length ? entries.map((entry) => <article className="admin-audit-row" key={entry.id}><strong>{entry.entry_type} · {money(entry.amount, selected.currency)}</strong><small>{entry.occurred_on}{entry.reference ? ` · ${entry.reference}` : ""}</small><p>{entry.description}</p></article>) : <p className="workspace-muted">No pledges, commitments or expenditure recorded.</p>}
        </section>}
      </>}
    </section>
  </main>;
}
