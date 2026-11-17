"""Contract tests for the study evidence ledger."""

from stagingnextgenearth.api.research_evidence import (
    EvidenceClimateSummary,
    EvidenceDataset,
    EvidencePublication,
    EvidenceAnalysisRun,
    ResearchEvidenceLedgerRead,
    router,
)


def test_evidence_ledger_route_is_read_only_and_bounded() -> None:
    route = next(
        item for item in router.routes
        if getattr(item, "path", "").endswith("/{study_id}/evidence-ledger")
    )
    assert route.methods == {"GET"}
    assert route.response_model == ResearchEvidenceLedgerRead
    limit = next(
        parameter for parameter in route.dependant.query_params
        if parameter.name == "limit"
    )
    assert any(getattr(item, "le", None) == 500 for item in limit.field_info.metadata)


def test_evidence_ledger_contract_exposes_traceability_not_private_file_data() -> None:
    report = ResearchEvidenceLedgerRead(
        study_id="study-1",
        study_title="Community rainfall monitoring",
        generated_at="2026-11-17T12:00:00Z",
        datasets=[
            EvidenceDataset(
                dataset_id="dataset-1",
                title="Rainfall observations",
                version="1.0",
                access_classification="organization",
                manifest_sha256="a" * 64,
                file_count=2,
            )
        ],
        analysis_runs=[
            EvidenceAnalysisRun(
                run_id="run-1",
                dataset_id="dataset-1",
                input_manifest_sha256="a" * 64,
                manifest_matches_current=True,
                software_name="NextGen Research",
                software_version="1.0",
                code_revision="abc123",
                output_artifact_count=1,
                created_at="2026-11-17T11:00:00Z",
            )
        ],
        publications=[
            EvidencePublication(
                publication_id="publication-1",
                title="Rainfall trends",
                publication_type="report",
                doi=None,
                openalex_id="W123456789",
                metadata_provenance_count=1,
            )
        ],
        climate=EvidenceClimateSummary(
            observation_count=10,
            verified_count=8,
            pending_count=1,
            rejected_count=1,
            first_observed_at="2026-01-01T00:00:00Z",
            last_observed_at="2026-01-10T00:00:00Z",
        ),
    )
    payload = report.model_dump()
    assert payload["analysis_runs"][0]["manifest_matches_current"] is True
    assert payload["publications"][0]["metadata_provenance_count"] == 1
    assert payload["climate"]["verified_count"] == 8
    assert "storage_key" not in str(payload)
    assert "file_contents" not in str(payload)
