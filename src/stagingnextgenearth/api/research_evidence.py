"""Study-level evidence ledger joining approved datasets, analysis runs and outputs."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    ClimateObservation,
    Membership,
    ResearchAnalysisRun,
    ResearchDataset,
    ResearchDatasetFile,
    ResearchPublication,
    ResearchPublicationMetadataSource,
    ResearchStudy,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    require_membership,
)
from .research_collaborators import study_access_role
from .research_dataset_manifests import DatasetManifestFile, _manifest_digest

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies",
    tags=["research-evidence"],
)


class EvidenceDataset(BaseModel):
    dataset_id: str
    title: str
    version: str
    access_classification: str
    manifest_sha256: str
    file_count: int


class EvidenceAnalysisRun(BaseModel):
    run_id: str
    dataset_id: str
    input_manifest_sha256: str
    manifest_matches_current: bool
    software_name: str
    software_version: str
    code_revision: str | None
    output_artifact_count: int
    created_at: datetime


class EvidencePublication(BaseModel):
    publication_id: str
    title: str
    publication_type: str
    doi: str | None
    openalex_id: str | None
    metadata_provenance_count: int


class EvidenceClimateSummary(BaseModel):
    observation_count: int
    verified_count: int
    pending_count: int
    rejected_count: int
    first_observed_at: datetime | None
    last_observed_at: datetime | None


class ResearchEvidenceLedgerRead(BaseModel):
    study_id: str
    study_title: str
    generated_at: datetime
    datasets: list[EvidenceDataset]
    analysis_runs: list[EvidenceAnalysisRun]
    publications: list[EvidencePublication]
    climate: EvidenceClimateSummary
    interpretation: str = "traceability_inventory_not_independent_scientific_validation"


@router.get("/{study_id}/evidence-ledger", response_model=ResearchEvidenceLedgerRead)
async def get_research_evidence_ledger(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=100, ge=1, le=500),
) -> ResearchEvidenceLedgerRead:
    """Assemble bounded study evidence references without exposing file contents."""
    study = await session.scalar(
        select(ResearchStudy).where(
            ResearchStudy.id == study_id,
            ResearchStudy.organization_id == organization_id,
        )
    )
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")
    await study_access_role(session, organization_id, study_id, principal, membership)

    datasets_result = await session.scalars(
        select(ResearchDataset)
        .where(
            ResearchDataset.organization_id == organization_id,
            ResearchDataset.study_id == study_id,
            ResearchDataset.status == "approved",
        )
        .order_by(ResearchDataset.title.asc(), ResearchDataset.id.asc())
        .limit(limit)
    )
    datasets = list(datasets_result.all())
    dataset_ids = [item.id for item in datasets]
    dataset_evidence: list[EvidenceDataset] = []
    current_digests: dict[str, str] = {}

    for dataset in datasets:
        file_rows = await session.scalars(
            select(ResearchDatasetFile)
            .where(
                ResearchDatasetFile.dataset_id == dataset.id,
                ResearchDatasetFile.status == "available",
                ResearchDatasetFile.scan_status == "clean",
                ResearchDatasetFile.sha256_hex.is_not(None),
            )
            .order_by(ResearchDatasetFile.version.asc(), ResearchDatasetFile.id.asc())
            .limit(1000)
        )
        manifest_files = [
            DatasetManifestFile(
                file_id=item.id,
                version=item.version,
                filename=item.original_filename,
                media_type=item.media_type,
                size_bytes=item.size_bytes,
                sha256=item.sha256_hex,
            )
            for item in file_rows.all()
            if item.sha256_hex is not None
        ]
        digest = _manifest_digest(dataset.id, dataset.version, manifest_files)
        current_digests[dataset.id] = digest
        dataset_evidence.append(
            EvidenceDataset(
                dataset_id=dataset.id,
                title=dataset.title,
                version=dataset.version,
                access_classification=dataset.access_classification,
                manifest_sha256=digest,
                file_count=len(manifest_files),
            )
        )

    run_statement = select(ResearchAnalysisRun).where(
        ResearchAnalysisRun.organization_id == organization_id,
        ResearchAnalysisRun.study_id == study_id,
    )
    if dataset_ids:
        run_statement = run_statement.where(
            ResearchAnalysisRun.dataset_id.in_(dataset_ids)
        )
    else:
        run_statement = run_statement.where(ResearchAnalysisRun.dataset_id == "")
    runs_result = await session.scalars(
        run_statement.order_by(
            ResearchAnalysisRun.created_at.desc(), ResearchAnalysisRun.id.desc()
        ).limit(limit)
    )
    analysis_runs = [
        EvidenceAnalysisRun(
            run_id=run.id,
            dataset_id=run.dataset_id,
            input_manifest_sha256=run.input_manifest_sha256,
            manifest_matches_current=(
                current_digests.get(run.dataset_id) == run.input_manifest_sha256
            ),
            software_name=run.software_name,
            software_version=run.software_version,
            code_revision=run.code_revision,
            output_artifact_count=len(run.output_artifacts),
            created_at=run.created_at,
        )
        for run in runs_result.all()
    ]

    publications_result = await session.scalars(
        select(ResearchPublication)
        .where(ResearchPublication.study_id == study_id)
        .order_by(
            ResearchPublication.published_on.desc(),
            ResearchPublication.created_at.desc(),
        )
        .limit(limit)
    )
    publications = list(publications_result.all())
    publication_ids = [item.id for item in publications]
    metadata_counts: dict[str, int] = {}
    if publication_ids:
        count_rows = await session.execute(
            select(
                ResearchPublicationMetadataSource.publication_id,
                func.count(ResearchPublicationMetadataSource.id),
            )
            .where(
                ResearchPublicationMetadataSource.publication_id.in_(publication_ids)
            )
            .group_by(ResearchPublicationMetadataSource.publication_id)
        )
        metadata_counts = {
            publication_id: count
            for publication_id, count in count_rows.all()
        }
    publication_evidence = [
        EvidencePublication(
            publication_id=item.id,
            title=item.title,
            publication_type=item.publication_type,
            doi=item.doi,
            openalex_id=item.openalex_id,
            metadata_provenance_count=metadata_counts.get(item.id, 0),
        )
        for item in publications
    ]

    climate_statement = select(
        func.count(ClimateObservation.id),
        func.sum(
            func.case((ClimateObservation.quality_status == "verified", 1), else_=0)
        ),
        func.sum(
            func.case((ClimateObservation.quality_status == "pending", 1), else_=0)
        ),
        func.sum(
            func.case((ClimateObservation.quality_status == "rejected", 1), else_=0)
        ),
        func.min(ClimateObservation.observed_at),
        func.max(ClimateObservation.observed_at),
    ).where(
        ClimateObservation.organization_id == organization_id,
        ClimateObservation.study_id == study_id,
    )
    climate_row = (await session.execute(climate_statement)).one()
    return ResearchEvidenceLedgerRead(
        study_id=study.id,
        study_title=study.title,
        generated_at=datetime.now().astimezone(),
        datasets=dataset_evidence,
        analysis_runs=analysis_runs,
        publications=publication_evidence,
        climate=EvidenceClimateSummary(
            observation_count=int(climate_row[0] or 0),
            verified_count=int(climate_row[1] or 0),
            pending_count=int(climate_row[2] or 0),
            rejected_count=int(climate_row[3] or 0),
            first_observed_at=climate_row[4],
            last_observed_at=climate_row[5],
        ),
    )
