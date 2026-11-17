"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPatch, apiPost, clearSession, hasSession } from "@/lib/api";

interface Organization {
  id: string;
  name: string;
  country_code: string;
}
interface Membership {
  user_id: string;
  role: "admin" | "founder" | "executive" | "programme_manager" | "researcher" | "youth_volunteer" | "institutional_partner";
  roles?: Membership["role"][];
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
interface ProtocolVersion {
  id: string; study_id: string; version_number: number; title: string;
  objectives: string; methodology: string; sampling_and_participants: string | null;
  data_management: string | null; risk_and_safeguarding: string | null;
  status: string; submitted_at: string | null; created_at: string;
}
interface ProtocolReview { id: string; protocol_version_id: string; decision: string; note: string | null; reviewed_at: string; }
interface EthicsReview { id: string; study_id: string; protocol_version_id: string | null; decision: string; reference: string | null; note: string | null; reviewed_at: string; }
interface EvidenceLedger {
  study_id: string; study_title: string; generated_at: string;
  datasets: { dataset_id: string; title: string; version: string; access_classification: string; manifest_sha256: string; file_count: number; files_truncated: boolean }[];
  analysis_runs: { run_id: string; dataset_id: string; input_manifest_sha256: string; manifest_matches_current: boolean; software_name: string; software_version: string; code_revision: string | null; output_artifact_count: number; created_at: string }[];
  publications: { publication_id: string; title: string; publication_type: string; doi: string | null; openalex_id: string | null; metadata_provenance_count: number }[];
  governance: { study_status: string; study_ethics_reference: string | null; protocol_version_count: number; latest_protocol_version_number: number | null; latest_protocol_status: string | null; latest_protocol_review_decision: string | null; latest_protocol_reviewed_at: string | null; ethics_review_count: number; latest_ethics_decision: string | null; latest_ethics_reference: string | null; latest_ethics_reviewed_at: string | null };
  climate: { observation_count: number; verified_count: number; pending_count: number; rejected_count: number; first_observed_at: string | null; last_observed_at: string | null };
  datasets_truncated: boolean; analysis_runs_truncated: boolean; publications_truncated: boolean;
  interpretation: string;
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
interface ResearchAnalysisRun {
  id: string; organization_id: string; dataset_id: string; study_id: string | null;
  input_manifest_sha256: string;
  input_file_versions: { file_id: string; version: number; filename: string; sha256: string }[];
  analysis_configuration: Record<string, unknown>;
  software_name: string; software_version: string; code_revision: string | null;
  parameters: Record<string, unknown>; random_seed: number | null;
  output_artifacts: { artifact_id: string; filename: string; media_type: string; size_bytes: number; sha256: string }[];
  created_by: string; created_at: string;
}
interface DatasetFile { id: string; version: number; original_filename: string; media_type: string; size_bytes: number; sha256_hex: string | null; status: string; scan_status: string; uploaded_at: string | null; }
interface DatasetManifest { dataset_id: string; dataset_version: string; manifest_sha256: string; file_count: number; files: { file_id: string; version: number; filename: string; media_type: string; size_bytes: number; sha256: string }[]; }
interface ClimateUnitSummary {
  unit: string; count: number; missing_count: number; mean: number | null; median: number | null;
  sample_standard_deviation: number | null; standard_error: number | null; minimum: number | null; maximum: number | null;
  percentile_05: number | null; percentile_25: number | null; percentile_75: number | null; percentile_95: number | null;
  median_absolute_deviation: number | null;
}
interface ClimateObservation {
  id: string; organization_id: string; study_id: string | null; project_id: string | null;
  observed_at: string; variable: string; value: number; unit: string; latitude: number; longitude: number;
  source: string; quality_status: "pending" | "verified" | "rejected"; reviewed_by: string | null;
  reviewed_at: string | null; review_note: string | null;
}
interface FlaggedObservation {
  id: string; observed_at: string; variable: string; value: number; unit: string;
  latitude: number; longitude: number; source: string; quality_status: string; flags: string[];
}
interface FlaggedObservationReport {
  items: FlaggedObservation[]; scanned_count: number; matched_count: number;
  offset: number; limit: number; scan_truncated: boolean;
}
interface DailyCoverageReport {
  variable: string; latitude: number; longitude: number; start_date: string; end_date: string;
  expected_days: number; observed_days: number; missing_days: string[];
  coverage_ratio: number; missing_data_policy: "report_only_no_imputation";
}
interface SpatialClimateQuery {
  west: string; south: string; east: string; north: string; variable: string;
  quality_status: "" | "pending" | "verified" | "rejected";
  start: string; end: string;
}
interface ClimateAnalysisSummary {
  variable: string; quality_status: "verified" | "pending"; start: string; end: string;
  observation_count: number; groups: ClimateUnitSummary[];
  method: "descriptive_hyndman_fan_type_7"; missing_data_policy: "no_imputation";
}

interface MonthlyAnomalyPoint {
  year: number; month: number; observed_total_mm: number; observed_days: number;
  expected_days: number; completeness: number; baseline_mean_mm: number;
  baseline_sample_standard_deviation_mm: number; baseline_year_count: number;
  standardized_anomaly: number; method: string; classification: "unclassified";
}
interface MonthlyAnomalyReport {
  variable: string; unit: string; quality_status: "verified" | "pending";
  latitude: number; longitude: number; baseline_start: string; baseline_end: string;
  target_start: string; target_end: string; minimum_completeness: number;
  minimum_baseline_years: number; observation_count: number;
  provenance_sources: string[]; provider_ids: string[]; ingestion_run_ids: string[];
  points: MonthlyAnomalyPoint[];
}


const RESEARCH_ROLES = ["admin", "founder", "executive", "programme_manager", "researcher", "institutional_partner"];
const STUDY_NEXT_STATUS: Record<string, { status: string; label: string }> = {
  concept: { status: "protocol", label: "Move to protocol review" },
  protocol: { status: "active", label: "Activate study" },
  active: { status: "completed", label: "Mark completed" },
  completed: { status: "published", label: "Mark published" },
  published: { status: "archived", label: "Archive study" },
};

export default function ResearchWorkspacePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const workspaceGeneration = useRef(0);
  const governanceRequest = useRef(0);
  const [membership, setMembership] = useState<Membership | null>(null);
  const [studies, setStudies] = useState<Study[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [evidenceStudyId, setEvidenceStudyId] = useState("");
  const [evidenceLedger, setEvidenceLedger] = useState<EvidenceLedger | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceExporting, setEvidenceExporting] = useState(false);
  const [lifecycleSaving, setLifecycleSaving] = useState<string | null>(null);
  const [governanceStudyId, setGovernanceStudyId] = useState("");
  const [protocolVersions, setProtocolVersions] = useState<ProtocolVersion[]>([]);
  const [protocolReviews, setProtocolReviews] = useState<Record<string, ProtocolReview[]>>({});
  const [ethicsReviews, setEthicsReviews] = useState<EthicsReview[]>([]);
  const [governanceLoading, setGovernanceLoading] = useState(false);
  const [governanceBusy, setGovernanceBusy] = useState(false);
  const [protocolReviewNotes, setProtocolReviewNotes] = useState<Record<string, string>>({});
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
      const assignedRoles = member.roles?.length ? member.roles : [member.role];
      if (!assignedRoles.some((role) => RESEARCH_ROLES.includes(role)) || member.status !== "active") {
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


  useEffect(() => {
    workspaceGeneration.current += 1;
    governanceRequest.current += 1;
    setGovernanceStudyId("");
    setProtocolVersions([]);
    setProtocolReviews({});
    setEthicsReviews([]);
    setProtocolReviewNotes({});
    setGovernanceLoading(false);
    setGovernanceBusy(false);
    setEvidenceStudyId("");
    setEvidenceLedger(null);
    setClimateObservations([]);
    setClimateListLoading(false);
    setAnalysis(null);
    setAnalysisLoading(false);
    setAnalysisError("");
    setSpatialResults(null);
    setSpatialLoading(false);
    setSpatialError("");
    setFlaggedReport(null);
    setFlaggedOffset(0);
    setFlaggedLoading(false);
    setFlaggedError("");
    setCoverageReport(null);
    setCoverageLoading(false);
    setCoverageError("");
  }, [organizationId]);

  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [reviewHistory, setReviewHistory] = useState<Record<string, { id: string; decision: string; note: string | null; reviewed_at: string }[]>>({});
  const [historyLoading, setHistoryLoading] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, { title: string; description: string; version: string; format: string; source: string; license: string; access_classification: string }>>({});
  const [datasetFiles, setDatasetFiles] = useState<Record<string, DatasetFile[]>>({});
  const [analysisRuns, setAnalysisRuns] = useState<Record<string, ResearchAnalysisRun[]>>({});
  const [analysisRunsLoading, setAnalysisRunsLoading] = useState<string | null>(null);
  const [datasetManifests, setDatasetManifests] = useState<Record<string, DatasetManifest>>({});
  const [manifestLoading, setManifestLoading] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [climateObservations, setClimateObservations] = useState<ClimateObservation[]>([]);
  const [climateListLoading, setClimateListLoading] = useState(false);
  const [climateReviewNotes, setClimateReviewNotes] = useState<Record<string, string>>({});
  const [climateSubmitting, setClimateSubmitting] = useState(false);
  const [analysisVariable, setAnalysisVariable] = useState("precipitation");
  const [analysisStart, setAnalysisStart] = useState("2026-01-01T00:00");
  const [analysisEnd, setAnalysisEnd] = useState("2026-12-31T23:59");
  const [analysisQuality, setAnalysisQuality] = useState<"verified" | "pending">("verified");
  const [analysis, setAnalysis] = useState<ClimateAnalysisSummary | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [spatialQuery, setSpatialQuery] = useState<SpatialClimateQuery>({
    west: "33.9", south: "-4.7", east: "41.9", north: "5.2",
    variable: "", quality_status: "verified", start: "", end: "",
  });
  const [spatialResults, setSpatialResults] = useState<ClimateObservation[] | null>(null);
  const [spatialLoading, setSpatialLoading] = useState(false);
  const [spatialError, setSpatialError] = useState("");
  const [flaggedReport, setFlaggedReport] = useState<FlaggedObservationReport | null>(null);
  const [flaggedOffset, setFlaggedOffset] = useState(0);
  const [flaggedLoading, setFlaggedLoading] = useState(false);
  const [flaggedError, setFlaggedError] = useState("");
  const [flaggedQuality, setFlaggedQuality] = useState<"" | "pending" | "verified" | "rejected">("");
  const [flaggedName, setFlaggedName] = useState("");
  const [flaggedStart, setFlaggedStart] = useState("");
  const [flaggedEnd, setFlaggedEnd] = useState("");
  const [coverageQuery, setCoverageQuery] = useState({
    variable: "precipitation", latitude: "", longitude: "",
    start_date: "2026-01-01", end_date: "2026-12-31",
  });
  const [coverageReport, setCoverageReport] = useState<DailyCoverageReport | null>(null);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [coverageError, setCoverageError] = useState("");
  const [monthlyAnomalyQuery, setMonthlyAnomalyQuery] = useState({
    latitude: "", longitude: "", baseline_start: "2010-01-01",
    baseline_end: "2019-12-31", target_start: "2020-01-01",
    target_end: "2020-12-31", minimum_completeness: "0.9",
    minimum_baseline_years: "10",
  });
  const [monthlyAnomaly, setMonthlyAnomaly] = useState<MonthlyAnomalyReport | null>(null);
  const [monthlyAnomalyLoading, setMonthlyAnomalyLoading] = useState(false);
  const [monthlyAnomalyError, setMonthlyAnomalyError] = useState("");


  const membershipRoles = membership?.roles?.length
    ? membership.roles
    : membership ? [membership.role] : [];
  const isReviewer = membershipRoles.some((role) =>
    ["admin", "founder", "executive", "programme_manager"].includes(role)
  );
  const canAuthorProtocols = membershipRoles.some((role) => ["admin", "founder", "executive"].includes(role));
  useEffect(() => {
    if (organizationId && membership) void loadClimateObservations();
    // Reload when the active organisation or membership changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organizationId, membership?.role, membership?.roles, membership?.status]);


  async function loadClimateObservations() {
    setClimateListLoading(true);
    try {
      const items = await apiGet<ClimateObservation[]>(
        "/organizations/" + organizationId + "/climate-observations?quality_status=pending&limit=200",
      );
      setClimateObservations(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load climate observations.");
    } finally {
      setClimateListLoading(false);
    }
  }

  async function submitClimateObservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const observedAt = new Date(String(values.get("observed_at") || ""));
    if (!Number.isFinite(observedAt.getTime())) {
      setError("Enter a valid observation date and time.");
      return;
    }
    setClimateSubmitting(true);
    setError("");
    setNotice("");
    try {
      await apiPost<ClimateObservation>(
        "/organizations/" + organizationId + "/climate-observations",
        {
          observed_at: observedAt.toISOString(),
          variable: String(values.get("variable") || "").trim(),
          value: Number(values.get("value")),
          unit: String(values.get("unit") || "").trim(),
          latitude: Number(values.get("latitude")),
          longitude: Number(values.get("longitude")),
          source: String(values.get("source") || "").trim(),
          study_id: String(values.get("study_id") || "") || null,
        },
      );
      form.reset();
      await loadClimateObservations();
      setNotice("Observation submitted as pending. It will not appear in verified analysis until independently reviewed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to submit climate observation.");
    } finally {
      setClimateSubmitting(false);
    }
  }

  async function reviewClimateObservation(id: string, decision: "verified" | "rejected") {
    setClimateSubmitting(true);
    setError("");
    setNotice("");
    try {
      await apiPost<ClimateObservation>(
        "/organizations/" + organizationId + "/climate-observations/" + id + "/review",
        { decision, note: climateReviewNotes[id]?.trim() || null },
      );
      setClimateObservations((items) => items.filter((item) => item.id !== id));
      setClimateReviewNotes((items) => { const next = { ...items }; delete next[id]; return next; });
      setNotice("Quality decision recorded. Review decisions are immutable.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to review climate observation.");
    } finally {
      setClimateSubmitting(false);
    }
  }

  function exportMonthlyAnomalyCsv() {
    if (!monthlyAnomaly) return;
    const report = monthlyAnomaly;
    const columns = [
      "year", "month", "observed_total_mm", "observed_days", "expected_days",
      "completeness", "baseline_mean_mm", "baseline_sample_standard_deviation_mm",
      "baseline_year_count", "standardized_anomaly", "method", "classification",
      "latitude", "longitude", "quality_status", "baseline_start", "baseline_end",
      "target_start", "target_end", "minimum_completeness", "minimum_baseline_years",
      "provenance_sources", "provider_ids", "ingestion_run_ids",
    ];
    const csvCell = (value: unknown) => {
      let text = Array.isArray(value) ? value.join(";") : String(value ?? "");
      // Prevent spreadsheet formula execution when opening exported CSV files.
      if (/^\s*[=+\-@]/.test(text)) text = "'" + text;
      return '"' + text.replace(/"/g, '""') + '"';
    };
    const metadata = [
      report.latitude, report.longitude, report.quality_status,
      report.baseline_start, report.baseline_end, report.target_start,
      report.target_end, report.minimum_completeness,
      report.minimum_baseline_years, report.provenance_sources,
      report.provider_ids, report.ingestion_run_ids,
    ];
    const rows = report.points.map((point) => [
      point.year, point.month, point.observed_total_mm, point.observed_days,
      point.expected_days, point.completeness, point.baseline_mean_mm,
      point.baseline_sample_standard_deviation_mm, point.baseline_year_count,
      point.standardized_anomaly, point.method, point.classification, ...metadata,
    ]);
    const csv = [columns, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n");
    const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `nextgen-monthly-precipitation-anomalies-${report.target_start}-to-${report.target_end}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function runMonthlyPrecipitationAnomaly(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMonthlyAnomalyError("");
    setMonthlyAnomaly(null);
    const query = monthlyAnomalyQuery;
    const latitude = Number(query.latitude);
    const longitude = Number(query.longitude);
    const completeness = Number(query.minimum_completeness);
    const baselineYears = Number(query.minimum_baseline_years);
    if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90 ||
        !Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
      setMonthlyAnomalyError("Enter valid station or grid-cell coordinates.");
      return;
    }
    if (!(completeness > 0 && completeness <= 1) ||
        !Number.isInteger(baselineYears) || baselineYears < 2 || baselineYears > 100) {
      setMonthlyAnomalyError("Completeness must be above 0 and at most 1; baseline years must be 2–100.");
      return;
    }
    setMonthlyAnomalyLoading(true);
    try {
      const params = new URLSearchParams({
        ...query,
        latitude: String(latitude), longitude: String(longitude),
        minimum_completeness: String(completeness),
        minimum_baseline_years: String(baselineYears),
      });
      const report = await apiGet<MonthlyAnomalyReport>(
        `/organizations/${organizationId}/climate-observations/monthly-precipitation-anomalies?${params.toString()}`,
      );
      setMonthlyAnomaly(report);
    } catch (cause) {
      setMonthlyAnomalyError(cause instanceof Error ? cause.message : "Unable to calculate monthly anomalies.");
    } finally {
      setMonthlyAnomalyLoading(false);
    }
  }

  async function runClimateAnalysis(event: FormEvent<HTMLFormElement>) {
    const generation = workspaceGeneration.current;
    const requestOrganizationId = organizationId;
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
        "/organizations/" + requestOrganizationId + "/climate-observations/analysis-summary?" + params.toString(),
      );
      if (generation === workspaceGeneration.current) setAnalysis(result);
    } catch (cause) {
      if (generation === workspaceGeneration.current) setAnalysisError(cause instanceof Error ? cause.message : "Unable to calculate climate summary.");
    } finally {
      if (generation === workspaceGeneration.current) setAnalysisLoading(false);
    }
  }

  async function runSpatialClimateQuery(event: FormEvent<HTMLFormElement>) {
    const generation = workspaceGeneration.current;
    const requestOrganizationId = organizationId;
    event.preventDefault();
    setSpatialError("");
    setSpatialResults(null);
    const west = Number(spatialQuery.west);
    const south = Number(spatialQuery.south);
    const east = Number(spatialQuery.east);
    const north = Number(spatialQuery.north);
    if (![west, south, east, north].every(Number.isFinite) ||
        west < -180 || east > 180 || south < -90 || north > 90 ||
        west >= east || south >= north) {
      setSpatialError("Enter a valid WGS84 bounding box: west < east and south < north.");
      return;
    }
    const params = new URLSearchParams({
      west: String(west), south: String(south), east: String(east), north: String(north),
      limit: "500", offset: "0",
    });
    if (spatialQuery.variable.trim()) params.set("variable", spatialQuery.variable.trim());
    if (spatialQuery.quality_status) params.set("quality_status", spatialQuery.quality_status);
    if (spatialQuery.start) {
      const start = new Date(spatialQuery.start);
      if (!Number.isFinite(start.getTime())) { setSpatialError("Enter a valid start date."); return; }
      params.set("start", start.toISOString());
    }
    if (spatialQuery.end) {
      const end = new Date(spatialQuery.end);
      if (!Number.isFinite(end.getTime())) { setSpatialError("Enter a valid end date."); return; }
      params.set("end", end.toISOString());
    }
    if (spatialQuery.start && spatialQuery.end &&
        new Date(spatialQuery.end).getTime() < new Date(spatialQuery.start).getTime()) {
      setSpatialError("End date must not precede start date.");
      return;
    }
    setSpatialLoading(true);
    try {
      const result = await apiGet<ClimateObservation[]>(
        "/organizations/" + requestOrganizationId + "/climate-observations/spatial?" + params.toString(),
      );
      if (generation === workspaceGeneration.current) setSpatialResults(result);
    } catch (cause) {
      if (generation === workspaceGeneration.current) setSpatialError(cause instanceof Error ? cause.message : "Unable to query spatial observations.");
    } finally {
      if (generation === workspaceGeneration.current) setSpatialLoading(false);
    }
  }

  async function loadFlaggedObservations(offset = 0) {
    const generation = workspaceGeneration.current;
    const requestOrganizationId = organizationId;
    setFlaggedError("");
    const start = flaggedStart ? new Date(flaggedStart) : null;
    const end = flaggedEnd ? new Date(flaggedEnd) : null;
    if (flaggedName.trim() && flaggedName.trim().length < 2) {
      setFlaggedError("An exact flag must contain at least two characters.");
      return;
    }
    if ((start && !Number.isFinite(start.getTime())) || (end && !Number.isFinite(end.getTime())) ||
        (start && end && end < start)) {
      setFlaggedError("Enter valid dates; the end must not precede the start.");
      return;
    }
    setFlaggedLoading(true);
    const params = new URLSearchParams({ limit: "200", offset: String(offset) });
    if (flaggedName.trim()) params.set("flag", flaggedName.trim());
    if (flaggedQuality) params.set("quality_status", flaggedQuality);
    if (start) params.set("start", start.toISOString());
    if (end) params.set("end", end.toISOString());
    try {
      const report = await apiGet<FlaggedObservationReport>(
        "/organizations/" + requestOrganizationId + "/climate-observations/flagged?" + params.toString(),
      );
      if (generation === workspaceGeneration.current) setFlaggedReport(report);
      if (generation === workspaceGeneration.current) setFlaggedOffset(report.offset);
    } catch (cause) {
      if (generation === workspaceGeneration.current) setFlaggedError(cause instanceof Error ? cause.message : "Unable to load flagged observations.");
    } finally {
      if (generation === workspaceGeneration.current) setFlaggedLoading(false);
    }
  }

  async function runCoverageReport(event: FormEvent<HTMLFormElement>) {
    const generation = workspaceGeneration.current;
    const requestOrganizationId = organizationId;
    event.preventDefault();
    setCoverageError("");
    setCoverageReport(null);
    const latitude = Number(coverageQuery.latitude);
    const longitude = Number(coverageQuery.longitude);
    if (!coverageQuery.variable.trim() || !coverageQuery.latitude.trim() || !coverageQuery.longitude.trim() ||
        !Number.isFinite(latitude) || latitude < -90 || latitude > 90 ||
        !Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
      setCoverageError("Enter a variable and valid station coordinates (latitude −90 to 90, longitude −180 to 180).");
      return;
    }
    if (!coverageQuery.start_date || !coverageQuery.end_date ||
        coverageQuery.end_date < coverageQuery.start_date) {
      setCoverageError("Choose a valid date range; the end date must not precede the start date.");
      return;
    }
    const start = new Date(coverageQuery.start_date + "T00:00:00Z");
    const end = new Date(coverageQuery.end_date + "T00:00:00Z");
    if ((end.getTime() - start.getTime()) / 86400000 + 1 > 366) {
      setCoverageError("Coverage windows are limited to 366 calendar days.");
      return;
    }
    const params = new URLSearchParams({
      variable: coverageQuery.variable.trim(),
      latitude: String(latitude),
      longitude: String(longitude),
      start_date: coverageQuery.start_date,
      end_date: coverageQuery.end_date,
    });
    setCoverageLoading(true);
    try {
      const report = await apiGet<DailyCoverageReport>(
        "/organizations/" + requestOrganizationId + "/climate-observations/coverage?" + params.toString(),
      );
      if (generation === workspaceGeneration.current) setCoverageReport(report);
    } catch (cause) {
      if (generation === workspaceGeneration.current) setCoverageError(cause instanceof Error ? cause.message : "Unable to calculate station coverage.");
    } finally {
      if (generation === workspaceGeneration.current) setCoverageLoading(false);
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

  async function loadAnalysisRuns(datasetId: string) {
    setAnalysisRunsLoading(datasetId);
    try {
      const items = await apiGet<ResearchAnalysisRun[]>(
        "/organizations/" + organizationId + "/research-datasets/" + datasetId + "/analysis-runs?limit=100",
      );
      setAnalysisRuns((current) => ({ ...current, [datasetId]: items }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load reproducible analysis history.");
    } finally {
      setAnalysisRunsLoading(null);
    }
  }

  async function loadDatasetManifest(datasetId: string) {
    setManifestLoading(datasetId);
    try {
      const manifest = await apiGet<DatasetManifest>(
        "/organizations/" + organizationId + "/research-datasets/" + datasetId + "/manifest",
      );
      setDatasetManifests((current) => ({ ...current, [datasetId]: manifest }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to verify the approved dataset manifest.");
    } finally {
      setManifestLoading(null);
    }
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
  async function loadEvidenceLedger() {
    if (!evidenceStudyId) return;
    setEvidenceLoading(true);
    setError("");
    setEvidenceLedger(null);
    try {
      const report = await apiGet<EvidenceLedger>(
        `/organizations/${organizationId}/research-studies/${evidenceStudyId}/evidence-ledger?limit=100`,
      );
      setEvidenceLedger(report);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load the study evidence ledger.");
    } finally {
      setEvidenceLoading(false);
    }
  }

  async function downloadEvidenceLedger() {
    if (!evidenceStudyId) return;
    setEvidenceExporting(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(
        `/api/backend/organizations/${organizationId}/research-studies/${evidenceStudyId}/evidence-ledger/export?limit=100`,
        { credentials: "same-origin", cache: "no-store", headers: { Accept: "text/csv" } },
      );
      if (!response.ok) throw new Error(`Evidence export failed (${response.status}).`);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `research-evidence-${evidenceStudyId}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setNotice("Study evidence ledger CSV downloaded. The export contains metadata and aggregate climate review counts only.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to download the study evidence ledger.");
    } finally {
      setEvidenceExporting(false);
    }
  }

  async function loadStudyGovernance(studyId: string) {
    const generation = workspaceGeneration.current;
    const request = ++governanceRequest.current;
    setGovernanceStudyId(studyId);
    setGovernanceLoading(true);
    setError("");
    setProtocolVersions([]);
    setProtocolReviews({});
    setEthicsReviews([]);
    try {
      const [protocols, ethics] = await Promise.all([
        apiGet<ProtocolVersion[]>(`/organizations/${organizationId}/research-studies/${studyId}/protocol-versions?limit=100`),
        apiGet<EthicsReview[]>(`/organizations/${organizationId}/research-studies/${studyId}/ethics-reviews?limit=100`),
      ]);
      const reviewEntries = await Promise.all(protocols.map(async (protocol) => [
        protocol.id,
        await apiGet<ProtocolReview[]>(`/organizations/${organizationId}/research-studies/${studyId}/protocol-versions/${protocol.id}/reviews?limit=100`),
      ] as const));
      if (generation !== workspaceGeneration.current || request !== governanceRequest.current) return;
      setProtocolVersions(protocols);
      setProtocolReviews(Object.fromEntries(reviewEntries));
      setEthicsReviews(ethics);
    } catch (cause) {
      if (generation === workspaceGeneration.current && request === governanceRequest.current) {
        setError(cause instanceof Error ? cause.message : "Unable to load study governance records.");
      }
    } finally {
      if (generation === workspaceGeneration.current && request === governanceRequest.current) setGovernanceLoading(false);
    }
  }

  async function createProtocolVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!governanceStudyId) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    setGovernanceBusy(true); setError(""); setNotice("");
    try {
      const created = await apiPost<ProtocolVersion>(
        `/organizations/${organizationId}/research-studies/${governanceStudyId}/protocol-versions`,
        {
          title: String(values.get("protocol_title") || ""),
          objectives: String(values.get("protocol_objectives") || ""),
          methodology: String(values.get("protocol_methodology") || ""),
          sampling_and_participants: String(values.get("protocol_sampling") || "") || null,
          data_management: String(values.get("protocol_data") || "") || null,
          risk_and_safeguarding: String(values.get("protocol_risk") || "") || null,
        },
      );
      setProtocolVersions((current) => [created, ...current]);
      form.reset();
      setNotice(`Protocol version ${created.version_number} saved as a draft.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create protocol version.");
    } finally { setGovernanceBusy(false); }
  }

  async function submitProtocolVersion(protocolId: string) {
    setGovernanceBusy(true); setError(""); setNotice("");
    try {
      const updated = await apiPost<ProtocolVersion>(
        `/organizations/${organizationId}/research-studies/${governanceStudyId}/protocol-versions/${protocolId}/submit`, {},
      );
      setProtocolVersions((items) => items.map((item) => item.id === protocolId ? updated : item));
      setNotice(`Protocol v${updated.version_number} submitted for independent review.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to submit protocol."); }
    finally { setGovernanceBusy(false); }
  }

  async function reviewProtocolVersion(protocolId: string, decision: "approved" | "revisions_required" | "rejected") {
    const note = (protocolReviewNotes[protocolId] || "").trim();
    if (note.length < 10) { setError("Enter a review note of at least 10 characters before recording a decision."); return; }
    setGovernanceBusy(true); setError(""); setNotice("");
    try {
      await apiPost<ProtocolReview>(
        `/organizations/${organizationId}/research-studies/${governanceStudyId}/protocol-versions/${protocolId}/reviews`,
        { decision, note },
      );
      await loadStudyGovernance(governanceStudyId);
      setNotice(`Protocol review recorded: ${decision.replace(/_/g, " ")}.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to record protocol review."); }
    finally { setGovernanceBusy(false); }
  }

  async function recordEthicsReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setGovernanceBusy(true); setError(""); setNotice("");
    try {
      const created = await apiPost<EthicsReview>(
        `/organizations/${organizationId}/research-studies/${governanceStudyId}/ethics-reviews`,
        {
          protocol_version_id: String(values.get("ethics_protocol") || ""),
          decision: String(values.get("ethics_decision") || "approved"),
          reference: String(values.get("ethics_reference") || "") || null,
          note: String(values.get("ethics_note") || ""),
        },
      );
      setEthicsReviews((items) => [created, ...items]);
      form.reset();
      setNotice(`Ethics decision recorded: ${created.decision}.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to record ethics decision."); }
    finally { setGovernanceBusy(false); }
  }

  async function transitionStudy(studyId: string, targetStatus: string) {
    setLifecycleSaving(studyId);
    setError("");
    setNotice("");
    try {
      const updated = await apiPatch<Study>(
        `/organizations/${organizationId}/research-studies/${studyId}/status`,
        { status: targetStatus },
      );
      setStudies((current) => current.map((item) => item.id === studyId ? updated : item));
      if (evidenceStudyId === studyId) setEvidenceLedger(null);
      setNotice(`Study lifecycle advanced to ${updated.status.replace(/_/g, " ")}. The transition was recorded in the organisation audit trail.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update the study lifecycle.");
    } finally {
      setLifecycleSaving(null);
    }
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
                <section className="research-section climate-submission-panel">
                  <div className="section-heading"><div><p className="eyebrow">FIELD DATA</p><h2>Submit a climate observation</h2></div><span>Pending independent review</span></div>
                  <p className="workspace-muted">Each submission records its timestamp, measurement unit, coordinates and source. New observations are pending and are excluded from verified summaries until independently reviewed.</p>
                  <form className="climate-submission-form" onSubmit={submitClimateObservation}>
                    <label>Observed at (local time)<input type="datetime-local" name="observed_at" required /></label>
                    <label>Variable<input name="variable" minLength={2} maxLength={80} required placeholder="e.g. precipitation" /></label>
                    <label>Value<input name="value" type="number" step="any" required /></label>
                    <label>Unit<input name="unit" minLength={1} maxLength={32} required placeholder="e.g. mm/day" /></label>
                    <label>Latitude<input name="latitude" type="number" min="-90" max="90" step="any" required /></label>
                    <label>Longitude<input name="longitude" type="number" min="-180" max="180" step="any" required /></label>
                    <label>Source<input name="source" minLength={2} maxLength={160} required placeholder="Instrument, station or source reference" /></label>
                    <label>Linked study (optional)<select name="study_id" defaultValue=""><option value="">No linked study</option>{studies.map((study) => <option value={study.id} key={study.id}>{study.title}</option>)}</select></label>
                    <button className="primary-action" disabled={climateSubmitting}>{climateSubmitting ? "Submitting…" : "Submit observation"}</button>
                  </form>
                  <div className="section-heading climate-queue-heading"><div><p className="eyebrow">QUALITY CONTROL</p><h3>Pending observations</h3></div><button type="button" className="secondary-action" disabled={climateListLoading} onClick={() => void loadClimateObservations()}>{climateListLoading ? "Refreshing…" : "Refresh queue"}</button></div>
                  {climateObservations.length === 0 ? <p className="workspace-muted">The pending queue has not been loaded or contains no observations. Refresh to check.</p> : (
                    <div className="climate-observation-list">{climateObservations.map((item) => (
                      <article className="climate-observation-card" key={item.id}>
                        <div><strong>{item.variable}: {formatStatistic(item.value)} {item.unit}</strong><span>{new Date(item.observed_at).toLocaleString()} · {item.source}</span><span>Coordinates: {item.latitude.toFixed(5)}, {item.longitude.toFixed(5)}</span></div>
                        {isReviewer && <div className="climate-review-controls"><label>Review note<textarea rows={2} maxLength={2000} value={climateReviewNotes[item.id] || ""} onChange={(event) => setClimateReviewNotes((items) => ({ ...items, [item.id]: event.target.value }))} placeholder="Optional quality-review note" /></label><div className="dataset-review-actions"><button type="button" className="primary-action" disabled={climateSubmitting} onClick={() => void reviewClimateObservation(item.id, "verified")}>Verify</button><button type="button" className="secondary-action" disabled={climateSubmitting} onClick={() => void reviewClimateObservation(item.id, "rejected")}>Reject</button></div></div>}
                      </article>
                    ))}</div>
                  )}
                  <p className="workspace-muted">Reviewers must not verify their own submissions. The API enforces independent review and prevents decisions on already reviewed observations.</p>
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
                <section className="research-section climate-analysis-panel">
                  <div className="section-heading"><div><p className="eyebrow">SPATIAL DATA</p><h2>Observation area query</h2></div><span>WGS84 · max 500 rows</span></div>
                  <p className="workspace-muted">Filter observations by a geographic bounding box. The initial extent covers Kenya; narrow it to an area of interest. This is a coordinate query, not a map or an interpolated surface.</p>
                  <form className="climate-analysis-form" onSubmit={runSpatialClimateQuery}>
                    <label>West longitude<input type="number" step="any" min="-180" max="180" required value={spatialQuery.west} onChange={(event) => setSpatialQuery((q) => ({ ...q, west: event.target.value }))} /></label>
                    <label>South latitude<input type="number" step="any" min="-90" max="90" required value={spatialQuery.south} onChange={(event) => setSpatialQuery((q) => ({ ...q, south: event.target.value }))} /></label>
                    <label>East longitude<input type="number" step="any" min="-180" max="180" required value={spatialQuery.east} onChange={(event) => setSpatialQuery((q) => ({ ...q, east: event.target.value }))} /></label>
                    <label>North latitude<input type="number" step="any" min="-90" max="90" required value={spatialQuery.north} onChange={(event) => setSpatialQuery((q) => ({ ...q, north: event.target.value }))} /></label>
                    <label>Variable (optional)<input value={spatialQuery.variable} onChange={(event) => setSpatialQuery((q) => ({ ...q, variable: event.target.value }))} maxLength={80} placeholder="e.g. precipitation" /></label>
                    <label>Quality status<select value={spatialQuery.quality_status} onChange={(event) => setSpatialQuery((q) => ({ ...q, quality_status: event.target.value as SpatialClimateQuery["quality_status"] }))}><option value="">All statuses</option><option value="verified">Verified</option><option value="pending">Pending</option><option value="rejected">Rejected</option></select></label>
                    <label>Start (optional)<input type="datetime-local" value={spatialQuery.start} onChange={(event) => setSpatialQuery((q) => ({ ...q, start: event.target.value }))} /></label>
                    <label>End (optional)<input type="datetime-local" value={spatialQuery.end} onChange={(event) => setSpatialQuery((q) => ({ ...q, end: event.target.value }))} /></label>
                    <button className="primary-action" disabled={spatialLoading}>{spatialLoading ? "Querying…" : "Find observations"}</button>
                  </form>
                  {spatialError && <p className="workspace-error" role="alert">{spatialError}</p>}
                  {spatialResults && <div className="climate-analysis-results" aria-live="polite">
                    <p><strong>{spatialResults.length.toLocaleString()}</strong> observations returned (maximum 500 per query).</p>
                    {spatialResults.length === 0 ? <p className="workspace-muted">No observations match this area and filter set.</p> : (
                      <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Observed</th><th>Variable</th><th>Value</th><th>Coordinates</th><th>Source</th><th>Quality</th></tr></thead>
                        <tbody>{spatialResults.map((item) => <tr key={item.id}><td>{new Date(item.observed_at).toLocaleString()}</td><td>{item.variable}</td><td>{formatStatistic(item.value)} {item.unit}</td><td>{item.latitude.toFixed(5)}, {item.longitude.toFixed(5)}</td><td>{item.source}</td><td><span className="status-chip">{item.quality_status}</span></td></tr>)}</tbody>
                      </table></div>
                    )}
                  </div>}
                </section>
                <section className="research-section climate-analysis-panel">
                  <div className="section-heading"><div><p className="eyebrow">QUALITY SCREENING</p><h2>Flagged observations</h2></div><span>Scan cap 5,000 · page size 200</span></div>
                  <p className="workspace-muted">Provider screening flags identify records for further review. They are not scientific validation or an automatic rejection decision.</p>
                  <div className="climate-analysis-form">
                    <label>Exact flag (optional)<input value={flaggedName} onChange={(event) => setFlaggedName(event.target.value)} minLength={2} maxLength={80} placeholder="e.g. outside_expected_range" /></label>
                    <label>Quality status<select value={flaggedQuality} onChange={(event) => setFlaggedQuality(event.target.value as typeof flaggedQuality)}><option value="">All statuses</option><option value="pending">Pending</option><option value="verified">Verified</option><option value="rejected">Rejected</option></select></label>
                    <label>Start (optional)<input type="datetime-local" value={flaggedStart} onChange={(event) => setFlaggedStart(event.target.value)} /></label>
                    <label>End (optional, exclusive)<input type="datetime-local" value={flaggedEnd} onChange={(event) => setFlaggedEnd(event.target.value)} /></label>
                    <button type="button" className="primary-action" disabled={flaggedLoading} onClick={() => void loadFlaggedObservations()}>{flaggedLoading ? "Scanning…" : "Load flagged observations"}</button>
                  </div>
                  {flaggedError && <p className="workspace-error" role="alert">{flaggedError}</p>}
                  {flaggedReport && <div className="climate-analysis-results" aria-live="polite">
                    <div className="research-metrics">
                      <article><span>Scanned</span><strong>{flaggedReport.scanned_count.toLocaleString()}</strong></article>
                      <article><span>Matched</span><strong>{flaggedReport.matched_count.toLocaleString()}</strong></article>
                      <article><span>Displayed</span><strong>{flaggedReport.items.length.toLocaleString()}</strong></article>
                      <article><span>Scan complete</span><strong>{flaggedReport.scan_truncated ? "No" : "Yes"}</strong></article>
                    </div>
                    {flaggedReport.scan_truncated && <p className="workspace-notice">The scan reached its 5,000-record cap. This report may omit older flagged observations; narrow the period or use the API for additional filtering.</p>}
                    {flaggedReport.items.length === 0 ? <p className="workspace-muted">No flagged observations matched the selected filters in the scanned records.</p> : (
                      <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Observed</th><th>Measurement</th><th>Coordinates</th><th>Source</th><th>Quality</th><th>Screening flags</th></tr></thead>
                        <tbody>{flaggedReport.items.map((item) => <tr key={item.id}><td>{new Date(item.observed_at).toLocaleString()}</td><td>{item.variable}: {formatStatistic(item.value)} {item.unit}</td><td>{item.latitude.toFixed(5)}, {item.longitude.toFixed(5)}</td><td>{item.source}</td><td>{item.quality_status}</td><td>{item.flags.join(", ")}</td></tr>)}</tbody>
                      </table></div>
                    )}
                    <div className="dataset-review-actions" aria-label="Flagged observation pagination">
                      <button type="button" className="secondary-action" disabled={flaggedLoading || flaggedOffset === 0} onClick={() => void loadFlaggedObservations(Math.max(0, flaggedOffset - flaggedReport.limit))}>Previous</button>
                      <span className="workspace-muted">Showing {flaggedReport.matched_count === 0 ? 0 : flaggedOffset + 1}–{flaggedOffset + flaggedReport.items.length} of {flaggedReport.matched_count} scanned matches</span>
                      <button type="button" className="secondary-action" disabled={flaggedLoading || flaggedOffset + flaggedReport.items.length >= flaggedReport.matched_count} onClick={() => void loadFlaggedObservations(flaggedOffset + flaggedReport.limit)}>Next</button>
                    </div>
                  </div>}
                </section>
                <section className="research-section climate-analysis-panel">
                  <div className="section-heading"><div><p className="eyebrow">STATION COMPLETENESS</p><h2>Daily coverage report</h2></div><span>Maximum 366 days</span></div>
                  <p className="workspace-muted">Check whether a station has at least one non-rejected observation per calendar day for a variable. Station matching uses a coordinate tolerance of 0.0001 degrees; pending observations count as observed.</p>
                  <form className="climate-analysis-form" onSubmit={runCoverageReport}>
                    <label>Variable<input value={coverageQuery.variable} onChange={(event) => setCoverageQuery((q) => ({ ...q, variable: event.target.value }))} minLength={2} maxLength={80} required /></label>
                    <label>Station latitude<input type="number" step="any" min="-90" max="90" value={coverageQuery.latitude} onChange={(event) => setCoverageQuery((q) => ({ ...q, latitude: event.target.value }))} required /></label>
                    <label>Station longitude<input type="number" step="any" min="-180" max="180" value={coverageQuery.longitude} onChange={(event) => setCoverageQuery((q) => ({ ...q, longitude: event.target.value }))} required /></label>
                    <label>Start date<input type="date" value={coverageQuery.start_date} onChange={(event) => setCoverageQuery((q) => ({ ...q, start_date: event.target.value }))} required /></label>
                    <label>End date<input type="date" value={coverageQuery.end_date} onChange={(event) => setCoverageQuery((q) => ({ ...q, end_date: event.target.value }))} required /></label>
                    <button className="primary-action" disabled={coverageLoading}>{coverageLoading ? "Calculating…" : "Calculate coverage"}</button>
                  </form>
                  {coverageError && <p className="workspace-error" role="alert">{coverageError}</p>}
                  {coverageReport && <div className="climate-analysis-results" aria-live="polite">
                    <div className="research-metrics">
                      <article><span>Expected days</span><strong>{coverageReport.expected_days}</strong></article>
                      <article><span>Observed days</span><strong>{coverageReport.observed_days}</strong></article>
                      <article><span>Missing days</span><strong>{coverageReport.missing_days.length}</strong></article>
                      <article><span>Coverage</span><strong>{(coverageReport.coverage_ratio * 100).toFixed(2)}%</strong></article>
                    </div>
                    <p className="workspace-muted">{coverageReport.variable} at {coverageReport.latitude.toFixed(5)}, {coverageReport.longitude.toFixed(5)} · {coverageReport.start_date} to {coverageReport.end_date}.</p>
                    {coverageReport.missing_days.length === 0 ? <p className="workspace-notice">No missing calendar days were detected for this station and variable.</p> : <div><strong>Missing calendar days</strong><p className="workspace-muted">{coverageReport.missing_days.join(", ")}</p></div>}
                    <p className="workspace-muted">Policy: {coverageReport.missing_data_policy.replace(/_/g, " ")}. Missing values are reported, never filled or inferred.</p>
                  </div>}
                </section>
                <section className="research-section climate-analysis-panel">
                  <div className="section-heading"><div><p className="eyebrow">CLIMATE INTELLIGENCE</p><h2>Monthly precipitation anomalies</h2></div><span>Daily data · exact location</span></div>
                  <p className="workspace-muted">Compare each target calendar month with the same month in the baseline years. Only verified daily precipitation in mm/day is used. Incomplete months are excluded without imputation; this standardized score is not SPI or a drought classification.</p>
                  <form className="climate-analysis-form" onSubmit={runMonthlyPrecipitationAnomaly}>
                    <label>Latitude<input type="number" step="any" min="-90" max="90" value={monthlyAnomalyQuery.latitude} onChange={(event) => setMonthlyAnomalyQuery((q) => ({ ...q, latitude: event.target.value }))} required /></label>
                    <label>Longitude<input type="number" step="any" min="-180" max="180" value={monthlyAnomalyQuery.longitude} onChange={(event) => setMonthlyAnomalyQuery((q) => ({ ...q, longitude: event.target.value }))} required /></label>
                    <label>Baseline start<input type="date" value={monthlyAnomalyQuery.baseline_start} onChange={(event) => setMonthlyAnomalyQuery((q) => ({ ...q, baseline_start: event.target.value }))} required /></label>
                    <label>Baseline end<input type="date" value={monthlyAnomalyQuery.baseline_end} onChange={(event) => setMonthlyAnomalyQuery((q) => ({ ...q, baseline_end: event.target.value }))} required /></label>
                    <label>Target start<input type="date" value={monthlyAnomalyQuery.target_start} onChange={(event) => setMonthlyAnomalyQuery((q) => ({ ...q, target_start: event.target.value }))} required /></label>
                    <label>Target end<input type="date" value={monthlyAnomalyQuery.target_end} onChange={(event) => setMonthlyAnomalyQuery((q) => ({ ...q, target_end: event.target.value }))} required /></label>
                    <label>Minimum daily completeness<input type="number" min="0.01" max="1" step="0.01" value={monthlyAnomalyQuery.minimum_completeness} onChange={(event) => setMonthlyAnomalyQuery((q) => ({ ...q, minimum_completeness: event.target.value }))} required /></label>
                    <label>Minimum baseline years<input type="number" min="2" max="100" step="1" value={monthlyAnomalyQuery.minimum_baseline_years} onChange={(event) => setMonthlyAnomalyQuery((q) => ({ ...q, minimum_baseline_years: event.target.value }))} required /></label>
                    <button className="primary-action" disabled={monthlyAnomalyLoading || !organizationId}>{monthlyAnomalyLoading ? "Calculating…" : "Calculate monthly anomalies"}</button>
                  </form>
                  {monthlyAnomalyError && <p className="workspace-error" role="alert">{monthlyAnomalyError}</p>}
                  {monthlyAnomaly && <div className="climate-analysis-results" aria-live="polite">
                    <div className="research-metrics">
                      <article><span>Months returned</span><strong>{monthlyAnomaly.points.length}</strong></article>
                      <article><span>Observations scanned</span><strong>{monthlyAnomaly.observation_count.toLocaleString()}</strong></article>
                      <article><span>Baseline minimum</span><strong>{monthlyAnomaly.minimum_baseline_years} years</strong></article>
                      <article><span>Quality status</span><strong>{monthlyAnomaly.quality_status}</strong></article>
                    </div>
                    <div className="section-heading"><span className="workspace-muted">Reproducible table export · CSV</span><button type="button" className="secondary-action" onClick={exportMonthlyAnomalyCsv}>Export results CSV</button></div>\n                    <div className="research-table-wrap"><table className="research-table"><thead><tr><th>Month</th><th>Observed total</th><th>Completeness</th><th>Baseline mean</th><th>Baseline SD</th><th>Baseline years</th><th>Standardized anomaly</th></tr></thead>
                      <tbody>{monthlyAnomaly.points.map((point) => <tr key={`${point.year}-${point.month}`}><td>{new Date(Date.UTC(point.year, point.month - 1, 1)).toLocaleDateString(undefined, { month: "short", year: "numeric", timeZone: "UTC" })}</td><td>{point.observed_total_mm.toFixed(2)} mm</td><td>{(point.completeness * 100).toFixed(1)}%</td><td>{point.baseline_mean_mm.toFixed(2)} mm</td><td>{point.baseline_sample_standard_deviation_mm.toFixed(2)} mm</td><td>{point.baseline_year_count}</td><td>{point.standardized_anomaly.toFixed(3)}</td></tr>)}</tbody>
                    </table></div>
                    <p className="workspace-muted">Sources: {monthlyAnomaly.provenance_sources.join(", ") || "Not recorded"}. Providers: {monthlyAnomaly.provider_ids.join(", ") || "Not recorded"}. Ingestion runs: {monthlyAnomaly.ingestion_run_ids.length}. Location: {monthlyAnomaly.latitude}, {monthlyAnomaly.longitude}.</p>
                    <p className="workspace-muted">Method: sample-standardized anomaly z-score. Classification remains unclassified; do not interpret this output as SPI or a drought category.</p>
                  </div>}
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
                        {isReviewer && STUDY_NEXT_STATUS[study.status] && (
                          <div className="dataset-review-actions">
                            <button
                              type="button"
                              className="secondary-action"
                              disabled={lifecycleSaving === study.id}
                              onClick={() => void transitionStudy(study.id, STUDY_NEXT_STATUS[study.status].status)}
                            >
                              {lifecycleSaving === study.id ? "Updating…" : STUDY_NEXT_STATUS[study.status].label}
                            </button>
                          </div>
                        )}
                        <div className="dataset-review-actions">
                          <button type="button" className="secondary-action" onClick={() => void loadStudyGovernance(study.id)} disabled={governanceLoading && governanceStudyId === study.id}>
                            {governanceLoading && governanceStudyId === study.id ? "Loading governance…" : governanceStudyId === study.id ? "Refresh governance" : "Manage protocol & ethics"}
                          </button>
                        </div>
                      </article>
                    ))}</div>
                  )}
                </section>
                {governanceStudyId && (
                  <section className="research-section" aria-live="polite">
                    <div className="section-heading"><div><p className="eyebrow">RESEARCH GOVERNANCE</p><h2>Protocol and ethics workspace</h2><p>{studies.find((item) => item.id === governanceStudyId)?.title || "Selected study"} · immutable protocol versions and independent decisions</p></div><button type="button" className="secondary-action" onClick={() => { governanceRequest.current += 1; setGovernanceStudyId(""); }}>Close</button></div>
                    {governanceLoading ? <p className="workspace-muted">Loading governance history…</p> : <>
                      {(studies.find((item) => item.id === governanceStudyId)?.lead_researcher_id === membership?.user_id || canAuthorProtocols) && (
                        <section className="staff-card">
                          <p className="eyebrow">RESEARCH DESIGN</p><h3>Create protocol version</h3>
                          <p>Each submission creates a new immutable version. Existing versions cannot be overwritten.</p>
                          <form onSubmit={createProtocolVersion}>
                            <label>Protocol title<input name="protocol_title" minLength={3} maxLength={240} required /></label>
                            <label>Research objectives<textarea name="protocol_objectives" minLength={20} maxLength={12000} rows={3} required /></label>
                            <label>Methodology<textarea name="protocol_methodology" minLength={30} maxLength={20000} rows={5} required /></label>
                            <label>Sampling and participants<textarea name="protocol_sampling" maxLength={12000} rows={3} /></label>
                            <label>Data management<textarea name="protocol_data" maxLength={12000} rows={3} /></label>
                            <label>Risk and safeguarding<textarea name="protocol_risk" maxLength={12000} rows={3} /></label>
                            <button className="primary-action" disabled={governanceBusy}>{governanceBusy ? "Saving…" : "Save protocol draft"}</button>
                          </form>
                        </section>
                      )}
                      <h3>Protocol versions</h3>
                      {protocolVersions.length === 0 ? <p className="workspace-muted">No protocol versions have been created for this study.</p> : protocolVersions.map((protocol) => (
                        <article className="research-record" key={protocol.id}>
                          <div className="research-record-top"><strong>Version {protocol.version_number}: {protocol.title}</strong><span className="status-chip">{protocol.status.replace(/_/g, " ")}</span></div>
                          <p><strong>Objectives:</strong> {protocol.objectives}</p><p><strong>Methodology:</strong> {protocol.methodology}</p>
                          {protocol.sampling_and_participants && <p><strong>Sampling:</strong> {protocol.sampling_and_participants}</p>}
                          {protocol.data_management && <p><strong>Data management:</strong> {protocol.data_management}</p>}
                          {protocol.risk_and_safeguarding && <p><strong>Risk and safeguarding:</strong> {protocol.risk_and_safeguarding}</p>}
                          {protocol.status === "draft" && (studies.find((item) => item.id === governanceStudyId)?.lead_researcher_id === membership?.user_id || canAuthorProtocols) && <button type="button" className="secondary-action" disabled={governanceBusy} onClick={() => void submitProtocolVersion(protocol.id)}>Submit for independent review</button>}
                          {isReviewer && protocol.status === "submitted" && studies.find((item) => item.id === governanceStudyId)?.lead_researcher_id !== membership?.user_id && <div className="climate-review-controls"><label>Independent review note<textarea rows={3} minLength={10} maxLength={5000} value={protocolReviewNotes[protocol.id] || ""} onChange={(event) => setProtocolReviewNotes((items) => ({ ...items, [protocol.id]: event.target.value }))} placeholder="Assess methods, participant safeguards and data management" /></label><div className="dataset-review-actions"><button type="button" className="primary-action" disabled={governanceBusy} onClick={() => void reviewProtocolVersion(protocol.id, "approved")}>Approve</button><button type="button" className="secondary-action" disabled={governanceBusy} onClick={() => void reviewProtocolVersion(protocol.id, "revisions_required")}>Request revisions</button><button type="button" className="secondary-action" disabled={governanceBusy} onClick={() => void reviewProtocolVersion(protocol.id, "rejected")}>Reject</button></div></div>}
                          <h4>Review history</h4>
                          {(protocolReviews[protocol.id] || []).length === 0 ? <p className="workspace-muted">No independent reviews recorded.</p> : (protocolReviews[protocol.id] || []).map((review) => <p key={review.id} className="workspace-muted">{review.decision.replace(/_/g, " ")} · {new Date(review.reviewed_at).toLocaleString()} · {review.note}</p>)}
                        </article>
                      ))}
                      {isReviewer && protocolVersions.some((protocol) => protocol.status === "approved") && (
                        <section className="staff-card"><p className="eyebrow">ETHICS COMMITTEE</p><h3>Record formal ethics decision</h3><p>Only an approved protocol version can receive an ethics decision. The reviewer must be independent of its authors and study lead.</p>
                          <form onSubmit={recordEthicsReview}>
                            <label>Approved protocol version<select name="ethics_protocol" required defaultValue=""><option value="">Select approved version</option>{protocolVersions.filter((protocol) => protocol.status === "approved").map((protocol) => <option key={protocol.id} value={protocol.id}>v{protocol.version_number} · {protocol.title}</option>)}</select></label>
                            <label>Decision<select name="ethics_decision" defaultValue="approved"><option value="approved">Approved</option><option value="exempt">Exempt</option><option value="revisions_required">Revisions required</option><option value="rejected">Rejected</option></select></label>
                            <label>Committee reference<input name="ethics_reference" maxLength={160} /></label>
                            <label>Decision rationale<textarea name="ethics_note" minLength={10} maxLength={5000} rows={3} required /></label>
                            <button className="primary-action" disabled={governanceBusy}>{governanceBusy ? "Recording…" : "Record ethics decision"}</button>
                          </form>
                        </section>
                      )}
                      <h3>Ethics review history</h3>
                      {ethicsReviews.length === 0 ? <p className="workspace-muted">No ethics committee decisions recorded.</p> : ethicsReviews.map((review) => <article className="research-record" key={review.id}><div className="research-record-top"><strong>{review.decision.replace(/_/g, " ")}</strong><span>{review.reference || "No committee reference"}</span></div><p>{review.note}</p><p className="workspace-muted">{review.protocol_version_id ? `Protocol ${protocolVersions.find((item) => item.id === review.protocol_version_id)?.version_number ?? "version"}` : "No linked protocol"} · {new Date(review.reviewed_at).toLocaleString()}</p></article>)}
                    </>}
                  </section>
                )}
                <section className="research-section">
                  <div className="section-heading"><div><p className="eyebrow">RESEARCH TRACEABILITY</p><h2>Study evidence ledger</h2><p>Connect approved dataset fingerprints, reproducible analysis runs, publications and reviewed climate records.</p></div></div>
                  <div className="research-form-pair">
                    <label>Research study<select value={evidenceStudyId} onChange={(event) => { setEvidenceStudyId(event.target.value); setEvidenceLedger(null); }}><option value="">Select a study</option>{studies.map((study) => <option value={study.id} key={study.id}>{study.title}</option>)}</select></label>
                    <div className="form-actions"><button type="button" className="primary-action" disabled={!evidenceStudyId || evidenceLoading} onClick={() => void loadEvidenceLedger()}>{evidenceLoading ? "Building ledger…" : "Build evidence ledger"}</button><button type="button" className="secondary-action" disabled={!evidenceStudyId || evidenceExporting} onClick={() => void downloadEvidenceLedger()}>{evidenceExporting ? "Preparing CSV…" : "Download CSV"}</button></div>
                  </div>
                  {evidenceLedger && (
                    <div className="research-record">
                      <p className="workspace-muted">Snapshot generated {new Date(evidenceLedger.generated_at).toLocaleString()}. This is a traceability inventory, not independent scientific validation.</p>
                      <div className="research-record-grid">
                        <article><strong>{evidenceLedger.datasets.length}</strong><span>Approved datasets</span></article>
                        <article><strong>{evidenceLedger.analysis_runs.length}</strong><span>Analysis runs</span></article>
                        <article><strong>{evidenceLedger.publications.length}</strong><span>Publications</span></article>
                        <article><strong>{evidenceLedger.climate.observation_count}</strong><span>Climate observations</span></article>
                        <article><strong>{evidenceLedger.climate.verified_count}</strong><span>Verified observations</span></article>
                        <article><strong>{evidenceLedger.climate.pending_count}</strong><span>Pending review</span></article>
                      </div>
                      <h3>Study governance</h3>
                      <div className="research-record-grid">
                        <article><strong>{evidenceLedger.governance.study_status.replace(/_/g, " ")}</strong><span>Study lifecycle</span></article>
                        <article><strong>{evidenceLedger.governance.protocol_version_count}</strong><span>Protocol versions</span></article>
                        <article><strong>{evidenceLedger.governance.latest_protocol_version_number ?? "—"}</strong><span>Latest protocol version</span></article>
                        <article><strong>{evidenceLedger.governance.latest_protocol_status || "Not recorded"}</strong><span>Latest protocol state</span></article>
                        <article><strong>{evidenceLedger.governance.latest_protocol_review_decision || "Not reviewed"}</strong><span>Latest protocol decision</span></article>
                        <article><strong>{evidenceLedger.governance.ethics_review_count}</strong><span>Ethics decisions</span></article>
                        <article><strong>{evidenceLedger.governance.latest_ethics_decision || "Not recorded"}</strong><span>Latest ethics outcome</span></article>
                      </div>
                      <p className="workspace-muted">Study ethics reference: {evidenceLedger.governance.study_ethics_reference || "Not recorded"}. Latest protocol review: {evidenceLedger.governance.latest_protocol_reviewed_at ? new Date(evidenceLedger.governance.latest_protocol_reviewed_at).toLocaleString() : "Not recorded"}. Latest ethics reference: {evidenceLedger.governance.latest_ethics_reference || "Not recorded"}. Latest ethics review: {evidenceLedger.governance.latest_ethics_reviewed_at ? new Date(evidenceLedger.governance.latest_ethics_reviewed_at).toLocaleString() : "Not recorded"}.</p>
                      <h3>Dataset fingerprints</h3>
                      {evidenceLedger.datasets.length === 0 ? <p className="workspace-muted">No approved study datasets.</p> : evidenceLedger.datasets.map((item) => <div className="research-record" key={item.dataset_id}><strong>{item.title} · v{item.version}</strong><p>{item.file_count} clean, available file versions · {item.access_classification}{item.files_truncated ? " · file list truncated at 1,000" : ""}</p><code>{item.manifest_sha256}</code></div>)}
                      {evidenceLedger.datasets_truncated && <p className="workspace-muted">Dataset list truncated at 100 records.</p>}
                      <h3>Reproducibility checks</h3>
                      {evidenceLedger.analysis_runs.length === 0 ? <p className="workspace-muted">No recorded analysis runs for approved datasets.</p> : evidenceLedger.analysis_runs.map((run) => <div className="research-record" key={run.run_id}><strong>{run.software_name} {run.software_version}</strong><p>{new Date(run.created_at).toLocaleString()} · {run.output_artifact_count} output artifacts · revision {run.code_revision || "not recorded"}</p><span className="status-chip">{run.manifest_matches_current ? "Input manifest matches" : "Input manifest differs from current dataset"}</span><code>{run.input_manifest_sha256}</code></div>)}
                      {evidenceLedger.analysis_runs_truncated && <p className="workspace-muted">Analysis run list truncated at 100 records.</p>}
                      <h3>Published outputs</h3>
                      {evidenceLedger.publications.length === 0 ? <p className="workspace-muted">No publications registered.</p> : evidenceLedger.publications.map((publication) => <div className="research-record" key={publication.publication_id}><strong>{publication.title}</strong><p>{publication.publication_type} · DOI: {publication.doi || "not recorded"} · OpenAlex: {publication.openalex_id || "not recorded"} · metadata provenance records: {publication.metadata_provenance_count}</p></div>)}
                      {evidenceLedger.publications_truncated && <p className="workspace-muted">Publication list truncated at 100 records.</p>}
                      <p className="workspace-muted">Climate review states: {evidenceLedger.climate.verified_count} verified, {evidenceLedger.climate.pending_count} pending, {evidenceLedger.climate.rejected_count} rejected. Window: {evidenceLedger.climate.first_observed_at ? new Date(evidenceLedger.climate.first_observed_at).toLocaleDateString() : "—"} to {evidenceLedger.climate.last_observed_at ? new Date(evidenceLedger.climate.last_observed_at).toLocaleDateString() : "—"}.</p>
                    </div>
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
                            <button type="button" className="text-action" disabled={analysisRunsLoading === dataset.id || dataset.status !== "approved"} onClick={() => loadAnalysisRuns(dataset.id)}>{analysisRunsLoading === dataset.id ? "Loading analysis runs…" : "Reproducible analysis history"}</button>
                            <button type="button" className="text-action" disabled={manifestLoading === dataset.id || dataset.status !== "approved"} onClick={() => loadDatasetManifest(dataset.id)}>{manifestLoading === dataset.id ? "Verifying manifest…" : "Verify dataset integrity"}</button>
                            {datasetManifests[dataset.id] && <div className="dataset-review-history" aria-live="polite"><strong>Manifest SHA-256</strong><p><code>{datasetManifests[dataset.id].manifest_sha256}</code></p><p>{datasetManifests[dataset.id].file_count} clean, available file version(s) · dataset version {datasetManifests[dataset.id].dataset_version}</p><ul>{datasetManifests[dataset.id].files.map((file) => <li key={file.file_id + ":" + file.version}>{file.filename} · v{file.version} · SHA-256 {file.sha256.slice(0, 16)}…</li>)}</ul><small>Digest covers canonical dataset identity and clean file-version metadata; it does not expose storage locations or file contents.</small></div>}
                            {analysisRuns[dataset.id] && <div className="dataset-review-history" aria-live="polite">
                              {analysisRuns[dataset.id].length === 0 ? <p className="workspace-muted">No analysis runs have been recorded for this dataset.</p> : <ol>{analysisRuns[dataset.id].map((run) => <li key={run.id}>
                                <strong>{run.software_name} {run.software_version}</strong> · {new Date(run.created_at).toLocaleString()}
                                <p>Inputs: {run.input_file_versions.length} file version(s) · manifest SHA-256: {run.input_manifest_sha256.slice(0, 16)}…</p>
                                <p>Outputs: {run.output_artifacts.length} artifact(s){run.code_revision ? " · revision " + run.code_revision.slice(0, 12) : ""}</p>
                                <small>Run {run.id} · recorded by {run.created_by}</small>
                              </li>)}</ol>}
                            </div>}
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
