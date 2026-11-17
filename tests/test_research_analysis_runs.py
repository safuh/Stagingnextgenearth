"""Contract tests for the read-only research analysis history API."""

from datetime import UTC, datetime

from stagingnextgenearth.api.research_analysis_runs import (
    ResearchAnalysisRunRead,
    router,
)


def test_analysis_history_route_is_registered_with_bounded_limit() -> None:
    route = next(
        item for item in router.routes
        if getattr(item, "path", "").endswith("/{dataset_id}/analysis-runs")
    )
    assert route.methods == {"GET"}
    assert route.response_model == list[ResearchAnalysisRunRead]
    limit = next(parameter for parameter in route.dependant.query_params if parameter.name == "limit")
    assert limit.field_info.ge == 1
    assert limit.field_info.le == 500


def test_analysis_run_read_contract_exposes_provenance_without_file_contents() -> None:
    record = ResearchAnalysisRunRead.model_validate(
        {
            "id": "run-1",
            "organization_id": "org-1",
            "dataset_id": "dataset-1",
            "study_id": None,
            "input_manifest_sha256": "a" * 64,
            "input_file_versions": [
                {"file_id": "file-1", "version": 2, "filename": "observations.csv",
                 "sha256": "b" * 64}
            ],
            "analysis_configuration": {"method": "monthly-summary"},
            "software_name": "NextGen Research",
            "software_version": "1.0.0",
            "code_revision": "abc123",
            "parameters": {"minimum_completeness": 0.9},
            "random_seed": None,
            "output_artifacts": [],
            "created_by": "user-1",
            "created_at": datetime(2026, 11, 17, tzinfo=UTC),
        }
    )
    payload = record.model_dump()
    assert payload["input_manifest_sha256"] == "a" * 64
    assert payload["input_file_versions"][0]["version"] == 2
    assert "storage_key" not in payload
    assert "file_contents" not in payload
