"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiDelete, apiGet, apiPost, apiPut, clearSession, hasSession } from "@/lib/api";

interface Organization { id: string; name: string; country_code: string }
interface Membership { role: string; roles?: string[]; status: string }
interface ODKConnection {
  configured: boolean;
  base_url: string | null;
  project_id: number | null;
  account_email: string | null;
  enabled: boolean;
  mapped_forms: string[];
  form_mappings: Record<string, Record<string, string>>;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_message: string | null;
}
interface ODKForm { xml_form_id: string; name: string; version: string | null; state: string | null }
interface ODKReconciliationItem {
  observation_id: string; form_id: string | null; instance_id: string | null;
  source_updated_at: string | null; source_deleted_at: string | null;
  revision_detected: boolean; deletion_review_required: boolean;
  quality_status: string; reviewed_at: string | null;
}
interface ODKReconciliationQueue { total: number; returned: number; items: ODKReconciliationItem[] }
interface ODKSyncRun {
  id: string; status: string; forms_checked: number; submissions_received: number;
  observations_imported: number; duplicates_skipped: number; rejected_count: number;
  error_count: number;
  error_summary: string | null; started_at: string; completed_at: string | null;
}
interface ODKOperationsAlert { code: string; severity: "info" | "warning" | "critical"; message: string }
interface ODKOperations {
  configured: boolean; enabled: boolean; last_sync_at: string | null; last_sync_status: string | null;
  mapped_forms: number; forms_with_cursors: number; consecutive_error_runs: number;
  alerts: ODKOperationsAlert[];
}
const EMPTY_OPERATIONS: ODKOperations = {
  configured: false, enabled: false, last_sync_at: null, last_sync_status: null,
  mapped_forms: 0, forms_with_cursors: 0, consecutive_error_runs: 0, alerts: [],
};

const EMPTY_CONNECTION: ODKConnection = {
  configured: false, base_url: null, project_id: null, account_email: null,
  enabled: false, mapped_forms: [], form_mappings: {}, last_sync_at: null,
  last_sync_status: null, last_sync_message: null,
};
const EXAMPLE_MAPPING = JSON.stringify({
  "rainfall-v1": {
    observed_at: "__system/submissionDate", variable: "measurement", value: "reading",
    unit: "unit", latitude: "gps_lat", longitude: "gps_lon",
  },
}, null, 2);
const MANAGER_ROLES = ["admin", "founder", "executive"];
const REVIEW_ROLES = [...MANAGER_ROLES, "researcher", "programme_manager"];

export default function ODKIntegrationPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [membership, setMembership] = useState<Membership | null>(null);
  const [connection, setConnection] = useState<ODKConnection>(EMPTY_CONNECTION);
  const [baseUrl, setBaseUrl] = useState("");
  const [projectId, setProjectId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mappings, setMappings] = useState(EXAMPLE_MAPPING);
  const [forms, setForms] = useState<ODKForm[]>([]);
  const [runs, setRuns] = useState<ODKSyncRun[]>([]);
  const [operations, setOperations] = useState<ODKOperations>(EMPTY_OPERATIONS);
  const [reconciliation, setReconciliation] = useState<ODKReconciliationQueue>({ total: 0, returned: 0, items: [] });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async (id: string) => {
    const [member, configured, history] = await Promise.all([
      apiGet<Membership>(`/organizations/${id}/memberships/me`),
      apiGet<ODKConnection>(`/organizations/${id}/odk/connection`),
      apiGet<ODKSyncRun[]>(`/organizations/${id}/odk/sync-runs`),
    ]);
    const activeRoles = member.status === "active" ? (member.roles ?? [member.role]) : [];
    const manager = activeRoles.some((role) => MANAGER_ROLES.includes(role));
    const reviewer = activeRoles.some((role) => REVIEW_ROLES.includes(role));
    const operationalStatus = manager
      ? await apiGet<ODKOperations>(`/organizations/${id}/odk/operations`)
      : EMPTY_OPERATIONS;
    const reviewQueue = reviewer
      ? await apiGet<ODKReconciliationQueue>(`/organizations/${id}/odk/reconciliation`)
      : { total: 0, returned: 0, items: [] };
    setMembership(member);
    setConnection(configured);
    setRuns(history);
    setOperations(operationalStatus);
    setReconciliation(reviewQueue);
    setBaseUrl(configured.base_url ?? "");
    setProjectId(configured.project_id ? String(configured.project_id) : "");
    setEmail(configured.account_email ?? "");
    setMappings(Object.keys(configured.form_mappings).length
      ? JSON.stringify(configured.form_mappings, null, 2) : EXAMPLE_MAPPING);
  }, []);

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
    setError(""); setForms([]);
    refresh(organizationId).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unable to load ODK integration settings.");
    });
    return () => { active = false; };
  }, [organizationId, refresh]);

  const activeRoles = membership?.status === "active" ? (membership.roles ?? [membership.role]) : [];
  const canManage = activeRoles.some((role) => MANAGER_ROLES.includes(role));
  const canReview = activeRoles.some((role) => REVIEW_ROLES.includes(role));

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const parsed = JSON.parse(mappings) as Record<string, Record<string, string>>;
      if (!projectId || !Number.isInteger(Number(projectId)) || Number(projectId) <= 0) {
        throw new Error("Enter a valid positive ODK Central project ID.");
      }
      const saved = await apiPut<ODKConnection>(`/organizations/${organizationId}/odk/connection`, {
        base_url: baseUrl, project_id: Number(projectId), account_email: email,
        password, form_mappings: parsed, enabled: true,
      });
      setConnection(saved); setPassword("");
      setNotice("ODK Central connection settings saved. Test the connection before enabling the sync worker.");
      await refresh(organizationId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save ODK Central settings.");
    } finally { setBusy(false); }
  }

  async function testConnection() {
    setBusy(true); setError(""); setNotice("");
    try {
      const payload = await apiPost<{ message: string; forms_available: number }>(
        `/organizations/${organizationId}/odk/connection/test`, {},
      );
      setNotice(`${payload.message}. ${payload.forms_available} forms available.`);
      const discovered = await apiGet<ODKForm[]>(`/organizations/${organizationId}/odk/forms`);
      setForms(discovered);
      await refresh(organizationId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ODK Central connection test failed.");
    } finally { setBusy(false); }
  }

  async function removeConnection() {
    if (!window.confirm("Remove this organisation's saved ODK Central connection?")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await apiDelete<void>(`/organizations/${organizationId}/odk/connection`);
      setConnection(EMPTY_CONNECTION); setForms([]); setRuns([]); setOperations(EMPTY_OPERATIONS); setPassword("");
      setNotice("ODK Central connection removed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to remove connection.");
    } finally { setBusy(false); }
  }

  async function decideReconciliation(item: ODKReconciliationItem, decision: "acknowledge_revision" | "acknowledge_deletion" | "retain_observation") {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiPost(`/organizations/${organizationId}/odk/${item.observation_id}/reconciliation`, {
        decision,
        note: decision === "retain_observation" ? "Reviewed; retain the existing evidence record." : "Reviewed upstream source change.",
      });
      setNotice("Source reconciliation decision recorded. Scientific measurements were not changed.");
      await refresh(organizationId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record reconciliation decision.");
    } finally { setBusy(false); }
  }

  async function refreshStatus() {
    setBusy(true); setError("");
    try {
      await refresh(organizationId);
      try {
        const discovered = await apiGet<ODKForm[]>(`/organizations/${organizationId}/odk/forms`);
        setForms(discovered);
      } catch (cause) {
        setForms([]);
        setError(cause instanceof Error ? cause.message : "Unable to refresh the Central form catalogue.");
      }
      setNotice("ODK operational status and sync history refreshed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to refresh ODK status.");
    } finally { setBusy(false); }
  }

  if (loading) return <main className="workspace-shell"><p>Loading ODK integration…</p></main>;
  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link>
        <button className="workspace-signout" onClick={() => { clearSession(); window.location.assign("/"); }}>Sign out</button>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">RESEARCH & CLIMATE INTELLIGENCE</p>
        <h1 className="workspace-title">ODK Central.<br /><em>Field data, connected.</em></h1>
        <p className="workspace-intro">Connect an ODK Central project, map form fields into the climate evidence ledger, and monitor automated imports. Imported observations remain pending until independently reviewed.</p>
        <div className="role-workspace-links"><Link href="/workspace/research">← Back to research workspace</Link></div>
        {error && <p className="workspace-error" role="alert">{error}</p>}
        {notice && <p className="workspace-notice" role="status">{notice}</p>}
        <label className="org-label" htmlFor="odk-organization">Active organisation</label>
        <select id="odk-organization" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
          {organizations.map((org) => <option key={org.id} value={org.id}>{org.name} · {org.country_code}</option>)}
        </select>
        {!canReview ? <div className="workspace-empty"><h2>Research access required</h2><p>ODK reconciliation is available to authorised researchers, programme managers and organisation leaders.</p></div> : (
          <>
            {canManage && <section className="research-section odk-connection-card">
              <div className="section-heading"><div><p className="eyebrow">CENTRAL PROJECT</p><h2>{connection.configured ? "Connection settings" : "Connect ODK Central"}</h2></div><span>{connection.configured ? "Configured" : "Not configured"}</span></div>
              <form className="climate-analysis-form" onSubmit={save}>
                <label>ODK Central server URL<input type="url" required value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://central.example.org" /></label>
                <label>Project ID<input type="number" min="1" step="1" required value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="e.g. 12" /></label>
                <label>Central account email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="field-team@example.org" /></label>
                <label>Central account password<input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" placeholder={connection.configured ? "Re-enter to rotate saved password" : "Password is encrypted before storage"} /></label>
                <label>Form field mappings (JSON)<textarea rows={12} required value={mappings} onChange={(event) => setMappings(event.target.value)} spellCheck={false} /></label>
                <p className="workspace-muted">Each mapping key is an ODK XML form ID. Required fields: observed_at, variable, value, unit, latitude and longitude. Use __system/submissionDate for Central&apos;s submission timestamp. Optional mappings: project_id and study_id.</p>
                <div className="dataset-review-actions"><button className="primary-action" disabled={busy}>{busy ? "Saving…" : "Save connection"}</button><button type="button" className="secondary-action" disabled={busy || !connection.configured} onClick={() => void testConnection()}>Test & discover forms</button>{connection.configured && <button type="button" className="secondary-action" disabled={busy} onClick={() => void removeConnection()}>Remove connection</button>}</div>
              </form>
            </section>}
            <section className="research-section">
              <div className="section-heading"><div><p className="eyebrow">SOURCE GOVERNANCE</p><h2>ODK reconciliation queue</h2></div><span>{reconciliation.total} awaiting review</span></div>
              <p className="workspace-muted">Central records can be revised or deleted after collection. Review each notice explicitly; this workflow preserves the organisation&apos;s existing scientific evidence and records the decision in the audit trail.</p>
              {reconciliation.items.length ? reconciliation.items.map((item) => <article className="odk-form-row" key={item.observation_id}>
                <div><strong>{item.form_id ?? "ODK form"} · {item.instance_id ?? item.observation_id}</strong>
                  <small>{item.revision_detected ? `Source revised ${item.source_updated_at ?? "(timestamp unavailable)"}` : "No pending revision"} · {item.deletion_review_required ? `Source deletion reported ${item.source_deleted_at ?? "(timestamp unavailable)"}` : "No pending deletion"}</small>
                  <small>Evidence status: {item.quality_status} · Observation: {item.observation_id}</small>
                  <div className="dataset-review-actions">
                    {item.revision_detected && <button type="button" className="secondary-action" disabled={busy} onClick={() => void decideReconciliation(item, "acknowledge_revision")}>Acknowledge revision</button>}
                    {item.deletion_review_required && <button type="button" className="secondary-action" disabled={busy} onClick={() => void decideReconciliation(item, "acknowledge_deletion")}>Acknowledge deletion</button>}
                    <button type="button" className="secondary-action" disabled={busy} onClick={() => void decideReconciliation(item, "retain_observation")}>Retain existing evidence</button>
                  </div>
                </div>
              </article>) : <p className="workspace-notice" role="status">No source revisions or deletions require reconciliation.</p>}
            </section>
            {canManage && connection.configured && <>
              <section className="research-section">
                <div className="section-heading"><div><p className="eyebrow">SYNC HEALTH</p><h2>Latest synchronisation</h2></div><button type="button" className="secondary-action" disabled={busy} onClick={() => void refreshStatus()}>Refresh status</button></div>
                <div className="odk-status-grid"><article><strong>{connection.last_sync_status ?? "Not run"}</strong><span>Last run status</span></article><article><strong>{connection.last_sync_at ? new Date(connection.last_sync_at).toLocaleString() : "—"}</strong><span>Last synchronised</span></article><article><strong>{connection.mapped_forms.length}</strong><span>Mapped forms</span></article></div>
                {operations.alerts.length ? <div className="odk-operations-alerts" aria-live="polite">{operations.alerts.map((alert) => <p key={alert.code} className={alert.severity === "critical" ? "workspace-error" : "workspace-muted"}><strong>{alert.severity.toUpperCase()} · </strong>{alert.message}</p>)}</div> : <p className="workspace-notice" role="status">No ODK operational alerts detected.</p>}
                <p className="workspace-muted">{operations.consecutive_error_runs} consecutive runs with errors · {operations.forms_with_cursors} forms with saved continuation cursors · Worker {operations.enabled ? "enabled" : "disabled"}</p>
                {connection.last_sync_message && <p className="workspace-error">{connection.last_sync_message}</p>}
                <p className="workspace-muted">The worker runs on the configured polling interval. A connection test does not start a sync; the worker must be running in the deployment.</p>
              </section>
              <section className="research-section">
                <div className="section-heading"><div><p className="eyebrow">FORM CATALOGUE</p><h2>Available forms</h2></div><span>{forms.length} discovered</span></div>
                {forms.length ? forms.map((form) => <article className="odk-form-row" key={form.xml_form_id}><div><strong>{form.name}</strong><small>{form.xml_form_id} · v{form.version ?? "—"} · {form.state ?? "unknown state"}</small></div><span>{connection.mapped_forms.includes(form.xml_form_id) ? "Mapped" : "Not mapped"}</span></article>) : <p className="workspace-muted">Use “Test & discover forms” to load the project&apos;s form catalogue.</p>}
              </section>
              <section className="research-section">
                <div className="section-heading"><div><p className="eyebrow">AUDIT TRAIL</p><h2>Synchronisation history</h2></div><span>{runs.length} recent runs</span></div>
                {runs.length ? runs.map((run) => <article className="odk-form-row" key={run.id}><div><strong>{run.status} · {new Date(run.started_at).toLocaleString()}</strong><small>{run.forms_checked} forms · {run.submissions_received} submissions · {run.observations_imported} imported · {run.duplicates_skipped} duplicates · {run.rejected_count} rejected · {run.error_count} errors</small>{run.error_summary && <small>{run.error_summary}</small>}</div></article>) : <p className="workspace-muted">No synchronisation runs recorded yet.</p>}
              </section>
            </>}
          </>
        )}
      </section>
    </main>
  );
}
