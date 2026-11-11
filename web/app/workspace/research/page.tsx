"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { apiGet, apiPatch, apiPost, clearSession, hasSession } from "@/lib/api";

interface Organization {
  id: string;
  name: string;
  country_code: string;
}
interface Membership {
  user_id: string;
  role: "admin" | "programme_manager" | "researcher" | "youth_volunteer" | "institutional_partner";
  status: string;
}
interface Study {
  id: string;
  title: string;
  abstract: string | null;
  study_type: string | null;
  status: string;
  lead_researcher_id: string;
  ethics_reference: string | null;
}
interface Dataset {
  id: string;
  study_id: string | null;
  title: string;
  description: string | null;
  version: string;
  format: string;
  source: string;
  license: string | null;
  access_classification: string;
  status: string;
  collection_start: string | null;
  collection_end: string | null;
  owner_user_id: string;
}
interface DatasetFile { id: string; version: number; original_filename: string; media_type: string; size_bytes: number; sha256_hex: string | null; status: string; scan_status: string; uploaded_at: string | null; }\ninterface ClimateUnitSummary {
  unit: string; count: number; missing_count: number; mean: number | null; median: number | null;
  sample_standard_deviation: number | null; standard_error: number | null; minimum: number | null; maximum: number | null;
  percentile_05: number | null; percentile_25: number | null; percentile_75: number | null; percentile_95: number | null;
  median_absolute_deviation: number | null;
}
interface ClimateAnalysisSummary {
  variable: string; quality_status: "verified" | "pending"; start: string; end: string;
  observation_count: number; groups: ClimateUnitSummary[];
  method: "descriptive_hyndman_fan_type_7"; missing_data_policy: "no_imputation";
}


const RESEARCH_ROLES = ["admin", "programme_manager", "researcher", "institutional_partner"];

export default function ResearchWorkspacePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [studies, setStudies] = useState<Study[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
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
    setStudies([]);
    setDatasets([]);
    Promise.all([
      apiGet<Membership>(`/organizations/${organizationId}/memberships/me`),
      apiGet<Study[]>(`/organizations/${organizationId}/research-studies`),
      apiGet<Dataset[]>(`/organizations/${organizationId}/research-datasets?limit=200`),
    ]).then(([member, studyItems, datasetItems]) => {
      if (!active) return;
      if (!RESEARCH_ROLES.includes(member.role) || member.status !== "active") {
        setError("Research workspace access is not available for this membership.");
        return;
      }
      setMembership(member);
      setStudies(studyItems);
      setDatasets(datasetItems);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load research workspace.");
    });
    return () => { active = false; };
  }, [organizationId]);


  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [reviewHistory, setReviewHistory] = useState<Record<string, { id: string; decision: string; note: string | null; reviewed_at: string }[]>>({});
  const [historyLoading, setHistoryLoading] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, { title: string; description: string; version: string; format: string; source: string; license: string; access_classification: string }>>({});
  const [datasetFiles, setDatasetFiles] = useState<Record<string, DatasetFile[]>>({});
  const [fileLoading, setFileLoading] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [analysisVariable, setAnalysisVariable] = useState("precipitation");
  const [analysisStart, setAnalysisStart] = useState("2026-01-01T00:00");
  const [analysisEnd, setAnalysisEnd] = useState("2026-12-31T23:59");
  const [analysisQuality, setAnalysisQuality] = useState<"verified" | "pending">("verified");
  const [analysis, setAnalysis] = useState<ClimateAnalysisSummary | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const isReviewer = membership?.role === "admin" || membership?.role === "programme_manager";

  async function runClimateAnalysis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAnalysisError("");
    setAnalysis(null);
    const startDate = new Date(analysisStart);
    const endDate = new Date(analysisEnd);
    if (!Number.isFinite(startDate.getTime()) || !Number.isFinite(endDate.getTime()) || endDate <= startDate) {
      setAnalysisError("Choose a valid date range; the end must be later than the start.");
      return;
    }
    if (analysisVariable.trim().length < 2) {
      setAnalysisError("Enter a variable name containing at least two characters.");
      return;
    }
    setAnalysisLoading(true);
    try {
      const params = new URLSearchParams({
        variable: analysisVariable.trim(),
        start: startDate.toISOString(),
        end: endDate.toISOString(),
        quality_status: analysisQuality,
      });
      const result = await apiGet<ClimateAnalysisSummary>(
        "/organizations/" + organizationId + "/climate-observations/analysis-summary?" + params.toString(),
      );
      setAnalysis(result);
    } catch (cause) {
      setAnalysisError(cause instanceof Error ? cause.message : "Unable to calculate climate summary.");
    } finally {
      setAnalysisLoading(false);
    }
  }

  function formatStatistic(value: number | null): string {
    return value === null ? "—" : new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
  }

  async function submitDataset(datasetId: string) {
    setSaving(true); setError(""); setNotice("");
    try {
      const updated = await apiPost<Dataset>(`/organizations/${organizationId}/research-datasets/${datasetId}/submit`, {});
      setDatasets((items) => items.map((item) => item.id === datasetId ? updated : item));
      setNotice("Dataset submitted. It is now awaiting an independent governance decision.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit dataset.");
    } finally { setSaving(false); }
  }

  async function decideDataset(datasetId: string, decision: "approved" | "rejected") {
    setSaving(true); setError(""); setNotice("");
    try {
      const updated = await apiPost<Dataset>(`/organizations/${organizationId}/research-datasets/${datasetId}/review`, {
        decision, note: reviewNotes[datasetId]?.trim() || null,
      });
      setDatasets((items) => items.map((item) => item.id === datasetId ? updated : item));
      setNotice(`Dataset ${decision}. The decision has been recorded in review history.`);
      setReviewNotes((notes) => ({ ...notes, [datasetId]: "" }));
      await loadReviewHistory(datasetId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record review decision.");
    } finally { setSaving(false); }
  }

  async function loadReviewHistory(datasetId: string) {
    setHistoryLoading(datasetId);
    try {
      const history = await apiGet<{ id: string; decision: string; note: string | null; reviewed_at: string }[]>(
        `/organizations/${organizationId}/research-datasets/${datasetId}/reviews`,
      );
      setReviewHistory((current) => ({ ...current, [datasetId]: history }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load review history.");
    } finally { setHistoryLoading(null); }
  }

  function beginDatasetEdit(dataset: Dataset) {
    setEditValues((current) => ({ ...current, [dataset.id]: { title: dataset.title, description: dataset.description || "", version: dataset.version, format: dataset.format, source: dataset.source, license: dataset.license || "", access_classification: dataset.access_classification } }));
  }

  async function saveDatasetCorrections(datasetId: string) {
    const values = editValues[datasetId]; if (!values) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const updated = await apiPatch<Dataset>("/organizations/" + organizationId + "/research-datasets/" + datasetId, { ...values, description: values.description || null, license: values.license || null });
      setDatasets((items) => items.map((item) => item.id === datasetId ? updated : item));
      setEditValues((current) => { const next = { ...current }; delete next[datasetId]; return next; });
      setNotice("Corrections saved. Submit the revised draft when ready.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to save corrections."); } finally { setSaving(false); }
  }

  async function loadDatasetFiles(datasetId: string) {
    setFileLoading(datasetId);
    try { const files = await apiGet<DatasetFile[]>("/organizations/" + organizationId + "/research-datasets/" + datasetId + "/files"); setDatasetFiles((current) => ({ ...current, [datasetId]: files })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load dataset files."); } finally { setFileLoading(null); }
  }

  async function retryDatasetFileScan(datasetId: string, fileId: string) {
    setUploading(datasetId); setError(""); setNotice("");
    try {
      await apiPost<DatasetFile>(
        "/organizations/" + organizationId + "/research-datasets/" + datasetId + "/files/" + fileId + "/complete", {},
      );
      await loadDatasetFiles(datasetId);
      setNotice("File verification and scanning retry completed. Check the updated file status before use.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to retry file scanning.");
    } finally { setUploading(null); }
  }

  async function uploadDatasetFile(datasetId: string, file: File) {
    const allowed: Record<string, string> = { "text/csv": ".csv", "application/json": ".json", "application/pdf": ".pdf", "application/zip": ".zip", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx" };
    const extension = allowed[file.type];
    if (!extension || !file.name.toLowerCase().endsWith(extension)) { setError("Unsupported file type. Allowed: CSV, JSON, PDF, ZIP and XLSX."); return; }
    if (file.size < 1 || file.size > 100 * 1024 * 1024) { setError("File size must be between 1 byte and 100 MB."); return; }
    setUploading(datasetId); setError(""); setNotice("");
    try {
      const intent = await apiPost<{ file_id: string; upload_url: string; upload_fields: Record<string, string> }>("/organizations/" + organizationId + "/research-datasets/" + datasetId + "/files/upload-intents", { filename: file.name, media_type: file.type, size_bytes: file.size });
      const payload = new FormData(); Object.entries(intent.upload_fields).forEach(([key, value]) => payload.append(key, value)); payload.append("file", file);
      const response = await fetch(intent.upload_url, { method: "POST", body: payload });
      if (!response.ok) throw new Error("Private storage upload failed (" + response.status + ").");
      await apiPost<DatasetFile>("/organizations/" + organizationId + "/research-datasets/" + datasetId + "/files/" + intent.file_id + "/complete", {});
      await loadDatasetFiles(datasetId); setNotice("Upload received. Quarantined files are not downloadable until scanning completes.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to upload dataset file."); } finally { setUploading(null); }
  }
  async function createStudy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const created = await apiPost<Study>(`/organizations/${organizationId}/research-studies`, {
        title: String(values.get("title") || ""),
        abstract: String(values.get("abstract") || "") || null,
        study_type: String(values.get("study_type") || "") || null,
        ethics_reference: String(values.get("ethics_reference") || "") || null,
      });
      setStudies((current) => [created, ...current]);
      form.reset();
      setNotice("Study registered as a concept. Add the required governance and ethics records before field activity.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create the study.");
    } finally {
      setSaving(false);
    }
  }

  async function createDataset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const studyId = String(values.get("study_id") || "");
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const created = await apiPost<Dataset>(`/organizations/${organizationId}/research-datasets`, {
        title: String(values.get("title") || ""),
        description: String(values.get("description") || "") || null,
        version: String(values.get("version") || "1.0"),
        format: String(values.get("format") || ""),
        source: String(values.get("source") || ""),
        license: String(values.get("license") || "") || null,
        access_classification: String(values.get("access_classification") || "organization"),
        study_id: studyId || null,
      });
      setDatasets((current) => [created, ...current]);
      form.reset();
      setNotice("Dataset metadata registered as a draft. Submit it for independent review before treating it as approved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to register the dataset.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading research workspace…</p></main>;

  const count = (items: Dataset[], status: string) => items.filter((item) => item.status === status).length;
  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">RESEARCH & CLIMATE INTELLIGENCE</p>
        <h1 className="workspace-title">Research workspace.<br /><em>Evidence, with provenance.</em></h1>
        <p className="workspace-intro">Manage study discovery and inspect the governance state of organisation datasets. File contents remain behind separate, authorised access workflows.</p>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        {organizations.length === 0 && !error ? (
          <div className="workspace-empty"><h2>No organisation access yet</h2><p>Ask an organisation administrator to invite your account.</p></div>
        ) : (
          <>
            <label className="org-label" htmlFor="research-organization">Active organisation</label>
            <select id="research-organization" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
              {organizations.map((org) => <option value={org.id} key={org.id}>{org.name} · {org.country_code}</option>)}
            </select>
            {membership && (
              <>
                <section className="role-workspace">
                  <div><span className="eyebrow">YOUR ACCESS</span><h2>{membership.role.replace(/_/g, " ")}</h2><p>All study and dataset access is re-authorised by the API for this organisation.</p></div>
                  <div className="role-workspace-links"><Link href="/workspace">Back to organisation workspace →</Link></div>
                </section>
                <section className="research-section climate-analysis-panel">
                  <div className="section-heading"><div><p className="eyebrow">CLIMATE INTELLIGENCE</p><h2>Descriptive analysis</h2></div><span>Maximum 10,000 observations</span></div>
                  <p className="workspace-muted">Summarise one variable over a bounded time window. Results remain separated by measurement unit; rejected observations are excluded by the API.</p>
                  <form className="climate-analysis-form" onSubmit={runClimateAnalysis}>
                    <label>Variable
                      <input value={analysisVariable} onChange={(event) => setAnalysisVariable(event.target.value)} minLength={2} maxLength={80} required placeholder="e.g. precipitation, air_temperature" />
                    </label>
                    <label>Start (local time)
                      <input type="datetime-local" value={analysisStart} onChange={(event) => setAnalysisStart(event.target.value)} required />
                    </label>
                    <label>End (local time, exclusive)
                      <input type="datetime-local" value={analysisEnd} onChange={(event) => setAnalysisEnd(event.target.value)} required />
                    </label>
                    <label>Data quality
                      <select value={analysisQuality} onChange={(event) => setAnalysisQuality(event.target.value as "verified" | "pending")}>
                        <option value="verified">Verified only</option><option value="pending">Pending (provisional)</option>
                      </select>
                    </label>
                    <button className="primary-action" disabled={analysisLoading}>{analysisLoading ? "Analysing…" : "Run analysis"}</button>
                  </form>
                  {analysisError && <p className="workspace-error" role="alert">{analysisError}</p>}
                  {analysis && (
                    <div className="climate-analysis-results" aria-live="polite">
                      <div className="research-metrics">
                        <article><span>Observations</span><strong>{analysis.observation_count.toLocaleString()}</strong></article>
                        <article><span>Unit groups</span><strong>{analysis.groups.length}</strong></article>
                        <article><span>Quality status</span><strong>{analysis.quality_status}</strong></article>
                        <article><span>Missing policy</span><strong>No imputation</strong></article>
                      </div>
                      {analysis.quality_status === "pending" && <p className="workspace-notice">Provisional data: these measurements have not completed independent quality review.</p>}
                      {analysis.groups.length === 0 ? <p className="workspace-muted">No observations match this variable, period and quality status.</p> : analysis.groups.map((group) => (
                        <section className="climate-unit-result" key={group.unit}>
                          <h3>Measurements in {group.unit}</h3>
                          <p>{group.count.toLocaleString()} recorded values · {group.missing_count} missing values</p>
                          <div className="research-table-wrap"><table className="research-table">
                            <thead><tr><th>Statistic</th><th>Value</th><th>Statistic</th><th>Value</th></tr></thead>
                            <tbody>
                              <tr><th scope="row">Mean</th><td>{formatStatistic(group.mean)}</td><th scope="row">Median</th><td>{formatStatistic(group.median)}</td></tr>
                              <tr><th scope="row">Sample standard deviation</th><td>{formatStatistic(group.sample_standard_deviation)}</td><th scope="row">Standard error</th><td>{formatStatistic(group.standard_error)}</td></tr>
                              <tr><th scope="row">Minimum</th><td>{formatStatistic(group.minimum)}</td><th scope="row">Maximum</th><td>{formatStatistic(group.maximum)}</td></tr>
                              <tr><th scope="row">5th percentile</th><td>{formatStatistic(group.percentile_05)}</td><th scope="row">25th percentile</th><td>{formatStatistic(group.percentile_25)}</td></tr>
                              <tr><th scope="row">75th percentile</th><td>{formatStatistic(group.percentile_75)}</td><th scope="row">95th percentile</th><td>{formatStatistic(group.percentile_95)}</td></tr>
                              <tr><th scope="row">Median absolute deviation</th><td>{formatStatistic(group.median_absolute_deviation)}</td><th scope="row">Missing count</th><td>{group.missing_count}</td></tr>
                            </tbody>
                          </table></div>
                        </section>
                      ))}
                      <p className="workspace-muted">Method: {analysis.method.replace(/_/g, " ")}. The selected time window is start-inclusive and end-exclusive. These are descriptive statistics, not trend significance or attribution.</p>
                    </div>
                  )}
                </section>
                <div className="research-metrics" aria-label="Research dataset summary">
                  <article><span>Studies</span><strong>{studies.length}</strong></article>
                  <article><span>Datasets</span><strong>{datasets.length}</strong></article>
                  <article><span>Awaiting review</span><strong>{count(datasets, "submitted")}</strong></article>
                  <article><span>Approved</span><strong>{count(datasets, "approved")}</strong></article>
                </div>
                <div className="staff-grid research-authoring-grid">
                  <section className="staff-card">
                    <p className="eyebrow">RESEARCH DESIGN</p>
                    <h2>Register a study</h2>
                    <p>New studies begin in concept status and are owned by the creating researcher.</p>
                    <form onSubmit={createStudy}>
                      <label>Study title<input name="title" minLength={3} maxLength={240} required /></label>
                      <label>Study type<input name="study_type" maxLength={80} placeholder="e.g. observational, field study" /></label>
                      <label>Abstract<textarea name="abstract" rows={4} maxLength={20000} /></label>
                      <label>Ethics reference<input name="ethics_reference" maxLength={160} /></label>
                      <button className="primary-action" disabled={saving}>{saving ? "Saving…" : "Create study"}</button>
                    </form>
                  </section>
                  <section className="staff-card">
                    <p className="eyebrow">DATA GOVERNANCE</p>
                    <h2>Register dataset metadata</h2>
                    <p>Registration creates a draft only. File uploads and access grants use separate controlled workflows.</p>
                    <form onSubmit={createDataset}>
                      <label>Dataset title<input name="title" minLength={3} maxLength={240} required /></label>
                      <label>Linked study<select name="study_id" defaultValue=""><option value="">No linked study</option>{studies.map((study) => <option value={study.id} key={study.id}>{study.title}</option>)}</select></label>
                      <label>Description<textarea name="description" rows={3} maxLength={20000} /></label>
                      <div className="research-form-pair">
                        <label>Version<input name="version" defaultValue="1.0" maxLength={40} required /></label>
                        <label>Format<input name="format" placeholder="CSV, GeoTIFF…" minLength={2} maxLength={40} required /></label>
                      </div>
                      <label>Source<input name="source" minLength={2} maxLength={200} required /></label>
                      <div className="research-form-pair">
                        <label>Licence<input name="license" maxLength={120} /></label>
                        <label>Classification<select name="access_classification" defaultValue="organization"><option value="organization">Organisation</option><option value="restricted">Restricted</option><option value="public">Public</option></select></label>
                      </div>
                      <button className="primary-action" disabled={saving}>{saving ? "Saving…" : "Register draft dataset"}</button>
                    </form>
                  </section>
                </div>
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">STUDY REGISTRY</p><h2>Research studies</h2></div><span>{studies.length} records</span></div>
                  {studies.length === 0 ? <p className="workspace-muted">No studies are registered in this organisation yet.</p> : (
                    <div className="research-record-grid">{studies.map((study) => (
                      <article className="research-record" key={study.id}>
                        <div className="research-record-top"><span className="status-chip">{study.status.replace(/_/g, " ")}</span>{study.study_type && <span>{study.study_type}</span>}</div>
                        <h3>{study.title}</h3>
                        <p>{study.abstract || "No study abstract supplied."}</p>
                        <dl><div><dt>Lead researcher</dt><dd>{study.lead_researcher_id}</dd></div><div><dt>Ethics reference</dt><dd>{study.ethics_reference || "Not recorded"}</dd></div></dl>
                      </article>
                    ))}</div>
                  )}
                </section>
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">DATA GOVERNANCE</p><h2>Dataset registry</h2></div><span>{datasets.length} records</span></div>
                  {datasets.length === 0 ? <p className="workspace-muted">No datasets are registered in this organisation yet.</p> : (
                    <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Dataset</th><th>Version</th><th>Format</th><th>Classification</th><th>Status</th><th>Collection period</th><th>Actions / review</th></tr></thead>
                      <tbody>{datasets.map((dataset) => (
                        <tr key={dataset.id}>
                          <td><strong>{dataset.title}</strong><small>{dataset.source}</small>{dataset.license && <small>Licence: {dataset.license}</small>}</td>
                          <td>{dataset.version}</td><td>{dataset.format.toUpperCase()}</td><td>{dataset.access_classification}</td>
                          <td><span className="status-chip">{dataset.status.replace(/_/g, " ")}</span></td>
                          <td>{dataset.collection_start || "—"} – {dataset.collection_end || "—"}</td>
                          <td>
                            {dataset.status === "draft" && (dataset.owner_user_id === membership.user_id || membership.role === "admin") && <button type="button" className="secondary-action" disabled={saving} onClick={() => submitDataset(dataset.id)}>Submit for review</button>}
                            {isReviewer && dataset.owner_user_id !== membership.user_id && dataset.status === "submitted" && (dataset.access_classification !== "restricted" || membership.role === "admin") && (
                              <div className="dataset-review-controls">
                                <label>Review note<textarea rows={2} maxLength={2000} value={reviewNotes[dataset.id] || ""} onChange={(event) => setReviewNotes((notes) => ({ ...notes, [dataset.id]: event.target.value }))} /></label>
                                <div className="dataset-review-actions">
                                  <button type="button" className="primary-action" disabled={saving} onClick={() => decideDataset(dataset.id, "approved")}>Approve</button>
                                  <button type="button" className="secondary-action" disabled={saving || !(reviewNotes[dataset.id] || "").trim()} onClick={() => decideDataset(dataset.id, "rejected")}>Request corrections</button>
                                </div>
                              </div>
                            )}
                            {dataset.status === "rejected" && dataset.owner_user_id === membership.user_id && (
                              !editValues[dataset.id] ? <button type="button" className="text-action" onClick={() => beginDatasetEdit(dataset)}>Correct rejected dataset</button> : (
                                <div className="dataset-review-controls">
                                  {(["title", "description", "version", "format", "source", "license"] as const).map((field) => <label key={field}>{field.replace(/_/g, " ")}{field === "description" ? <textarea rows={3} value={editValues[dataset.id][field]} onChange={(event) => setEditValues((items) => ({ ...items, [dataset.id]: { ...items[dataset.id], [field]: event.target.value } }))} /> : <input value={editValues[dataset.id][field]} onChange={(event) => setEditValues((items) => ({ ...items, [dataset.id]: { ...items[dataset.id], [field]: event.target.value } }))} />}</label>)}
                                  <label>Classification<select value={editValues[dataset.id].access_classification} onChange={(event) => setEditValues((items) => ({ ...items, [dataset.id]: { ...items[dataset.id], access_classification: event.target.value } }))}><option value="organization">Organisation</option><option value="restricted">Restricted</option><option value="public">Public</option></select></label>
                                  <button type="button" className="primary-action" disabled={saving} onClick={() => saveDatasetCorrections(dataset.id)}>Save corrections</button>
                                </div>
                              )
                            )}
                            {(dataset.status === "draft" || dataset.status === "rejected") && (dataset.owner_user_id === membership.user_id || membership.role === "admin") && <label className="dataset-file-picker">Add file version<input type="file" disabled={uploading === dataset.id || saving} accept=".csv,.json,.pdf,.zip,.xlsx" onChange={(event) => { const selected = event.currentTarget.files?.[0]; if (selected) void uploadDatasetFile(dataset.id, selected); event.currentTarget.value = ""; }} /><small>Maximum 100 MB. Files remain quarantined until scanning completes.</small></label>}
                            <button type="button" className="text-action" disabled={fileLoading === dataset.id} onClick={() => loadDatasetFiles(dataset.id)}>{fileLoading === dataset.id ? "Loading files…" : "File versions"}</button>
                            {datasetFiles[dataset.id] && <ul className="dataset-file-list">{datasetFiles[dataset.id].map((file) => <li key={file.id}><strong>v{file.version} · {file.original_filename}</strong><span>{file.status.replace(/_/g, " ")} / scan: {file.scan_status}</span>{file.status === "quarantined" && <button type="button" className="text-action" disabled={uploading === dataset.id} onClick={() => retryDatasetFileScan(dataset.id, file.id)}>{uploading === dataset.id ? "Retrying…" : "Retry verification / scan"}</button>}<small>{Math.ceil(file.size_bytes / 1024)} KB{file.sha256_hex ? " · SHA-256 " + file.sha256_hex.slice(0, 12) + "…" : ""}</small></li>)}</ul>}
                            <button type="button" className="text-action" disabled={historyLoading === dataset.id} onClick={() => loadReviewHistory(dataset.id)}>{historyLoading === dataset.id ? "Loading history…" : "Review history"}</button>
                            {reviewHistory[dataset.id] && <ol className="dataset-review-history">{reviewHistory[dataset.id].map((event) => <li key={event.id}><strong>{event.decision}</strong> · {new Date(event.reviewed_at).toLocaleString()}{event.note && <p>{event.note}</p>}</li>)}</ol>}
                          </td>
                        </tr>
                      ))}</tbody>
                    </table></div>
                  )}
                  <p className="workspace-muted">This registry displays metadata only. It does not expose object-storage keys, file bytes, or download URLs.</p>
                </section>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}
