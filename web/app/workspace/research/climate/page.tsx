"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { apiGet, apiPost, hasSession } from "@/lib/api";

type Organisation = { id: string; name: string; country_code: string };
type Membership = { user_id: string; role: string; roles?: string[]; status: string };
type IngestionRun = {
  id: string; provider_id: string; source_name: string; licence: string | null;
  requested_start: string; requested_end: string; requested_area: Record<string, number> | null;
  status: string; records_received: number; records_inserted: number; records_skipped: number;
  error_summary: string | null; started_at: string; finished_at: string | null;
};
type Observation = {
  id: string; observed_at: string; variable: string; value: number; unit: string;
  latitude: number; longitude: number; source: string; quality_status: string;
};
type Release = {
  id: string; slug: string; version: number; title: string; summary: string;
  indicator: string; unit: string; provider_id: string; provider_product: string;
  data_class: string; geography_label: string; geography_resolution: string;
  period_start: string; period_end: string; state: string; license_name: string;
  created_by: string; reviewed_by: string | null; published_at: string | null;
};
type QualitySummary = { total: number; by_status: Record<string, number>; by_variable: Record<string, number> };

type Stage = "collect" | "verify" | "publish";

const labelForState: Record<string, string> = {
  draft: "Draft", review: "Awaiting review", approved: "Approved", published: "Published",
  superseded: "Superseded", retracted: "Retracted",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(value));
}

export default function ClimateResearchStudioPage() {
  const [organisations, setOrganisations] = useState<Organisation[]>([]);
  const [organisationId, setOrganisationId] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [stage, setStage] = useState<Stage>("collect");
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [quality, setQuality] = useState<QualitySummary | null>(null);
  const [releases, setReleases] = useState<Release[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [provider, setProvider] = useState("chirps-v3");
  const [variant, setVariant] = useState("sat");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-01-03");
  const [west, setWest] = useState("39.7");
  const [south, setSouth] = useState("-3.8");
  const [east, setEast] = useState("40.0");
  const [north, setNorth] = useState("-3.5");
  const [areaLabel, setAreaLabel] = useState("Kilifi coastal study area, Kenya");
  const [reviewNote, setReviewNote] = useState("Provider metadata, requested extent, date range and sample values checked.");
  const [releaseTitle, setReleaseTitle] = useState("Daily rainfall signal — Kilifi");
  const [releaseSlug, setReleaseSlug] = useState("kilifi-daily-rainfall");
  const [releaseSummary, setReleaseSummary] = useState("Daily precipitation estimates derived from CHIRPS v3 satellite data over the selected Kilifi County area.");
  const [limitations, setLimitations] = useState("Satellite-derived precipitation estimates are not direct station measurements. Spatial averaging can mask local variation. This release is descriptive and does not establish climate-health causation or individual risk.");
  const [uncertainty, setUncertainty] = useState("CHIRPS estimates have product-specific uncertainty and may differ from local gauge measurements.");

  const roles = useMemo(() => membership?.roles?.length ? membership.roles : membership?.role ? [membership.role] : [], [membership]);
  const canAuthor = roles.some((role) => ["admin", "founder", "executive", "researcher"].includes(role));
  const canQualityReview = roles.some((role) => ["admin", "programme_manager"].includes(role));
  const canReleaseReview = roles.some((role) => ["admin", "founder", "executive", "programme_manager"].includes(role));
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null;
  const verifiedCount = quality?.by_status.verified ?? 0;
  const pendingCount = quality?.by_status.pending ?? 0;
  const publishedCount = releases.filter((release) => release.state === "published").length;
  const publishableRuns = runs.filter((run) => run.status === "completed" && run.records_inserted > 0 && run.verified_observations === run.records_inserted && Boolean(run.licence));

  const loadWorkspace = useCallback(async (orgId: string) => {
    const [member, runItems, qualitySummary, releaseItems] = await Promise.all([
      apiGet<Membership>(`/organizations/${orgId}/memberships/me`),
      apiGet<IngestionRun[]>(`/organizations/${orgId}/climate-ingestion?limit=50`),
      apiGet<QualitySummary>(`/organizations/${orgId}/climate-observations/quality-summary`),
      apiGet<Release[]>(`/organizations/${orgId}/climate-public-releases?limit=100`),
    ]);
    if (member.status !== "active") throw new Error("An active organisation membership is required.");
    setMembership(member);
    setRuns(runItems);
    setQuality(qualitySummary);
    setReleases(releaseItems);
    const eligible = runItems.find((run) => run.status === "completed" && run.records_inserted > 0);
    setSelectedRunId((current) => current && runItems.some((run) => run.id === current) ? current : eligible?.id ?? "");
  }, []);

  useEffect(() => {
    if (!hasSession()) {
      setError("Sign in to access the climate research studio.");
      setLoading(false);
      return;
    }
    apiGet<Organisation[]>("/organizations")
      .then((items) => {
        setOrganisations(items);
        if (items[0]) setOrganisationId(items[0].id);
        else setError("No organisation workspace is linked to this account.");
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Unable to load organisations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!organisationId) return;
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      apiGet<Membership>(`/organizations/${organisationId}/memberships/me`),
      apiGet<IngestionRun[]>(`/organizations/${organisationId}/climate-ingestion?limit=50`),
      apiGet<QualitySummary>(`/organizations/${organisationId}/climate-observations/quality-summary`),
      apiGet<Release[]>(`/organizations/${organisationId}/climate-public-releases?limit=100`),
    ]).then(([member, runItems, qualitySummary, releaseItems]) => {
      if (!active) return;
      if (member.status !== "active") throw new Error("An active organisation membership is required.");
      setMembership(member);
      setRuns(runItems);
      setQuality(qualitySummary);
      setReleases(releaseItems);
      const eligible = runItems.find((run) => run.status === "completed" && run.records_inserted > 0);
      setSelectedRunId(eligible?.id ?? "");
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load climate workspace.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [organisationId]);

  useEffect(() => {
    if (!organisationId || !selectedRunId) { setObservations([]); return; }
    let active = true;
    apiGet<Observation[]>(
      `/organizations/${organisationId}/climate-observations?ingestion_run_id=${encodeURIComponent(selectedRunId)}&limit=12`,
    ).then((items) => { if (active) setObservations(items); })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Unable to load observation sample."); });
    return () => { active = false; };
  }, [organisationId, selectedRunId]);

  async function refresh(orgId = organisationId) {
    await loadWorkspace(orgId);
  }

  async function runIngestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organisationId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const start = new Date(`${startDate}T00:00:00Z`);
      const end = new Date(`${endDate}T23:59:59Z`);
      const daySpan = Math.ceil((end.getTime() - start.getTime()) / 86400000);
      if (daySpan < 1 || daySpan > 7) throw new Error("Choose a date window between 1 and 7 days for this synchronous ingestion workflow.");
      const area = { west: Number(west), south: Number(south), east: Number(east), north: Number(north) };
      if (!(area.west < area.east && area.south < area.north)) throw new Error("The bounding box must have west < east and south < north.");
      const result = await apiPost<IngestionRun>(
        `/organizations/${organisationId}/climate-ingestion`,
        { provider, start: start.toISOString(), end: end.toISOString(), area, chirps_variant: variant },
      );
      setNotice(`Provider run completed: ${result.records_inserted.toLocaleString()} observations inserted. They remain pending quality review.`);
      await refresh();
      setSelectedRunId(result.id);
      setStage("verify");
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Provider ingestion failed.");
    } finally { setBusy(false); }
  }

  async function reviewRun(decision: "verified" | "rejected") {
    if (!organisationId || !selectedRunId) return;
    if (!window.confirm(`Apply '${decision}' to every pending observation in this provider run? This action is audited and cannot be undone.`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiPost<{ reviewed_count: number }>(
        `/organizations/${organisationId}/climate-ingestion/${selectedRunId}/review`,
        { decision, note: reviewNote },
      );
      setNotice(`${result.reviewed_count.toLocaleString()} observations ${decision} by your account.`);
      await refresh();
      const updatedSample = await apiGet<Observation[]>(
        `/organizations/${organisationId}/climate-observations?ingestion_run_id=${encodeURIComponent(selectedRunId)}&limit=12`,
      );
      setObservations(updatedSample);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Quality review failed.");
    } finally { setBusy(false); }
  }

  async function createRelease(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organisationId || !selectedRun) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiPost<Release>(
        `/organizations/${organisationId}/climate-public-releases`,
        {
          slug: releaseSlug, title: releaseTitle, summary: releaseSummary,
          provider_id: selectedRun.provider_id, data_class: "satellite_estimate",
          geography_label: areaLabel, geography_resolution: "0.05° CHIRPS grid; area mean per day",
          period_start: selectedRun.requested_start, period_end: selectedRun.requested_end,
          baseline: null, uncertainty_summary: uncertainty, limitations,
          citation_url: "https://doi.org/10.15780/G2JQ0P",
          source_ingestion_run_id: selectedRun.id,
        },
      );
      setNotice(`Release draft created as version ${result.version}. Continue through independent review and publication.`);
      await refresh();
      setStage("publish");
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Release draft could not be created.");
    } finally { setBusy(false); }
  }

  async function transitionRelease(release: Release, action: "submit" | "approve" | "publish" | "retract") {
    if (!organisationId) return;
    const note = action === "retract" ? window.prompt("Enter a substantive retraction reason (minimum 5 characters):") : null;
    if (action === "retract" && (!note || note.trim().length < 5)) return;
    if (action === "publish" && !window.confirm("Publish this independently approved climate release to the public website?")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(
        `/organizations/${organisationId}/climate-public-releases/${release.id}/${action}`,
        { note: note ?? `Workflow action: ${action}` },
      );
      setNotice(`Release '${release.title}' moved to ${labelForState[action === "submit" ? "review" : action === "approve" ? "approved" : action === "publish" ? "published" : "retracted"]}.`);
      await refresh();
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Release workflow action failed.");
    } finally { setBusy(false); }
  }

  const activeReleases = releases.filter((release) => !["superseded", "retracted"].includes(release.state));

  return (
    <main className="climate-studio">
      <header className="climate-studio-topbar">
        <Link className="climate-brand" href="/workspace/research"><span className="climate-brand-mark">N</span> NEXTGEN <i>FOR EARTH</i></Link>
        <nav aria-label="Research workspace navigation">
          <Link href="/workspace">Workspace</Link>
          <Link href="/workspace/research">Research</Link>
          <Link href="/climate-intelligence">Public climate hub <span aria-hidden="true">↗</span></Link>
        </nav>
      </header>
      <div className="climate-studio-layout">
        <aside className="climate-studio-rail">
          <p className="climate-rail-label">RESEARCH SYSTEMS / 04</p>
          <h2>Climate<br /><em>studio.</em></h2>
          <p className="climate-rail-copy">A governed path from provider signal to publishable evidence.</p>
          <div className="climate-stage-nav" aria-label="Climate workflow stages">
            {([
              ["collect", "01", "Collect", "Provider ingestion"],
              ["verify", "02", "Verify", "Quality review"],
              ["publish", "03", "Release", "Public evidence"],
            ] as const).map(([key, number, title, detail]) => (
              <button key={key} className={stage === key ? "active" : ""} onClick={() => setStage(key)}>
                <span>{number}</span><strong>{title}</strong><small>{detail}</small>
              </button>
            ))}
          </div>
          <div className="climate-rail-foot">
            <span className="climate-live-dot" /> GOVERNED DATA / AUDITED ACTIONS
          </div>
        </aside>
        <section className="climate-studio-main">
          <div className="climate-studio-head">
            <div>
              <p className="climate-kicker">FIELD INTELLIGENCE / ORGANISATION WORKSPACE</p>
              <h1>{stage === "collect" ? "Collect the signal." : stage === "verify" ? "Interrogate the evidence." : "Publish with provenance."}</h1>
              <p>Provider-backed climate evidence, quality review and public release governance in one workflow.</p>
            </div>
            <label className="climate-org-picker">WORKING ORGANISATION
              <select value={organisationId} onChange={(event) => setOrganisationId(event.target.value)}>
                {organisations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
              </select>
            </label>
          </div>

          {error && <p className="climate-alert climate-alert-error" role="alert">{error}</p>}
          {notice && <p className="climate-alert climate-alert-success" role="status">{notice}</p>}
          {loading ? <div className="climate-skeleton" role="status">Loading climate systems…</div> : (
            <>
              <div className="climate-metrics">
                <article><span>INGESTION RUNS</span><strong>{runs.length}</strong><small>Provider retrieval history</small></article>
                <article><span>VERIFIED RECORDS</span><strong>{verifiedCount.toLocaleString()}</strong><small>Independently reviewed</small></article>
                <article><span>AWAITING REVIEW</span><strong>{pendingCount.toLocaleString()}</strong><small>Not eligible for release</small></article>
                <article><span>PUBLIC RELEASES</span><strong>{publishedCount}</strong><small>Visible on public hub</small></article>
              </div>

              {stage === "collect" && (
                <div className="climate-work-grid">
                  <section className="climate-panel climate-panel-feature">
                    <div className="climate-panel-head"><span>01 / PROVIDER RETRIEVAL</span><span className="climate-panel-index">CH-03</span></div>
                    <h2>Pull a new climate signal</h2>
                    <p>Retrieve daily rainfall estimates from CHIRPS v3. Data is stored as pending observations; ingestion never implies quality approval.</p>
                    {!canAuthor ? <p className="climate-lock">Your membership does not include provider-ingestion permissions.</p> : (
                      <form className="climate-form" onSubmit={runIngestion}>
                        <label>Provider<select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="chirps-v3">CHIRPS v3 / daily rainfall</option></select></label>
                        <label>Product variant<select value={variant} onChange={(event) => setVariant(event.target.value)}><option value="sat">Satellite estimate / SAT</option></select></label>
                        <div className="climate-form-pair">
                          <label>Start date<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} required /></label>
                          <label>End date<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} required /></label>
                        </div>
                        <label>Area label<input value={areaLabel} onChange={(event) => setAreaLabel(event.target.value)} required /></label>
                        <p className="climate-form-caption">WGS84 bounding box / decimal degrees</p>
                        <div className="climate-bounds-grid">
                          <label>West<input inputMode="decimal" value={west} onChange={(event) => setWest(event.target.value)} required /></label>
                          <label>South<input inputMode="decimal" value={south} onChange={(event) => setSouth(event.target.value)} required /></label>
                          <label>East<input inputMode="decimal" value={east} onChange={(event) => setEast(event.target.value)} required /></label>
                          <label>North<input inputMode="decimal" value={north} onChange={(event) => setNorth(event.target.value)} required /></label>
                        </div>
                        <div className="climate-form-note"><strong>Request guardrails</strong><span>Maximum 7 days per request · one bounded area · no arbitrary URLs · provider licence retained.</span></div>
                        <button className="climate-primary" type="submit" disabled={busy}>{busy ? "Retrieving provider data…" : "Run provider ingestion"} <span>↗</span></button>
                      </form>
                    )}
                  </section>
                  <aside className="climate-side-panel">
                    <p className="climate-kicker">RECENT ACTIVITY</p><h3>Ingestion ledger</h3>
                    {runs.length === 0 ? <p className="climate-muted">No provider runs yet. Start with a bounded CHIRPS request.</p> : runs.slice(0, 7).map((run) => (
                      <button className="climate-run-row" key={run.id} onClick={() => { setSelectedRunId(run.id); setStage("verify"); }}>
                        <span><strong>{run.source_name}</strong><small>{formatDate(run.started_at)} · {run.records_inserted.toLocaleString()} records</small></span>
                        <i className={run.status === "completed" ? "is-good" : "is-warn"}>{run.status}</i>
                      </button>
                    ))}
                    <div className="climate-side-note"><strong>Data integrity</strong><p>Provider data is kept separate from field observations and remains private until quality-reviewed and explicitly released.</p></div>
                  </aside>
                </div>
              )}

              {stage === "verify" && (
                <div className="climate-work-grid">
                  <section className="climate-panel climate-panel-feature">
                    <div className="climate-panel-head"><span>02 / QUALITY REVIEW</span><span className="climate-panel-index">QA-02</span></div>
                    <h2>Review a provider run</h2>
                    <p>Inspect the retrieval metadata and a sample of observations before recording an independent, auditable quality decision.</p>
                    <label className="climate-select-label">SELECT PROVIDER RUN<select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)}><option value="">Choose a provider run</option>{runs.map((run) => <option key={run.id} value={run.id}>{run.source_name} · {formatDate(run.started_at)} · {run.records_inserted} records</option>)}</select></label>
                    {selectedRun && (
                      <>
                        <div className="climate-run-facts">
                          <div><small>Provider</small><strong>{selectedRun.source_name}</strong></div>
                          <div><small>Licence</small><strong>{selectedRun.licence ?? "Not recorded"}</strong></div>
                          <div><small>Inserted</small><strong>{selectedRun.records_inserted.toLocaleString()}</strong></div>
                          <div><small>Verified / pending</small><strong>{selectedRun.verified_observations.toLocaleString()} / {selectedRun.pending_observations.toLocaleString()}</strong></div>
                          <div><small>Skipped</small><strong>{selectedRun.records_skipped.toLocaleString()}</strong></div>
                          <div><small>Requested start</small><strong>{formatDate(selectedRun.requested_start)}</strong></div>
                          <div><small>Requested end</small><strong>{formatDate(selectedRun.requested_end)}</strong></div>
                        </div>
                        <div className="climate-sample-head"><strong>Observation sample</strong><span>First 12 records · WGS84</span></div>
                        <div className="climate-sample-table"><table><thead><tr><th>Observed</th><th>Variable</th><th>Value</th><th>Quality</th></tr></thead><tbody>
                          {observations.map((item) => <tr key={item.id}><td>{formatDate(item.observed_at)}</td><td>{item.variable}</td><td>{item.value} {item.unit}</td><td><span className={`climate-quality ${item.quality_status}`}>{item.quality_status}</span></td></tr>)}
                        </tbody></table></div>
                        {canQualityReview && selectedRun.status === "completed" && (
                          <div className="climate-review-box">
                            <label>Reviewer note<textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} minLength={5} /></label>
                            <p>This batch decision applies to every pending observation in the selected provider run. Your own submissions cannot be reviewed by you.</p>
                            <div className="climate-action-row">
                              <button className="climate-primary" disabled={busy || !observations.some((item) => item.quality_status === "pending")} onClick={() => reviewRun("verified")}>Verify pending batch</button>
                              <button className="climate-danger" disabled={busy || !observations.some((item) => item.quality_status === "pending")} onClick={() => reviewRun("rejected")}>Reject pending batch</button>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                    {!selectedRun && <div className="climate-empty"><strong>No run selected</strong><p>Select an ingestion record to inspect its source, coverage request and sample values.</p></div>}
                  </section>
                  <aside className="climate-side-panel">
                    <p className="climate-kicker">REVIEW STANDARD</p><h3>Before you verify</h3>
                    <ul className="climate-checklist"><li>Confirm provider and product variant.</li><li>Check requested dates and bounded geography.</li><li>Inspect the sample for plausible values and units.</li><li>Check licence, source and skipped-record count.</li><li>Record any caveats in the review note.</li></ul>
                    <div className="climate-side-note"><strong>Independent review</strong><p>Reviewers cannot approve their own submitted observations. Each decision is recorded in the organisation audit trail.</p></div>
                  </aside>
                </div>
              )}

              {stage === "publish" && (
                <div className="climate-work-grid">
                  <section className="climate-panel climate-panel-feature">
                    <div className="climate-panel-head"><span>03 / PUBLICATION GOVERNANCE</span><span className="climate-panel-index">PUB-01</span></div>
                    <h2>Shape the public evidence</h2>
                    <p>Build a versioned release from a completed, independently reviewed provider run. Values are derived by the server; this form cannot submit chart data.</p>
                    {!canAuthor ? <p className="climate-lock">Your membership does not include release-authoring permissions.</p> : (
                      <form className="climate-form" onSubmit={createRelease}>
                        <label>Verified provider run<select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)} required><option value="">Select reviewed provider run</option>{publishableRuns.map((run) => <option key={run.id} value={run.id}>{run.source_name} · {formatDate(run.started_at)} · {run.records_inserted} records</option>)}</select></label>
                        <label>Release title<input value={releaseTitle} onChange={(event) => setReleaseTitle(event.target.value)} minLength={3} maxLength={240} required /></label>
                        <label>Public URL slug<input value={releaseSlug} onChange={(event) => setReleaseSlug(event.target.value)} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" required /></label>
                        <label>Public summary<textarea value={releaseSummary} onChange={(event) => setReleaseSummary(event.target.value)} minLength={10} required /></label>
                        <label>Uncertainty statement<textarea value={uncertainty} onChange={(event) => setUncertainty(event.target.value)} /></label>
                        <label>Limitations<textarea value={limitations} onChange={(event) => setLimitations(event.target.value)} minLength={5} required /></label>
                        <div className="climate-form-note"><strong>Publication facts</strong><span>Data class: satellite estimate · Product: CHIRPS v3 · Licence and attribution are inherited from the provider run.</span></div>
                        <button className="climate-primary" type="submit" disabled={busy || !selectedRun || !publishableRuns.some((run) => run.id === selectedRun.id)}>Create evidence draft <span>↗</span></button>
                        {publishableRuns.length === 0 && <p className="climate-muted">No provider run is currently eligible. Complete an independent review and ensure every inserted observation is verified.</p>}
                      </form>
                    )}
                  </section>
                  <aside className="climate-side-panel">
                    <p className="climate-kicker">RELEASE WORKFLOW</p><h3>Governance queue</h3>
                    {activeReleases.length === 0 ? <p className="climate-muted">No release drafts yet. A release will appear here after its source run passes quality review.</p> : activeReleases.map((release) => (
                      <article className="climate-release-row" key={release.id}>
                        <div><span className={`climate-state ${release.state}`}>{labelForState[release.state] ?? release.state}</span><small>VERSION {release.version}</small></div>
                        <strong>{release.title}</strong>
                        <p>{release.indicator} · {release.unit} · {release.geography_label}</p>
                        <div className="climate-release-actions">
                          {release.state === "draft" && (release.created_by === membership?.user_id || canReleaseReview) && <button disabled={busy} onClick={() => transitionRelease(release, "submit")}>Submit for review</button>}
                          {release.state === "review" && canReleaseReview && <button disabled={busy || release.created_by === membership?.user_id} onClick={() => transitionRelease(release, "approve")}>Approve</button>}
                          {release.state === "approved" && canReleaseReview && <button disabled={busy} onClick={() => transitionRelease(release, "publish")}>Publish public</button>}
                          {release.state === "published" && canReleaseReview && <button className="danger-text" disabled={busy} onClick={() => transitionRelease(release, "retract")}>Retract</button>}
                        </div>
                      </article>
                    ))}
                    <div className="climate-side-note"><strong>Public exposure</strong><p>Only published releases appear on the public climate hub. Drafts, review notes, raw coordinates and internal provider runs remain private.</p></div>
                  </aside>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
