"""Tenant-scoped learning management workflows."""

import csv
import hashlib
import io
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.certificates.pdf import render_certificate
from stagingnextgenearth.identity.models import ResearcherProfile, User
from stagingnextgenearth.platform.models import (
    LearningAssessment,
    LearningAssessmentAttempt,
    LearningAssessmentEvaluation,
    LearningAttendance,
    LearningCertificate,
    LearningCohort,
    LearningCourse,
    LearningEnrollment,
    LearningIntervention,
    LearningLesson,
    LearningLessonCompletion,
    LearningMentorship,
    LearningModule,
    LearningResource,
    Membership,
    MembershipRole,
    Organization,
    OrganizationAuditEvent,
    Programme,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_membership_roles,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(prefix="/organizations/{organization_id}/learning", tags=["learning"])
public_router = APIRouter(tags=["public-learning"])
_MANAGE = {"admin", "founder", "executive", "programme_manager"}
_LEARN = {
    "admin",
    "founder",
    "executive",
    "programme_manager",
    "researcher",
    "youth_volunteer",
    "employee",
    "institutional_partner",
    "learner",
}


class PublicOrganizationRead(BaseModel):
    """Minimal public organisation identity used by public learning journeys."""

    id: str
    name: str
    slug: str


@public_router.get(
    "/public/organizations/{organization_slug}",
    response_model=PublicOrganizationRead,
)
async def get_public_organization(
    organization_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PublicOrganizationRead:
    organization = await session.scalar(
        select(Organization).where(Organization.slug == organization_slug)
    )
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    return PublicOrganizationRead(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
    )


class PublicCourseRead(BaseModel):
    """Publicly discoverable course fields; excludes learner and internal records."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    programme_id: str | None
    title: str
    slug: str
    description: str
    category: str | None
    delivery_mode: str
    status: str


@public_router.get(
    "/public/organizations/{organization_slug}/programmes/{programme_slug}/courses",
    response_model=list[PublicCourseRead],
)
async def list_public_programme_courses(
    organization_slug: str,
    programme_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicCourseRead]:
    """List published courses belonging to one publicly visible programme."""
    programme = await session.scalar(
        select(Programme)
        .join(Organization, Organization.id == Programme.organization_id)
        .where(
            Organization.slug == organization_slug,
            Programme.slug == programme_slug,
            Programme.status.in_({"planned", "active"}),
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    rows = await session.scalars(
        select(LearningCourse)
        .where(
            LearningCourse.organization_id == programme.organization_id,
            LearningCourse.programme_id == programme.id,
            LearningCourse.status == "published",
        )
        .order_by(LearningCourse.title)
        .limit(250)
    )
    return [PublicCourseRead.model_validate(item) for item in rows.all()]


@public_router.get(
    "/public/organizations/{organization_slug}/courses",
    response_model=list[PublicCourseRead],
)
async def list_public_courses(
    organization_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicCourseRead]:
    """List published courses for public discovery without exposing draft courses."""
    organization = await session.scalar(
        select(Organization).where(Organization.slug == organization_slug)
    )
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    rows = await session.scalars(
        select(LearningCourse)
        .where(
            LearningCourse.organization_id == organization.id,
            LearningCourse.status == "published",
        )
        .order_by(LearningCourse.title)
        .limit(250)
    )
    return [PublicCourseRead.model_validate(item) for item in rows.all()]


@public_router.get(
    "/public/organizations/{organization_slug}/courses/{course_slug}/curriculum",
)
async def get_public_course_curriculum(
    organization_slug: str,
    course_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Expose the complete outline and lesson content for published courses only."""
    course = await session.scalar(
        select(LearningCourse)
        .join(Organization, Organization.id == LearningCourse.organization_id)
        .where(
            Organization.slug == organization_slug,
            LearningCourse.slug == course_slug,
            LearningCourse.status == "published",
        )
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Published course not found")
    modules = await session.scalars(
        select(LearningModule)
        .where(LearningModule.course_id == course.id)
        .order_by(LearningModule.position)
    )
    module_rows = modules.all()
    outline: list[dict[str, object]] = []
    for module in module_rows:
        lessons = await session.scalars(
            select(LearningLesson)
            .where(LearningLesson.module_id == module.id)
            .order_by(LearningLesson.position)
        )
        outline.append(
            {
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "position": module.position,
                "lessons": [
                    {
                        "id": lesson.id,
                        "title": lesson.title,
                        "content_type": lesson.content_type,
                        "content": lesson.content,
                        "resource_url": lesson.resource_url,
                        "duration_minutes": lesson.duration_minutes,
                        "position": lesson.position,
                    }
                    for lesson in lessons.all()
                ],
            }
        )
    return {
        "course_id": course.id,
        "slug": course.slug,
        "title": course.title,
        "description": course.description,
        "modules": outline,
    }


class CourseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    slug: str = Field(min_length=2, max_length=140, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1, max_length=12000)
    category: str | None = Field(default=None, max_length=100)
    programme_id: str | None = None
    delivery_mode: Literal["online", "in_person", "blended"] = "blended"


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    programme_id: str | None
    title: str
    slug: str
    description: str
    category: str | None
    delivery_mode: str
    status: str


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=140,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = Field(default=None, min_length=1, max_length=12000)
    category: str | None = Field(default=None, max_length=100)
    programme_id: str | None = None
    delivery_mode: Literal["online", "in_person", "blended"] | None = None


class ModuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    position: int | None = Field(default=None, ge=1, le=500)


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    content_type: Literal["text", "video", "document", "link", "workshop"] | None = None
    content: str | None = Field(default=None, max_length=30000)
    resource_url: str | None = Field(default=None, max_length=2000)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    position: int | None = Field(default=None, ge=1, le=500)


class CohortCreate(BaseModel):
    programme_id: str
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    title: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    start_date: date | None = None
    end_date: date | None = None
    capacity: int | None = Field(default=None, ge=1)
    inactivity_threshold_days: int = Field(default=14, ge=1, le=90)
    absence_threshold: int = Field(default=2, ge=1, le=20)
    absence_window_days: int = Field(default=30, ge=7, le=90)
    overdue_grace_days: int = Field(default=2, ge=0, le=30)

    @model_validator(mode="after")
    def validate_dates(self) -> "CohortCreate":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Cohort start date must not be after its end date")
        return self


class CohortUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    start_date: date | None = None
    end_date: date | None = None
    capacity: int | None = Field(default=None, ge=1)
    inactivity_threshold_days: int | None = Field(default=None, ge=1, le=90)
    absence_threshold: int | None = Field(default=None, ge=1, le=20)
    absence_window_days: int | None = Field(default=None, ge=7, le=90)
    overdue_grace_days: int | None = Field(default=None, ge=0, le=30)
    status: Literal["open", "active", "completed", "archived"] | None = None


class InterventionCreate(BaseModel):
    enrollment_id: str
    assigned_to: str
    due_date: date | None = None
    note: str = Field(
        min_length=3,
        max_length=3000,
        description="Operational follow-up only; no health, disability or safeguarding details.",
    )


class InterventionUpdate(BaseModel):
    assigned_to: str | None = None
    due_date: date | None = None
    note: str | None = Field(
        default=None,
        min_length=3,
        max_length=3000,
        description="Operational follow-up only; no health, disability or safeguarding details.",
    )
    status: Literal["in_progress", "resolved", "cancelled"] | None = None
    resolution_note: str | None = Field(default=None, max_length=3000)


class CohortAssignment(BaseModel):
    cohort_id: str | None = None


class ModuleCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    position: int = Field(ge=1, le=500)


class LessonCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    content_type: Literal["text", "video", "document", "link", "workshop"]
    content: str | None = Field(default=None, max_length=30000)
    resource_url: str | None = Field(default=None, max_length=2000)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    position: int = Field(ge=1, le=500)


class EnrollmentDecision(BaseModel):
    decision: Literal["approved", "rejected"]


class EnrollmentBulkDecision(BaseModel):
    learner_ids: list[str] = Field(min_length=1, max_length=100)
    decision: Literal["approved", "rejected"]

    @model_validator(mode="after")
    def validate_learner_ids(self) -> "EnrollmentBulkDecision":
        if len(self.learner_ids) != len(set(self.learner_ids)):
            raise ValueError("Learner IDs must be unique within a bulk decision")
        return self


class AssessmentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    assessment_type: Literal["quiz", "assignment", "evaluation"]
    instructions: str = Field(min_length=1, max_length=10000)
    configuration: dict[str, object] = Field(default_factory=dict)
    pass_mark: int = Field(default=50, ge=0, le=100)
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_quiz_configuration(self) -> "AssessmentCreate":
        if self.assessment_type == "quiz" and "questions" in self.configuration:
            QuizConfiguration.model_validate(self.configuration)
        return self


class QuizOption(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=500)


class QuizQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    prompt: str = Field(min_length=1, max_length=2000)
    options: list[QuizOption] = Field(min_length=2, max_length=10)
    correct_option_id: str = Field(min_length=1, max_length=40)
    points: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def validate_options(self) -> "QuizQuestion":
        option_ids = [option.id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Quiz option IDs must be unique within a question")
        if self.correct_option_id not in option_ids:
            raise ValueError("The correct option must exist in the question options")
        return self


class QuizConfiguration(BaseModel):
    questions: list[QuizQuestion] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_question_ids(self) -> "QuizConfiguration":
        question_ids = [question.id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Quiz question IDs must be unique")
        return self


class QuizSubmission(BaseModel):
    answers: dict[str, str] = Field(min_length=1, max_length=50)


class SubmissionCreate(BaseModel):
    submission: dict[str, object] = Field(min_length=1)


class Evaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    feedback: str | None = Field(default=None, max_length=5000)


class MentorAssign(BaseModel):
    mentor_id: str
    mentee_id: str
    notes: str | None = Field(default=None, max_length=5000)


class MentorshipStatusUpdate(BaseModel):
    status: Literal["completed", "ended"]


class AttendanceCreate(BaseModel):
    session_key: str = Field(min_length=1, max_length=100)
    session_title: str = Field(min_length=2, max_length=240)
    session_date: date
    learner_id: str
    attendance_status: Literal["present", "late", "excused", "absent"]


class AttendanceBulkLearner(BaseModel):
    learner_id: str
    attendance_status: Literal["present", "late", "excused", "absent"]


class AttendanceBulkCreate(BaseModel):
    session_key: str = Field(min_length=1, max_length=100)
    session_title: str = Field(min_length=2, max_length=240)
    session_date: date
    learners: list[AttendanceBulkLearner] = Field(min_length=1, max_length=100)


class ResourceCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    resource_type: Literal["document", "video", "research", "link"]
    description: str | None = Field(default=None, max_length=5000)
    resource_url: str | None = Field(default=None, max_length=2000)
    storage_reference: str | None = Field(default=None, max_length=160)
    lesson_id: str | None = None


async def _course(session: AsyncSession, org_id: str, course_id: str) -> LearningCourse:
    item = await session.scalar(
        select(LearningCourse).where(
            LearningCourse.id == course_id, LearningCourse.organization_id == org_id
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return item


async def _enrollment(session: AsyncSession, course_id: str, learner_id: str) -> LearningEnrollment:
    item = await session.scalar(
        select(LearningEnrollment).where(
            LearningEnrollment.course_id == course_id, LearningEnrollment.learner_id == learner_id
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Enrollment not found")
    return item


async def _approved_enrollment(
    session: AsyncSession, course_id: str, learner_id: str
) -> LearningEnrollment:
    """Require an approved learner enrollment without disclosing whether one exists."""
    enrollment = await session.scalar(
        select(LearningEnrollment).where(
            LearningEnrollment.course_id == course_id,
            LearningEnrollment.learner_id == learner_id,
        )
    )
    if enrollment is None or enrollment.status not in {"approved", "completed"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "An approved enrollment is required",
        )
    return enrollment


@router.post("/courses", response_model=CourseRead, status_code=201)
async def create_course(
    organization_id: str,
    body: CourseCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CourseRead:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course management permission required")
    if body.programme_id is not None:
        programme_exists = await session.scalar(
            select(Programme.id).where(
                Programme.id == body.programme_id,
                Programme.organization_id == organization_id,
            )
        )
        if programme_exists is None:
            raise HTTPException(404, "Programme not found in this organisation")
    course = LearningCourse(
        organization_id=organization_id,
        programme_id=body.programme_id,
        title=body.title.strip(),
        slug=body.slug,
        description=body.description,
        category=body.category,
        delivery_mode=body.delivery_mode,
        status="draft",
        created_by=principal.user_id,
    )
    session.add(course)
    try:
        await session.commit()
        await session.refresh(course)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Course slug already exists") from exc
    return CourseRead.model_validate(course)


@router.get("/courses", response_model=list[CourseRead])
async def list_courses(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    include_drafts: bool = False,
) -> list[CourseRead]:
    statement = select(LearningCourse).where(LearningCourse.organization_id == organization_id)
    if not include_drafts or not await membership_has_any_role(session, membership, _MANAGE):
        statement = statement.where(LearningCourse.status == "published")
    result = await session.scalars(statement.order_by(LearningCourse.title).limit(200))
    return [CourseRead.model_validate(row) for row in result.all()]


@router.get("/cohorts")
async def list_learning_cohorts(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    programme_id: str | None = None,
) -> list[dict[str, object]]:
    """List cohorts in the current organisation with assigned-enrolment counts."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Cohort management permission required")
    statement = select(LearningCohort).where(LearningCohort.organization_id == organization_id)
    if programme_id:
        statement = statement.where(LearningCohort.programme_id == programme_id)
    rows = await session.scalars(
        statement.order_by(LearningCohort.start_date.desc(), LearningCohort.title).limit(250)
    )
    cohorts = rows.all()
    counts: dict[str, int] = {}
    if cohorts:
        count_rows = await session.execute(
            select(
                LearningEnrollment.cohort_id,
                func.count(func.distinct(LearningEnrollment.learner_id)),
            )
            .where(
                LearningEnrollment.cohort_id.in_([item.id for item in cohorts]),
                LearningEnrollment.status.in_({"applied", "approved", "completed"}),
            )
            .group_by(LearningEnrollment.cohort_id)
        )
        counts = {str(cohort_id): int(count) for cohort_id, count in count_rows.all()}
    return [
        {
            "id": item.id,
            "programme_id": item.programme_id,
            "code": item.code,
            "title": item.title,
            "description": item.description,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "capacity": item.capacity,
            "inactivity_threshold_days": item.inactivity_threshold_days,
            "absence_threshold": item.absence_threshold,
            "absence_window_days": item.absence_window_days,
            "overdue_grace_days": item.overdue_grace_days,
            "status": item.status,
            "assigned_count": counts.get(item.id, 0),
        }
        for item in cohorts
    ]


@router.post("/cohorts", status_code=201)
async def create_learning_cohort(
    organization_id: str,
    body: CohortCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Cohort management permission required")
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == body.programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(404, "Programme not found in this organisation")
    if not body.title.strip():
        raise HTTPException(422, "Cohort title cannot be blank")
    cohort = LearningCohort(
        organization_id=organization_id,
        programme_id=programme.id,
        code=body.code.strip(),
        title=body.title.strip(),
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        capacity=body.capacity,
        inactivity_threshold_days=body.inactivity_threshold_days,
        absence_threshold=body.absence_threshold,
        absence_window_days=body.absence_window_days,
        overdue_grace_days=body.overdue_grace_days,
        status="draft",
        created_by=principal.user_id,
    )
    session.add(cohort)
    try:
        await session.flush()
        session.add(
            OrganizationAuditEvent(
                organization_id=organization_id,
                actor_user_id=principal.user_id,
                action="learning.cohort.created",
                changes={
                    "cohort_id": cohort.id,
                    "programme_id": programme.id,
                    "code": cohort.code,
                    "status": cohort.status,
                },
            )
        )
        await session.commit()
        await session.refresh(cohort)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Cohort code already exists in this organisation") from exc
    return {
        "id": cohort.id,
        "programme_id": cohort.programme_id,
        "code": cohort.code,
        "title": cohort.title,
        "description": cohort.description,
        "start_date": cohort.start_date,
        "end_date": cohort.end_date,
        "capacity": cohort.capacity,
        "inactivity_threshold_days": cohort.inactivity_threshold_days,
        "absence_threshold": cohort.absence_threshold,
        "absence_window_days": cohort.absence_window_days,
        "overdue_grace_days": cohort.overdue_grace_days,
        "status": cohort.status,
        "assigned_count": 0,
    }


@router.patch("/cohorts/{cohort_id}")
async def update_learning_cohort(
    organization_id: str,
    cohort_id: str,
    body: CohortUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Cohort management permission required")
    cohort = await session.scalar(
        select(LearningCohort)
        .where(
            LearningCohort.id == cohort_id,
            LearningCohort.organization_id == organization_id,
        )
        .with_for_update()
    )
    if cohort is None:
        raise HTTPException(404, "Cohort not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "At least one cohort field must be supplied")
    if "title" in changes and (changes["title"] is None or not changes["title"].strip()):
        raise HTTPException(422, "Cohort title cannot be blank")
    if "status" in changes and changes["status"] is None:
        raise HTTPException(422, "Cohort status cannot be null")
    threshold_fields = {
        "inactivity_threshold_days",
        "absence_threshold",
        "absence_window_days",
        "overdue_grace_days",
    }
    null_threshold_fields = sorted(
        field for field in threshold_fields if field in changes and changes[field] is None
    )
    if null_threshold_fields:
        raise HTTPException(
            422,
            f"Risk threshold fields cannot be null: {', '.join(null_threshold_fields)}",
        )
    previous_thresholds = {
        field: getattr(cohort, field) for field in threshold_fields if field in changes
    }
    start_date = changes.get("start_date", cohort.start_date)
    end_date = changes.get("end_date", cohort.end_date)
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "Cohort start date must not be after its end date")
    previous_status = cohort.status
    next_status = changes.get("status", previous_status)
    if next_status == "active" and previous_status != "active":
        raise HTTPException(
            409,
            "Cohort activation is gated until safeguarding and consent readiness is verified",
        )
    allowed = {
        "draft": {"open", "archived"},
        "open": {"completed", "archived"},
        "active": {"completed", "archived"},
        "completed": {"archived"},
        "archived": set(),
    }
    if next_status != cohort.status and next_status not in allowed[cohort.status]:
        raise HTTPException(409, "Invalid cohort lifecycle transition")
    if "capacity" in changes and changes["capacity"] is not None:
        assigned_count = await session.scalar(
            select(func.count(func.distinct(LearningEnrollment.learner_id))).where(
                LearningEnrollment.cohort_id == cohort.id,
                LearningEnrollment.status.in_({"applied", "approved", "completed"}),
            )
        )
        if int(assigned_count or 0) > changes["capacity"]:
            raise HTTPException(409, "Capacity cannot be lower than assigned learners")
    for field, value in changes.items():
        if field == "title" and value is not None:
            value = value.strip()
        setattr(cohort, field, value)
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            action="learning.cohort.updated",
            changes={
                "cohort_id": cohort.id,
                "fields": sorted(changes),
                "status": {"before": previous_status, "after": next_status},
                "risk_thresholds": {
                    field: {"before": previous_thresholds[field], "after": changes[field]}
                    for field in sorted(previous_thresholds)
                },
            },
        )
    )
    await session.commit()
    await session.refresh(cohort)
    assigned_count = await session.scalar(
        select(func.count(func.distinct(LearningEnrollment.learner_id))).where(
            LearningEnrollment.cohort_id == cohort.id,
            LearningEnrollment.status.in_({"applied", "approved", "completed"}),
        )
    )
    return {
        "id": cohort.id,
        "programme_id": cohort.programme_id,
        "code": cohort.code,
        "title": cohort.title,
        "description": cohort.description,
        "start_date": cohort.start_date,
        "end_date": cohort.end_date,
        "capacity": cohort.capacity,
        "inactivity_threshold_days": cohort.inactivity_threshold_days,
        "absence_threshold": cohort.absence_threshold,
        "absence_window_days": cohort.absence_window_days,
        "overdue_grace_days": cohort.overdue_grace_days,
        "status": cohort.status,
        "assigned_count": int(assigned_count or 0),
    }


@router.post("/courses/{course_id}/enrollments/{learner_id}/cohort")
async def assign_enrollment_cohort(
    organization_id: str,
    course_id: str,
    learner_id: str,
    body: CohortAssignment,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Cohort assignment permission required")
    course = await _course(session, organization_id, course_id)
    enrollment = await _enrollment(session, course_id, learner_id)
    previous_cohort_id = enrollment.cohort_id
    if body.cohort_id == previous_cohort_id:
        return {
            "enrollment_id": enrollment.id,
            "learner_id": enrollment.learner_id,
            "course_id": enrollment.course_id,
            "cohort_id": enrollment.cohort_id,
        }
    if enrollment.status not in {"applied", "approved"}:
        raise HTTPException(409, "Only pending or approved enrolments can change cohort")
    if body.cohort_id is None:
        enrollment.cohort_id = None
        session.add(
            OrganizationAuditEvent(
                organization_id=organization_id,
                actor_user_id=principal.user_id,
                subject_user_id=learner_id,
                action="learning.enrollment.cohort_unassigned",
                changes={
                    "course_id": course_id,
                    "from_cohort_id": previous_cohort_id,
                },
            )
        )
    else:
        if course.programme_id is None:
            raise HTTPException(409, "Standalone courses cannot be assigned to programme cohorts")
        cohort = await session.scalar(
            select(LearningCohort)
            .where(
                LearningCohort.id == body.cohort_id,
                LearningCohort.organization_id == organization_id,
                LearningCohort.programme_id == course.programme_id,
            )
            .with_for_update()
        )
        if cohort is None:
            raise HTTPException(404, "Cohort not found for this course programme")
        if cohort.status not in {"open", "active"}:
            raise HTTPException(409, "Cohort is not accepting learner assignments")
        if enrollment.cohort_id != cohort.id and cohort.capacity is not None:
            existing_learner_assignment = await session.scalar(
                select(LearningEnrollment.id)
                .where(
                    LearningEnrollment.cohort_id == cohort.id,
                    LearningEnrollment.learner_id == learner_id,
                    LearningEnrollment.status.in_({"applied", "approved", "completed"}),
                )
                .limit(1)
            )
            if existing_learner_assignment is None:
                assigned_count = await session.scalar(
                    select(func.count(func.distinct(LearningEnrollment.learner_id))).where(
                        LearningEnrollment.cohort_id == cohort.id,
                        LearningEnrollment.status.in_({"applied", "approved", "completed"}),
                    )
                )
                if int(assigned_count or 0) >= cohort.capacity:
                    raise HTTPException(409, "Cohort capacity has been reached")
        enrollment.cohort_id = cohort.id
        session.add(
            OrganizationAuditEvent(
                organization_id=organization_id,
                actor_user_id=principal.user_id,
                subject_user_id=learner_id,
                action="learning.enrollment.cohort_assigned",
                changes={
                    "course_id": course_id,
                    "from_cohort_id": previous_cohort_id,
                    "to_cohort_id": cohort.id,
                },
            )
        )
    await session.commit()
    return {
        "enrollment_id": enrollment.id,
        "learner_id": enrollment.learner_id,
        "course_id": enrollment.course_id,
        "cohort_id": enrollment.cohort_id,
    }


@router.patch("/courses/{course_id}", response_model=CourseRead)
async def update_course(
    organization_id: str,
    course_id: str,
    body: CourseUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CourseRead:
    """Edit course metadata while the curriculum remains a draft."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course management permission required")
    course = await _course(session, organization_id, course_id)
    if course.status != "draft":
        raise HTTPException(409, "Only draft courses can be edited")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "At least one course field must be supplied")
    required_fields = ("title", "slug", "description", "delivery_mode")
    if any(changes.get(field) is None for field in required_fields if field in changes):
        raise HTTPException(422, "Required course fields cannot be null")
    if "programme_id" in changes and changes["programme_id"] is not None:
        programme_exists = await session.scalar(
            select(Programme.id).where(
                Programme.id == changes["programme_id"],
                Programme.organization_id == organization_id,
            )
        )
        if programme_exists is None:
            raise HTTPException(404, "Programme not found in this organisation")
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()
    for field, value in changes.items():
        setattr(course, field, value)
    try:
        await session.commit()
        await session.refresh(course)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Course slug already exists") from exc
    return CourseRead.model_validate(course)


@router.patch("/courses/{course_id}/modules/{module_id}")
async def update_module(
    organization_id: str,
    course_id: str,
    module_id: str,
    body: ModuleUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course management permission required")
    course = await _course(session, organization_id, course_id)
    if course.status != "draft":
        raise HTTPException(409, "Modules can only be edited while the course is a draft")
    module = await session.scalar(
        select(LearningModule).where(
            LearningModule.id == module_id,
            LearningModule.course_id == course_id,
        )
    )
    if module is None:
        raise HTTPException(404, "Module not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "At least one module field must be supplied")
    if any(changes.get(field) is None for field in ("title", "position") if field in changes):
        raise HTTPException(422, "Module title and position cannot be null")
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()
    for field, value in changes.items():
        setattr(module, field, value)
    try:
        await session.commit()
        await session.refresh(module)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Module position already exists") from exc
    return {
        "id": module.id,
        "course_id": module.course_id,
        "title": module.title,
        "description": module.description,
        "position": module.position,
    }


@router.patch("/courses/{course_id}/lessons/{lesson_id}")
async def update_lesson(
    organization_id: str,
    course_id: str,
    lesson_id: str,
    body: LessonUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course management permission required")
    course = await _course(session, organization_id, course_id)
    if course.status != "draft":
        raise HTTPException(409, "Lessons can only be edited while the course is a draft")
    lesson = await session.scalar(
        select(LearningLesson)
        .join(LearningModule)
        .where(
            LearningLesson.id == lesson_id,
            LearningModule.course_id == course_id,
        )
    )
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "At least one lesson field must be supplied")
    required_fields = ("title", "content_type", "position")
    if any(changes.get(field) is None for field in required_fields if field in changes):
        raise HTTPException(422, "Lesson title, content type and position cannot be null")
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()
    for field, value in changes.items():
        setattr(lesson, field, value)
    try:
        await session.commit()
        await session.refresh(lesson)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Lesson position already exists") from exc
    return {
        "id": lesson.id,
        "module_id": lesson.module_id,
        "title": lesson.title,
        "content_type": lesson.content_type,
        "content": lesson.content,
        "resource_url": lesson.resource_url,
        "duration_minutes": lesson.duration_minutes,
        "position": lesson.position,
    }


@router.post("/courses/{course_id}/publish", response_model=CourseRead)
async def publish_course(
    organization_id: str,
    course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CourseRead:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course management permission required")
    course = await _course(session, organization_id, course_id)
    if course.status == "archived":
        raise HTTPException(409, "Archived courses cannot be published")
    lesson_count = await session.scalar(
        select(LearningLesson.id)
        .join(LearningModule)
        .where(LearningModule.course_id == course_id)
        .limit(1)
    )
    if lesson_count is None:
        raise HTTPException(409, "A course needs at least one lesson before publishing")
    course.status = "published"
    await session.commit()
    await session.refresh(course)
    return CourseRead.model_validate(course)


@router.post("/courses/{course_id}/modules", status_code=201)
async def create_module(
    organization_id: str,
    course_id: str,
    body: ModuleCreate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course management permission required")
    await _course(session, organization_id, course_id)
    module = LearningModule(course_id=course_id, **body.model_dump())
    session.add(module)
    try:
        await session.commit()
        await session.refresh(module)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Module position already exists") from exc
    return {
        "id": module.id,
        "course_id": module.course_id,
        "title": module.title,
        "position": module.position,
    }


@router.post("/modules/{module_id}/lessons", status_code=201)
async def create_lesson(
    organization_id: str,
    module_id: str,
    body: LessonCreate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course management permission required")
    module = await session.scalar(
        select(LearningModule)
        .join(LearningCourse)
        .where(LearningModule.id == module_id, LearningCourse.organization_id == organization_id)
    )
    if module is None:
        raise HTTPException(404, "Module not found")
    lesson = LearningLesson(module_id=module_id, **body.model_dump())
    session.add(lesson)
    try:
        await session.commit()
        await session.refresh(lesson)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Lesson position already exists") from exc
    return {
        "id": lesson.id,
        "module_id": lesson.module_id,
        "title": lesson.title,
        "content_type": lesson.content_type,
        "position": lesson.position,
    }


@router.post("/courses/{course_id}/enrollments", status_code=201)
async def apply_for_course(
    organization_id: str,
    course_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Let any authenticated public learner apply; membership is granted only after review."""
    course = await _course(session, organization_id, course_id)
    if course.status != "published":
        raise HTTPException(409, "Applications are open only for published courses")
    existing_membership = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == principal.user_id,
        )
    )
    if existing_membership is not None and (
        existing_membership.status != "active"
        or not await membership_has_any_role(session, existing_membership, _LEARN)
    ):
        raise HTTPException(403, "This account is not eligible for learner applications")
    enrollment = LearningEnrollment(
        course_id=course_id,
        learner_id=principal.user_id,
        status="applied",
        progress_percent=0,
    )
    session.add(enrollment)
    try:
        await session.commit()
        await session.refresh(enrollment)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "An application already exists for this course") from exc
    return {"id": enrollment.id, "status": enrollment.status, "applied_at": enrollment.applied_at}


@router.get("/my-enrollments")
async def my_enrollments(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """Return only the authenticated learner's application and course status."""
    rows = await session.execute(
        select(
            LearningEnrollment,
            LearningCourse.title,
            LearningCourse.slug,
            LearningCohort.title,
        )
        .join(LearningCourse, LearningCourse.id == LearningEnrollment.course_id)
        .outerjoin(LearningCohort, LearningCohort.id == LearningEnrollment.cohort_id)
        .where(
            LearningCourse.organization_id == organization_id,
            LearningEnrollment.learner_id == principal.user_id,
        )
        .order_by(LearningEnrollment.applied_at.desc())
        .limit(200)
    )
    return [
        {
            "id": enrollment.id,
            "course_id": enrollment.course_id,
            "course_title": title,
            "course_slug": slug,
            "cohort_id": enrollment.cohort_id,
            "cohort_title": cohort_title,
            "status": enrollment.status,
            "progress_percent": enrollment.progress_percent,
            "applied_at": enrollment.applied_at,
        }
        for enrollment, title, slug, cohort_title in rows.all()
    ]


@router.get("/courses/{course_id}/enrollments")
async def list_course_enrollments(
    organization_id: str,
    course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """List learner applications for authorised course administrators."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Enrollment reporting permission required")
    await _course(session, organization_id, course_id)
    rows = await session.execute(
        select(LearningEnrollment, LearningCohort.title)
        .outerjoin(LearningCohort, LearningCohort.id == LearningEnrollment.cohort_id)
        .where(LearningEnrollment.course_id == course_id)
        .order_by(LearningEnrollment.applied_at.desc())
        .limit(500)
    )
    return [
        {
            "id": row.id,
            "learner_id": row.learner_id,
            "learner_ref": (
                f"Learner-{hashlib.sha256(row.learner_id.encode()).hexdigest()[:8].upper()}"
            ),
            "cohort_id": row.cohort_id,
            "cohort_title": cohort_title,
            "status": row.status,
            "progress_percent": row.progress_percent,
            "applied_at": row.applied_at,
            "reviewed_at": row.reviewed_at,
        }
        for row, cohort_title in rows.all()
    ]


@router.post("/courses/{course_id}/enrollments/{learner_id}/decision")
async def decide_enrollment(
    organization_id: str,
    course_id: str,
    learner_id: str,
    body: EnrollmentDecision,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Enrollment approval permission required")
    await _course(session, organization_id, course_id)
    enrollment = await _enrollment(session, course_id, learner_id)
    if enrollment.status != "applied":
        raise HTTPException(409, "Only pending applications can be decided")
    if body.decision == "approved":
        existing_membership = await session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == learner_id,
            )
        )
        if existing_membership is None:
            learner_membership = Membership(
                organization_id=organization_id,
                user_id=learner_id,
                role="learner",
                status="active",
            )
            session.add(learner_membership)
            await session.flush()
            session.add(MembershipRole(membership_id=learner_membership.id, role="learner"))
            session.add(
                OrganizationAuditEvent(
                    organization_id=organization_id,
                    actor_user_id=principal.user_id,
                    subject_user_id=learner_id,
                    action="membership.roles_changed",
                    changes={
                        "roles": {"before": [], "after": ["learner"]},
                        "reason": "course_enrollment_approved",
                        "course_id": course_id,
                    },
                )
            )
        elif existing_membership.status != "active" or not await membership_has_any_role(
            session, existing_membership, _LEARN
        ):
            raise HTTPException(
                409,
                "Applicant has an incompatible or inactive organisation membership",
            )
        else:
            # Course approval is an explicit learner-role grant. Preserve any
            # existing staff/volunteer/partner role as the membership's primary
            # role and add learner as a separate, auditable assignment.
            current_roles = await get_membership_roles(session, existing_membership)
            if "learner" not in current_roles:
                session.add(
                    MembershipRole(
                        membership_id=existing_membership.id,
                        role="learner",
                    )
                )
                session.add(
                    OrganizationAuditEvent(
                        organization_id=organization_id,
                        actor_user_id=principal.user_id,
                        subject_user_id=learner_id,
                        action="membership.roles_changed",
                        changes={
                            "roles": {
                                "before": sorted(current_roles),
                                "after": sorted(current_roles | {"learner"}),
                            },
                            "reason": "course_enrollment_approved",
                            "course_id": course_id,
                        },
                    )
                )
    enrollment.status = body.decision
    enrollment.reviewed_by = principal.user_id
    enrollment.reviewed_at = datetime.now(UTC)
    await session.commit()
    return {"id": enrollment.id, "status": enrollment.status}


@router.post("/courses/{course_id}/enrollments/bulk-decision")
async def bulk_decide_enrollments(
    organization_id: str,
    course_id: str,
    body: EnrollmentBulkDecision,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Apply independent decisions and return an explicit result for every learner."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Enrollment approval permission required")
    await _course(session, organization_id, course_id)
    results: list[dict[str, object]] = []
    for learner_id in body.learner_ids:
        try:
            result = await decide_enrollment(
                organization_id,
                course_id,
                learner_id,
                EnrollmentDecision(decision=body.decision),
                principal,
                membership,
                session,
            )
            results.append({"learner_id": learner_id, "status": result["status"], "ok": True})
        except HTTPException as exc:
            results.append(
                {
                    "learner_id": learner_id,
                    "ok": False,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                }
            )
    return {
        "course_id": course_id,
        "decision": body.decision,
        "processed": len(results),
        "succeeded": sum(bool(item["ok"]) for item in results),
        "failed": sum(not bool(item["ok"]) for item in results),
        "results": results,
    }


@router.get("/courses/{course_id}/assessments")
async def list_course_assessments(
    organization_id: str,
    course_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """List assessment instructions without exposing private configuration payloads."""
    course = await _course(session, organization_id, course_id)
    if course.status != "published" and not await membership_has_any_role(
        session, membership, _MANAGE
    ):
        raise HTTPException(404, "Course not found")
    if not await membership_has_any_role(session, membership, _MANAGE):
        if not await membership_has_any_role(session, membership, _LEARN):
            raise HTTPException(403, "Learner access required")
        await _approved_enrollment(session, course_id, principal.user_id)
    rows = await session.scalars(
        select(LearningAssessment)
        .where(LearningAssessment.course_id == course_id)
        .order_by(LearningAssessment.title)
        .limit(200)
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "assessment_type": row.assessment_type,
            "instructions": row.instructions,
            "pass_mark": row.pass_mark,
            "due_at": row.due_at,
            "automated": row.assessment_type == "quiz" and "questions" in row.configuration,
        }
        for row in rows.all()
    ]


@router.post("/courses/{course_id}/assessments", status_code=201)
async def create_assessment(
    organization_id: str,
    course_id: str,
    body: AssessmentCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Assessment management permission required")
    await _course(session, organization_id, course_id)
    assessment = LearningAssessment(
        course_id=course_id, created_by=principal.user_id, **body.model_dump()
    )
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return {
        "id": assessment.id,
        "title": assessment.title,
        "assessment_type": assessment.assessment_type,
        "pass_mark": assessment.pass_mark,
    }


@router.get("/assessments/{assessment_id}/quiz")
async def get_quiz(
    organization_id: str,
    assessment_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Return quiz prompts and options without ever exposing answer keys."""
    if not await membership_has_any_role(session, membership, _LEARN):
        raise HTTPException(403, "Learner access required")
    assessment = await session.scalar(
        select(LearningAssessment)
        .join(LearningCourse)
        .where(
            LearningAssessment.id == assessment_id,
            LearningCourse.organization_id == organization_id,
            LearningCourse.status == "published",
        )
    )
    if assessment is None or assessment.assessment_type != "quiz":
        raise HTTPException(404, "Quiz not found")
    await _approved_enrollment(session, assessment.course_id, principal.user_id)
    if assessment.due_at is not None:
        due_at = assessment.due_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if datetime.now(UTC) > due_at:
            raise HTTPException(409, "The quiz deadline has passed")
    try:
        configuration = QuizConfiguration.model_validate(assessment.configuration)
    except ValidationError as exc:
        raise HTTPException(409, "This quiz is not configured for automated execution") from exc
    return {
        "id": assessment.id,
        "title": assessment.title,
        "instructions": assessment.instructions,
        "pass_mark": assessment.pass_mark,
        "questions": [
            {
                "id": question.id,
                "prompt": question.prompt,
                "points": question.points,
                "options": [option.model_dump() for option in question.options],
            }
            for question in configuration.questions
        ],
    }


@router.post("/assessments/{assessment_id}/quiz-attempts", status_code=201)
async def submit_quiz_attempt(
    organization_id: str,
    assessment_id: str,
    body: QuizSubmission,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Score a configured multiple-choice quiz on the server and persist the result."""
    if not await membership_has_any_role(session, membership, _LEARN):
        raise HTTPException(403, "Learner access required")
    assessment = await session.scalar(
        select(LearningAssessment)
        .join(LearningCourse)
        .where(
            LearningAssessment.id == assessment_id,
            LearningCourse.organization_id == organization_id,
            LearningCourse.status == "published",
        )
    )
    if assessment is None or assessment.assessment_type != "quiz":
        raise HTTPException(404, "Quiz not found")
    await _approved_enrollment(session, assessment.course_id, principal.user_id)
    if assessment.due_at is not None:
        due_at = assessment.due_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if datetime.now(UTC) > due_at:
            raise HTTPException(409, "The quiz deadline has passed")
    try:
        configuration = QuizConfiguration.model_validate(assessment.configuration)
    except ValidationError as exc:
        raise HTTPException(409, "This quiz is not configured for automated execution") from exc

    question_ids = {question.id for question in configuration.questions}
    if set(body.answers) != question_ids:
        raise HTTPException(422, "Submit exactly one answer for every quiz question")
    total_points = sum(question.points for question in configuration.questions)
    earned_points = 0
    for question in configuration.questions:
        selected_option = body.answers[question.id]
        valid_options = {option.id for option in question.options}
        if selected_option not in valid_options:
            raise HTTPException(422, f"Invalid option for question {question.id}")
        if selected_option == question.correct_option_id:
            earned_points += question.points
    score = round(earned_points * 100 / total_points)
    evaluated_at = datetime.now(UTC)
    attempt = LearningAssessmentAttempt(
        assessment_id=assessment.id,
        learner_id=principal.user_id,
        submission={"answers": body.answers},
        score=score,
        feedback="Automatically scored multiple-choice quiz",
        evaluated_at=evaluated_at,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return {
        "id": attempt.id,
        "score": score,
        "passed": score >= assessment.pass_mark,
        "pass_mark": assessment.pass_mark,
        "earned_points": earned_points,
        "total_points": total_points,
        "submitted_at": attempt.submitted_at,
    }


@router.post("/assessments/{assessment_id}/submissions", status_code=201)
async def submit_assessment(
    organization_id: str,
    assessment_id: str,
    body: SubmissionCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _LEARN):
        raise HTTPException(403, "Learner access required")
    assessment = await session.scalar(
        select(LearningAssessment)
        .join(LearningCourse)
        .where(
            LearningAssessment.id == assessment_id,
            LearningCourse.organization_id == organization_id,
            LearningCourse.status == "published",
        )
    )
    if assessment is None:
        raise HTTPException(404, "Assessment not found")
    if assessment.assessment_type == "quiz" and "questions" in assessment.configuration:
        raise HTTPException(409, "Use the automated quiz attempt endpoint for this assessment")
    enrollment = await _enrollment(session, assessment.course_id, principal.user_id)
    if enrollment.status != "approved":
        raise HTTPException(403, "An approved enrollment is required")
    if assessment.due_at is not None:
        due_at = assessment.due_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if datetime.now(UTC) > due_at:
            raise HTTPException(409, "The assessment submission deadline has passed")
    attempt = LearningAssessmentAttempt(
        assessment_id=assessment_id, learner_id=principal.user_id, submission=body.submission
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return {"id": attempt.id, "submitted_at": attempt.submitted_at, "status": "submitted"}


@router.post("/submissions/{attempt_id}/evaluate")
async def evaluate_submission(
    organization_id: str,
    attempt_id: str,
    body: Evaluation,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Evaluation permission required")
    attempt = await session.scalar(
        select(LearningAssessmentAttempt)
        .join(LearningAssessment)
        .join(LearningCourse)
        .where(
            LearningAssessmentAttempt.id == attempt_id,
            LearningCourse.organization_id == organization_id,
        )
    )
    if attempt is None:
        raise HTTPException(404, "Submission not found")
    assessment = await session.get(LearningAssessment, attempt.assessment_id)
    if (
        assessment is not None
        and assessment.assessment_type == "quiz"
        and "questions" in assessment.configuration
    ):
        raise HTTPException(409, "Automated quiz results cannot be manually re-scored")
    evaluated_at = datetime.now(UTC)
    evaluation = LearningAssessmentEvaluation(
        attempt_id=attempt.id,
        score=body.score,
        feedback=body.feedback,
        previous_score=attempt.score,
        previous_feedback=attempt.feedback,
        evaluated_by=principal.user_id,
        evaluated_at=evaluated_at,
    )
    session.add(evaluation)
    attempt.score = body.score
    attempt.feedback = body.feedback
    attempt.evaluated_by = principal.user_id
    attempt.evaluated_at = evaluated_at
    await session.commit()
    await session.refresh(evaluation)
    return {
        "id": attempt.id,
        "evaluation_id": evaluation.id,
        "score": attempt.score,
        "evaluated_at": attempt.evaluated_at,
    }


@router.get("/submissions/{attempt_id}/evaluations")
async def list_submission_evaluations(
    organization_id: str,
    attempt_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """Return the immutable evaluation timeline to authorised tenant staff."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Evaluation history permission required")
    attempt = await session.scalar(
        select(LearningAssessmentAttempt)
        .join(LearningAssessment)
        .join(LearningCourse)
        .where(
            LearningAssessmentAttempt.id == attempt_id,
            LearningCourse.organization_id == organization_id,
        )
    )
    if attempt is None:
        raise HTTPException(404, "Submission not found")
    rows = await session.scalars(
        select(LearningAssessmentEvaluation)
        .where(LearningAssessmentEvaluation.attempt_id == attempt_id)
        .order_by(
            LearningAssessmentEvaluation.evaluated_at,
            LearningAssessmentEvaluation.id,
        )
        .limit(100)
    )
    return [
        {
            "id": row.id,
            "score": row.score,
            "feedback": row.feedback,
            "previous_score": row.previous_score,
            "previous_feedback": row.previous_feedback,
            "evaluated_by": row.evaluated_by,
            "evaluated_at": row.evaluated_at,
        }
        for row in rows.all()
    ]


@router.get("/courses/{course_id}/submissions")
async def list_course_submissions(
    organization_id: str,
    course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """List learner submissions for staff review within the active tenant."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Assessment review permission required")
    await _course(session, organization_id, course_id)
    rows = await session.execute(
        select(LearningAssessmentAttempt, LearningAssessment)
        .join(LearningAssessment, LearningAssessment.id == LearningAssessmentAttempt.assessment_id)
        .where(LearningAssessment.course_id == course_id)
        .order_by(LearningAssessmentAttempt.submitted_at.desc())
        .limit(500)
    )
    submission_rows = rows.all()
    attempt_ids = [attempt.id for attempt, _ in submission_rows]
    evaluation_rows = (
        list(
            await session.scalars(
                select(LearningAssessmentEvaluation)
                .where(LearningAssessmentEvaluation.attempt_id.in_(attempt_ids))
                .order_by(
                    LearningAssessmentEvaluation.evaluated_at,
                    LearningAssessmentEvaluation.id,
                )
            )
        )
        if attempt_ids
        else []
    )
    history_by_attempt: dict[str, list[dict[str, object]]] = {}
    for evaluation in evaluation_rows:
        history_by_attempt.setdefault(evaluation.attempt_id, []).append(
            {
                "id": evaluation.id,
                "score": evaluation.score,
                "feedback": evaluation.feedback,
                "previous_score": evaluation.previous_score,
                "previous_feedback": evaluation.previous_feedback,
                "evaluated_by": evaluation.evaluated_by,
                "evaluated_at": evaluation.evaluated_at,
            }
        )
    return [
        {
            "id": attempt.id,
            "assessment_id": assessment.id,
            "assessment_title": assessment.title,
            "learner_id": attempt.learner_id,
            "submission": attempt.submission,
            "score": attempt.score,
            "feedback": attempt.feedback,
            "submitted_at": attempt.submitted_at,
            "evaluated_at": attempt.evaluated_at,
            "evaluation_history": history_by_attempt.get(attempt.id, []),
        }
        for attempt, assessment in submission_rows
    ]


@router.get("/courses/{course_id}/attendance")
async def list_course_attendance(
    organization_id: str,
    course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """List course attendance records for authorised programme staff."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Attendance reporting permission required")
    await _course(session, organization_id, course_id)
    rows = await session.scalars(
        select(LearningAttendance)
        .where(LearningAttendance.course_id == course_id)
        .order_by(LearningAttendance.session_date.desc(), LearningAttendance.session_title)
        .limit(500)
    )
    return [
        {
            "id": row.id,
            "session_key": row.session_key,
            "session_title": row.session_title,
            "session_date": row.session_date,
            "learner_id": row.learner_id,
            "attendance_status": row.attendance_status,
        }
        for row in rows.all()
    ]


@router.get("/courses/{course_id}/attendance/export")
async def export_course_attendance(
    organization_id: str,
    course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export a bounded, tenant-scoped attendance register as spreadsheet-safe CSV."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Attendance export permission required")
    await _course(session, organization_id, course_id)
    rows = await session.scalars(
        select(LearningAttendance)
        .where(LearningAttendance.course_id == course_id)
        .order_by(
            LearningAttendance.session_date.desc(),
            LearningAttendance.session_title,
            LearningAttendance.learner_id,
        )
        .limit(5000)
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["session_key", "session_title", "session_date", "learner_id", "attendance_status"]
    )
    for row in rows.all():
        values = [
            row.session_key,
            row.session_title,
            row.session_date.isoformat(),
            row.learner_id,
            row.attendance_status,
        ]
        writer.writerow(
            ["'" + value if value.startswith(("=", "+", "-", "@")) else value for value in values]
        )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="attendance-{course_id}.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/courses/{course_id}/mentorships")
async def list_course_mentorships(
    organization_id: str,
    course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """List course mentorship assignments for authorised programme staff."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Mentorship reporting permission required")
    await _course(session, organization_id, course_id)
    rows = await session.scalars(
        select(LearningMentorship)
        .where(LearningMentorship.course_id == course_id)
        .order_by(LearningMentorship.created_at.desc())
        .limit(500)
    )
    return [
        {
            "id": row.id,
            "mentor_id": row.mentor_id,
            "mentee_id": row.mentee_id,
            "status": row.status,
            "notes": row.notes,
            "created_at": row.created_at,
        }
        for row in rows.all()
    ]


@router.post("/courses/{course_id}/mentorships", status_code=201)
async def assign_mentor(
    organization_id: str,
    course_id: str,
    body: MentorAssign,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Mentorship assignment permission required")
    await _course(session, organization_id, course_id)
    mentor_membership = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == body.mentor_id,
            Membership.status == "active",
        )
    )
    mentee_membership = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == body.mentee_id,
            Membership.status == "active",
        )
    )
    eligible_mentor = mentor_membership is not None and await membership_has_any_role(
        session, mentor_membership, _MANAGE | {"researcher"}
    )
    if not eligible_mentor or mentee_membership is None or body.mentor_id == body.mentee_id:
        raise HTTPException(
            422,
            "Mentor and mentee must be distinct active members; "
            "the mentor must hold an eligible role",
        )
    assignment = LearningMentorship(
        course_id=course_id,
        mentor_id=body.mentor_id,
        mentee_id=body.mentee_id,
        notes=body.notes,
        assigned_by=principal.user_id,
        status="active",
    )
    session.add(assignment)
    try:
        await session.commit()
        await session.refresh(assignment)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "This mentorship assignment already exists") from exc
    return {
        "id": assignment.id,
        "mentor_id": assignment.mentor_id,
        "mentee_id": assignment.mentee_id,
        "status": assignment.status,
    }


@router.patch("/courses/{course_id}/mentorships/{mentorship_id}/status")
async def update_mentorship_status(
    organization_id: str,
    course_id: str,
    mentorship_id: str,
    body: MentorshipStatusUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Close an active mentorship and append an organisation audit event."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Mentorship management permission required")
    await _course(session, organization_id, course_id)
    assignment = await session.scalar(
        select(LearningMentorship).where(
            LearningMentorship.id == mentorship_id,
            LearningMentorship.course_id == course_id,
        )
    )
    if assignment is None:
        raise HTTPException(404, "Mentorship assignment not found")
    if assignment.status != "active":
        raise HTTPException(409, "Only active mentorships can be closed")
    previous_status = assignment.status
    assignment.status = body.status
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=assignment.mentee_id,
            action="learning.mentorship.status_changed",
            changes={
                "mentorship_id": assignment.id,
                "course_id": course_id,
                "mentor_id": assignment.mentor_id,
                "from": previous_status,
                "to": body.status,
            },
        )
    )
    await session.commit()
    return {"id": assignment.id, "status": assignment.status}


@router.post("/courses/{course_id}/attendance/bulk", status_code=201)
async def record_bulk_attendance(
    organization_id: str,
    course_id: str,
    body: AttendanceBulkCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Record one workshop roll call atomically for up to 100 approved learners."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Attendance recording permission required")
    await _course(session, organization_id, course_id)
    learner_ids = [item.learner_id for item in body.learners]
    if len(set(learner_ids)) != len(learner_ids):
        raise HTTPException(422, "A learner may appear only once in a workshop roll call")
    enrolled_rows = await session.scalars(
        select(LearningEnrollment.learner_id).where(
            LearningEnrollment.course_id == course_id,
            LearningEnrollment.learner_id.in_(learner_ids),
            LearningEnrollment.status.in_({"approved", "completed"}),
        )
    )
    eligible = set(enrolled_rows.all())
    if eligible != set(learner_ids):
        raise HTTPException(422, "Every attendee must have an approved course enrollment")
    records = [
        LearningAttendance(
            course_id=course_id,
            recorded_by=principal.user_id,
            session_key=body.session_key,
            session_title=body.session_title,
            session_date=body.session_date,
            learner_id=item.learner_id,
            attendance_status=item.attendance_status,
        )
        for item in body.learners
    ]
    session.add_all(records)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            409,
            "At least one learner already has attendance for this workshop session",
        ) from exc
    return {
        "session_key": body.session_key,
        "recorded": len(records),
        "records": [
            {"id": row.id, "learner_id": row.learner_id, "attendance_status": row.attendance_status}
            for row in records
        ],
    }


@router.post("/courses/{course_id}/attendance", status_code=201)
async def record_attendance(
    organization_id: str,
    course_id: str,
    body: AttendanceCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Attendance recording permission required")
    await _course(session, organization_id, course_id)
    enrolled = await session.scalar(
        select(LearningEnrollment.id).where(
            LearningEnrollment.course_id == course_id,
            LearningEnrollment.learner_id == body.learner_id,
            LearningEnrollment.status.in_({"approved", "completed"}),
        )
    )
    if enrolled is None:
        raise HTTPException(422, "Attendance requires an approved learner")
    record = LearningAttendance(
        course_id=course_id, recorded_by=principal.user_id, **body.model_dump()
    )
    session.add(record)
    try:
        await session.commit()
        await session.refresh(record)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Attendance for this learner and session already exists") from exc
    return {
        "id": record.id,
        "learner_id": record.learner_id,
        "attendance_status": record.attendance_status,
    }


@router.post("/courses/{course_id}/resources", status_code=201)
async def add_resource(
    organization_id: str,
    course_id: str,
    body: ResourceCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Learning resource management permission required")
    await _course(session, organization_id, course_id)
    if body.lesson_id is not None:
        lesson = await session.scalar(
            select(LearningLesson)
            .join(LearningModule)
            .join(LearningCourse)
            .where(
                LearningLesson.id == body.lesson_id,
                LearningCourse.id == course_id,
                LearningCourse.organization_id == organization_id,
            )
        )
        if lesson is None:
            raise HTTPException(404, "Lesson not found in this course")
    if body.resource_type == "link" and not body.resource_url:
        raise HTTPException(422, "Link resources require resource_url")
    if body.resource_type != "link" and not body.resource_url and not body.storage_reference:
        raise HTTPException(422, "Provide a resource URL or private storage reference")
    resource = LearningResource(
        course_id=course_id, uploaded_by=principal.user_id, **body.model_dump()
    )
    session.add(resource)
    await session.commit()
    await session.refresh(resource)
    return {
        "id": resource.id,
        "title": resource.title,
        "resource_type": resource.resource_type,
        "lesson_id": resource.lesson_id,
    }


@router.post("/lessons/{lesson_id}/complete")
async def complete_lesson(
    organization_id: str,
    lesson_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _LEARN):
        raise HTTPException(403, "Learner access required")
    lesson = await session.scalar(
        select(LearningLesson)
        .join(LearningModule)
        .join(LearningCourse)
        .where(
            LearningLesson.id == lesson_id,
            LearningCourse.organization_id == organization_id,
            LearningCourse.status == "published",
        )
    )
    if lesson is None:
        raise HTTPException(404, "Published lesson not found")
    course_id = (
        await session.scalar(
            select(LearningModule.course_id).where(LearningModule.id == lesson.module_id)
        )
    ) or ""
    enrollment = await _approved_enrollment(session, course_id, principal.user_id)

    completion = await session.scalar(
        select(LearningLessonCompletion).where(
            LearningLessonCompletion.enrollment_id == enrollment.id,
            LearningLessonCompletion.lesson_id == lesson_id,
        )
    )
    if completion is None:
        session.add(
            LearningLessonCompletion(
                enrollment_id=enrollment.id,
                lesson_id=lesson_id,
            )
        )

    lesson_ids = await session.scalars(
        select(LearningLesson.id)
        .join(LearningModule)
        .where(LearningModule.course_id == enrollment.course_id)
    )
    total_lessons = set(lesson_ids.all())
    assessment_rows = await session.scalars(
        select(LearningAssessment).where(LearningAssessment.course_id == enrollment.course_id)
    )
    assessments = assessment_rows.all()
    attempts = await session.scalars(
        select(LearningAssessmentAttempt)
        .join(LearningAssessment)
        .where(
            LearningAssessment.course_id == enrollment.course_id,
            LearningAssessmentAttempt.learner_id == principal.user_id,
        )
    )
    pass_marks = {item.id: item.pass_mark for item in assessments}
    passed_assessments = {
        attempt.assessment_id
        for attempt in attempts.all()
        if attempt.score is not None and attempt.score >= pass_marks.get(attempt.assessment_id, 101)
    }
    completion_rows = await session.scalars(
        select(LearningLessonCompletion.lesson_id).where(
            LearningLessonCompletion.enrollment_id == enrollment.id
        )
    )
    completed_lessons = set(completion_rows.all())
    completed_lessons.add(lesson_id)

    total_units = len(total_lessons) + len(assessments)
    completed_units = len(total_lessons & completed_lessons) + len(passed_assessments)
    enrollment.progress_percent = int(completed_units * 100 / total_units)
    certificate = None
    if total_units > 0 and completed_units == total_units:
        enrollment.status = "completed"
        certificate = await session.scalar(
            select(LearningCertificate).where(LearningCertificate.enrollment_id == enrollment.id)
        )
        if certificate is None:
            certificate = LearningCertificate(
                enrollment_id=enrollment.id,
                certificate_number=f"NGE-{secrets.token_hex(6).upper()}",
                verification_code=secrets.token_urlsafe(32),
                status="valid",
            )
            session.add(certificate)

    await session.commit()
    if certificate is not None:
        await session.refresh(certificate)
    return {
        "enrollment_id": enrollment.id,
        "status": enrollment.status,
        "progress_percent": enrollment.progress_percent,
        "certificate_id": certificate.id if certificate else None,
        "certificate_number": certificate.certificate_number if certificate else None,
        "verification_code": certificate.verification_code if certificate else None,
    }


@router.get("/certificates/{certificate_id}/download")
async def download_certificate(
    organization_id: str,
    certificate_id: str,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Download a valid certificate for its learner or authorised course managers."""
    roles = await get_membership_roles(session, membership)
    if not roles & _LEARN:
        raise HTTPException(403, "Learning access required")
    row = await session.execute(
        select(LearningCertificate, LearningEnrollment, LearningCourse, Organization, User)
        .join(LearningEnrollment, LearningEnrollment.id == LearningCertificate.enrollment_id)
        .join(LearningCourse, LearningCourse.id == LearningEnrollment.course_id)
        .join(Organization, Organization.id == LearningCourse.organization_id)
        .join(User, User.id == LearningEnrollment.learner_id)
        .where(
            LearningCertificate.id == certificate_id,
            LearningCourse.organization_id == organization_id,
        )
    )
    result = row.first()
    if result is None:
        raise HTTPException(404, "Certificate not found")
    certificate, enrollment, course, organization, user = result
    if principal.user_id != enrollment.learner_id and not roles & _MANAGE:
        raise HTTPException(403, "You cannot download another learner's certificate")
    if certificate.status != "valid":
        raise HTTPException(410, "This certificate has been revoked")

    profile = await session.scalar(
        select(ResearcherProfile).where(ResearcherProfile.user_id == user.id)
    )
    recipient = profile.display_name if profile is not None else user.identifier
    public_base_url = str(request.app.state.settings.public_base_url).rstrip("/")
    verification_url = f"{public_base_url}/certificates/verify?code={certificate.verification_code}"
    pdf_bytes = render_certificate(
        recipient=recipient,
        course_title=course.title,
        organization_name=organization.name,
        certificate_number=certificate.certificate_number,
        verification_code=certificate.verification_code,
        issued_at=certificate.issued_at,
        verification_url=verification_url,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (f'attachment; filename="{certificate.certificate_number}.pdf"'),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/certificates/verify/{verification_code}")
async def verify_certificate(
    organization_id: str,
    verification_code: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    row = await session.scalar(
        select(LearningCertificate)
        .join(LearningEnrollment)
        .join(LearningCourse)
        .where(
            LearningCertificate.verification_code == verification_code,
            LearningCourse.organization_id == organization_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Certificate not found")
    enrollment = await session.get(LearningEnrollment, row.enrollment_id)
    if enrollment is None:
        raise HTTPException(404, "Certificate enrollment not found")
    course = await _course(session, organization_id, enrollment.course_id)
    return {
        "valid": row.status == "valid",
        "certificate_number": row.certificate_number,
        "course_title": course.title,
        "issued_at": row.issued_at,
        "status": row.status,
    }


@router.get("/courses/{course_id}/curriculum")
async def course_curriculum(
    organization_id: str,
    course_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Return ordered modules and lessons without exposing draft content to learners."""
    course = await _course(session, organization_id, course_id)
    if course.status != "published" and not await membership_has_any_role(
        session, membership, _MANAGE
    ):
        raise HTTPException(404, "Course not found")
    if not await membership_has_any_role(session, membership, _MANAGE):
        if not await membership_has_any_role(session, membership, _LEARN):
            raise HTTPException(403, "Learner access required")
        await _approved_enrollment(session, course_id, principal.user_id)
    modules = await session.scalars(
        select(LearningModule)
        .where(LearningModule.course_id == course_id)
        .order_by(LearningModule.position)
    )
    module_rows = modules.all()
    result: list[dict[str, object]] = []
    for module in module_rows:
        lessons = await session.scalars(
            select(LearningLesson)
            .where(LearningLesson.module_id == module.id)
            .order_by(LearningLesson.position)
        )
        result.append(
            {
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "position": module.position,
                "lessons": [
                    {
                        "id": lesson.id,
                        "title": lesson.title,
                        "content_type": lesson.content_type,
                        "content": lesson.content,
                        "resource_url": lesson.resource_url,
                        "duration_minutes": lesson.duration_minutes,
                        "position": lesson.position,
                    }
                    for lesson in lessons.all()
                ],
            }
        )
    return {
        "course_id": course.id,
        "title": course.title,
        "description": course.description,
        "modules": result,
    }


@router.get("/courses/{course_id}/my-progress")
async def my_course_progress(
    organization_id: str,
    course_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Return only the authenticated learner's own completion and assessment results."""
    if not await membership_has_any_role(session, membership, _LEARN):
        raise HTTPException(403, "Learner access required")
    course = await _course(session, organization_id, course_id)
    if course.status != "published":
        raise HTTPException(404, "Course not found")
    enrollment = await _approved_enrollment(session, course_id, principal.user_id)
    completed = await session.scalars(
        select(LearningLessonCompletion.lesson_id).where(
            LearningLessonCompletion.enrollment_id == enrollment.id
        )
    )
    certificate = await session.scalar(
        select(LearningCertificate).where(LearningCertificate.enrollment_id == enrollment.id)
    )
    attempts = await session.execute(
        select(
            LearningAssessmentAttempt.assessment_id,
            LearningAssessmentAttempt.score,
            LearningAssessmentAttempt.feedback,
            LearningAssessmentAttempt.evaluated_at,
        )
        .join(LearningAssessment)
        .where(
            LearningAssessment.course_id == course_id,
            LearningAssessmentAttempt.learner_id == principal.user_id,
        )
        .order_by(LearningAssessmentAttempt.submitted_at.desc())
        .limit(200)
    )
    return {
        "course_id": course_id,
        "enrollment_status": enrollment.status,
        "progress_percent": enrollment.progress_percent,
        "certificate_id": certificate.id if certificate is not None else None,
        "certificate_number": certificate.certificate_number if certificate is not None else None,
        "certificate_status": certificate.status if certificate is not None else None,
        "completed_lesson_ids": list(completed.all()),
        "assessments": [
            {
                "assessment_id": row.assessment_id,
                "score": row.score,
                "feedback": row.feedback,
                "evaluated_at": row.evaluated_at,
            }
            for row in attempts
        ],
    }


@router.get("/my-mentorships")
async def my_mentorships(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """Return mentorship relationships involving the authenticated member only."""
    if not await membership_has_any_role(session, membership, _LEARN):
        raise HTTPException(403, "Learner access required")
    rows = await session.execute(
        select(LearningMentorship, LearningCourse.title)
        .join(LearningCourse, LearningCourse.id == LearningMentorship.course_id)
        .where(
            LearningCourse.organization_id == organization_id,
            (LearningMentorship.mentor_id == principal.user_id)
            | (LearningMentorship.mentee_id == principal.user_id),
        )
        .order_by(LearningMentorship.created_at.desc())
        .limit(200)
    )
    return [
        {
            "id": item.id,
            "course_id": item.course_id,
            "course_title": title,
            "relationship": "mentor" if item.mentor_id == principal.user_id else "mentee",
            "status": item.status,
            "notes": item.notes,
            "created_at": item.created_at,
        }
        for item, title in rows.all()
    ]


@router.get("/my-attendance")
async def my_attendance(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """Return attendance history for the authenticated learner only."""
    if not await membership_has_any_role(session, membership, _LEARN):
        raise HTTPException(403, "Learner access required")
    rows = await session.execute(
        select(LearningAttendance, LearningCourse.title)
        .join(LearningCourse, LearningCourse.id == LearningAttendance.course_id)
        .where(
            LearningCourse.organization_id == organization_id,
            LearningAttendance.learner_id == principal.user_id,
        )
        .order_by(LearningAttendance.session_date.desc())
        .limit(500)
    )
    return [
        {
            "id": item.id,
            "course_id": item.course_id,
            "course_title": title,
            "session_key": item.session_key,
            "session_title": item.session_title,
            "session_date": item.session_date,
            "attendance_status": item.attendance_status,
        }
        for item, title in rows.all()
    ]


@router.get("/courses/{course_id}/resources")
async def list_learning_resources(
    organization_id: str,
    course_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """List course resources while never returning internal storage references."""
    course = await _course(session, organization_id, course_id)
    if course.status != "published" and not await membership_has_any_role(
        session, membership, _MANAGE
    ):
        raise HTTPException(404, "Course not found")
    if not await membership_has_any_role(session, membership, _MANAGE):
        if not await membership_has_any_role(session, membership, _LEARN):
            raise HTTPException(403, "Learner access required")
        await _approved_enrollment(session, course_id, principal.user_id)
    resources = await session.scalars(
        select(LearningResource)
        .where(LearningResource.course_id == course_id)
        .order_by(LearningResource.title)
        .limit(200)
    )
    return [
        {
            "id": item.id,
            "lesson_id": item.lesson_id,
            "title": item.title,
            "resource_type": item.resource_type,
            "description": item.description,
            "resource_url": item.resource_url,
        }
        for item in resources.all()
    ]


@router.post("/certificates/{certificate_id}/revoke")
async def revoke_certificate(
    organization_id: str,
    certificate_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Revoke a credential through an auditable, tenant-scoped staff action."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Certificate administration permission required")
    certificate = await session.scalar(
        select(LearningCertificate)
        .join(LearningEnrollment)
        .join(LearningCourse)
        .where(
            LearningCertificate.id == certificate_id,
            LearningCourse.organization_id == organization_id,
        )
    )
    if certificate is None:
        raise HTTPException(404, "Certificate not found")
    if certificate.status == "revoked":
        raise HTTPException(409, "Certificate has already been revoked")
    certificate.status = "revoked"
    certificate.revoked_at = datetime.now(UTC)
    certificate.revoked_by = principal.user_id
    await session.commit()
    return {
        "id": certificate.id,
        "status": certificate.status,
        "revoked_at": certificate.revoked_at,
    }


@router.get("/programmes/{programme_id}/outcomes")
async def programme_outcomes(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Aggregate course delivery, learner progress and support outcomes."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Programme reporting permission required")
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(404, "Programme not found")
    course_rows = await session.scalars(
        select(LearningCourse)
        .where(
            LearningCourse.organization_id == organization_id,
            LearningCourse.programme_id == programme_id,
        )
        .order_by(LearningCourse.title, LearningCourse.id)
        .limit(200)
    )
    courses = course_rows.all()
    course_reports = [
        cast(
            dict[str, Any],
            await course_progress(organization_id, course.id, membership, session),
        )
        for course in courses
    ]
    programme_course_ids = [course.id for course in courses]
    enrollment_rows = await session.scalars(
        select(LearningEnrollment).where(LearningEnrollment.course_id.in_(programme_course_ids))
    )
    enrolments = enrollment_rows.all()
    progress_by_learner: dict[str, list[int]] = {}
    for enrolment in enrolments:
        progress_by_learner.setdefault(enrolment.learner_id, []).append(enrolment.progress_percent)
    learner_count = len(progress_by_learner)
    learner_average_progress = [
        sum(progress_values) / len(progress_values)
        for progress_values in progress_by_learner.values()
    ]
    average_progress = (
        round(sum(learner_average_progress) / learner_count, 1) if learner_count else 0.0
    )
    totals = {
        "learners": learner_count,
        "enrolments": len(enrolments),
        "approved": sum(int(report["approved"]) for report in course_reports),
        "completed": sum(int(report["completed"]) for report in course_reports),
        "attendance_records": sum(int(report["attendance_records"]) for report in course_reports),
        "attendance_sessions": sum(int(report["attendance_sessions"]) for report in course_reports),
        "mentorship_assignments": sum(
            int(report["mentorship_assignments"]) for report in course_reports
        ),
        "active_mentorships": sum(int(report["active_mentorships"]) for report in course_reports),
        "assessment_submissions": sum(
            int(report["assessment_submissions"]) for report in course_reports
        ),
        "evaluated_submissions": sum(
            int(report["evaluated_submissions"]) for report in course_reports
        ),
        "pending_evaluations": sum(int(report["pending_evaluations"]) for report in course_reports),
    }
    return {
        "programme_id": programme.id,
        "programme_title": programme.title,
        "course_count": len(courses),
        "average_progress": average_progress,
        "totals": totals,
        "courses": [
            {
                "course_id": course.id,
                "title": course.title,
                "status": course.status,
                **report,
                "enrolments": int(report["learners"]),
            }
            for course, report in zip(courses, course_reports, strict=True)
        ],
    }


@router.get("/programmes/{programme_id}/outcomes/export")
async def export_programme_outcomes(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Download a tenant-scoped programme outcomes report as spreadsheet-safe CSV."""
    report = await programme_outcomes(organization_id, programme_id, membership, session)

    def safe_cell(value: object) -> str:
        rendered = "" if value is None else str(value)
        if rendered.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + rendered
        return rendered

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["section", "metric", "value"])
    totals = report["totals"]
    if isinstance(totals, dict):
        for key, value in totals.items():
            writer.writerow([safe_cell("programme_total"), safe_cell(key), safe_cell(value)])
    writer.writerow(
        [
            safe_cell("programme"),
            safe_cell("average_progress"),
            safe_cell(report["average_progress"]),
        ]
    )
    writer.writerow([])
    writer.writerow(
        [
            "course_id",
            "course_title",
            "status",
            "enrolments",
            "approved",
            "completed",
            "average_progress",
            "attendance_records",
            "attendance_sessions",
            "mentorship_assignments",
            "active_mentorships",
            "assessment_submissions",
            "evaluated_submissions",
            "pending_evaluations",
        ]
    )
    courses = report["courses"]
    if isinstance(courses, list):
        for course in courses:
            if isinstance(course, dict):
                writer.writerow(
                    [
                        safe_cell(course.get("course_id")),
                        safe_cell(course.get("title")),
                        safe_cell(course.get("status")),
                        *[
                            safe_cell(course.get(key))
                            for key in (
                                "enrolments",
                                "approved",
                                "completed",
                                "average_progress",
                                "attendance_records",
                                "attendance_sessions",
                                "mentorship_assignments",
                                "active_mentorships",
                                "assessment_submissions",
                                "evaluated_submissions",
                                "pending_evaluations",
                            )
                        ],
                    ]
                )
    filename = f"programme-{programme_id}-outcomes.csv"
    return Response(
        content="\\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/courses/{course_id}/learners/{learner_id}/progress")
async def learner_course_progress_detail(
    organization_id: str,
    course_id: str,
    learner_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Return a tenant-scoped staff view of one learner's course activity."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Learner progress permission required")
    await _course(session, organization_id, course_id)
    enrollment = await session.scalar(
        select(LearningEnrollment).where(
            LearningEnrollment.course_id == course_id,
            LearningEnrollment.learner_id == learner_id,
        )
    )
    if enrollment is None:
        raise HTTPException(404, "Learner enrolment not found")
    lesson_rows = await session.execute(
        select(
            LearningModule.id,
            LearningModule.title,
            LearningLesson.id,
            LearningLesson.title,
            LearningLesson.position,
            LearningLessonCompletion.completed_at,
        )
        .join(LearningLesson, LearningLesson.module_id == LearningModule.id)
        .outerjoin(
            LearningLessonCompletion,
            (LearningLessonCompletion.lesson_id == LearningLesson.id)
            & (LearningLessonCompletion.enrollment_id == enrollment.id),
        )
        .where(LearningModule.course_id == course_id)
        .order_by(LearningModule.position, LearningLesson.position)
    )
    assessment_rows = await session.execute(
        select(
            LearningAssessment.id,
            LearningAssessment.title,
            LearningAssessmentAttempt.id,
            LearningAssessmentAttempt.score,
            LearningAssessmentAttempt.feedback,
            LearningAssessmentAttempt.submitted_at,
            LearningAssessmentAttempt.evaluated_at,
        )
        .outerjoin(
            LearningAssessmentAttempt,
            (LearningAssessmentAttempt.assessment_id == LearningAssessment.id)
            & (LearningAssessmentAttempt.learner_id == learner_id),
        )
        .where(LearningAssessment.course_id == course_id)
        .order_by(LearningAssessment.title, LearningAssessmentAttempt.submitted_at)
    )
    attendance_rows = await session.scalars(
        select(LearningAttendance)
        .where(
            LearningAttendance.course_id == course_id,
            LearningAttendance.learner_id == learner_id,
        )
        .order_by(LearningAttendance.session_date.desc())
        .limit(200)
    )
    mentorship_rows = await session.scalars(
        select(LearningMentorship)
        .where(
            LearningMentorship.course_id == course_id,
            LearningMentorship.mentee_id == learner_id,
        )
        .order_by(LearningMentorship.created_at.desc())
        .limit(100)
    )
    lessons = [
        {
            "module_id": row[0],
            "module_title": row[1],
            "lesson_id": row[2],
            "lesson_title": row[3],
            "position": row[4],
            "completed_at": row[5],
            "completed": row[5] is not None,
        }
        for row in lesson_rows.all()
    ]
    assessments = [
        {
            "assessment_id": row[0],
            "assessment_title": row[1],
            "attempt_id": row[2],
            "score": row[3],
            "feedback": row[4],
            "submitted_at": row[5],
            "evaluated_at": row[6],
        }
        for row in assessment_rows.all()
    ]
    attendance = [
        {
            "session_key": item.session_key,
            "session_title": item.session_title,
            "session_date": item.session_date,
            "attendance_status": item.attendance_status,
        }
        for item in attendance_rows.all()
    ]
    mentorships = [
        {
            "id": item.id,
            "mentor_id": item.mentor_id,
            "status": item.status,
            "created_at": item.created_at,
        }
        for item in mentorship_rows.all()
    ]
    return {
        "course_id": course_id,
        "learner_id": learner_id,
        "enrollment": {
            "id": enrollment.id,
            "status": enrollment.status,
            "progress_percent": enrollment.progress_percent,
            "applied_at": enrollment.applied_at,
            "reviewed_at": enrollment.reviewed_at,
        },
        "lessons": lessons,
        "assessments": assessments,
        "attendance": attendance,
        "mentorships": mentorships,
    }


@router.get("/courses/{course_id}/progress")
async def course_progress(
    organization_id: str,
    course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course reporting permission required")
    await _course(session, organization_id, course_id)
    rows = await session.scalars(
        select(LearningEnrollment).where(LearningEnrollment.course_id == course_id)
    )
    enrollments = rows.all()
    attendance_rows = await session.scalars(
        select(LearningAttendance).where(LearningAttendance.course_id == course_id)
    )
    attendance = attendance_rows.all()
    mentorship_rows = await session.scalars(
        select(LearningMentorship).where(LearningMentorship.course_id == course_id)
    )
    mentorships = mentorship_rows.all()
    attempt_rows = await session.scalars(
        select(LearningAssessmentAttempt)
        .join(LearningAssessment)
        .where(LearningAssessment.course_id == course_id)
    )
    attempts = attempt_rows.all()
    attendance_by_status = {
        status: sum(row.attendance_status == status for row in attendance)
        for status in ("present", "late", "absent", "excused")
    }
    return {
        "course_id": course_id,
        "learners": len(enrollments),
        "approved": sum(x.status in {"approved", "completed"} for x in enrollments),
        "completed": sum(x.status == "completed" for x in enrollments),
        "average_progress": round(
            sum(x.progress_percent for x in enrollments) / len(enrollments), 1
        )
        if enrollments
        else 0.0,
        "attendance_records": len(attendance),
        "attendance_by_status": attendance_by_status,
        "attendance_sessions": len({row.session_key for row in attendance}),
        "mentorship_assignments": len(mentorships),
        "active_mentorships": sum(row.status == "active" for row in mentorships),
        "assessment_submissions": len(attempts),
        "evaluated_submissions": sum(row.evaluated_at is not None for row in attempts),
        "pending_evaluations": sum(row.evaluated_at is None for row in attempts),
    }


@router.get("/portfolio-outcomes")
async def organisation_learning_outcomes(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Aggregate learning outcomes across every programme in an organisation."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Learning portfolio reporting permission required")
    programme_rows = await session.scalars(
        select(Programme)
        .where(Programme.organization_id == organization_id)
        .order_by(Programme.title, Programme.id)
        .limit(100)
    )
    reports = [
        cast(
            dict[str, Any],
            await programme_outcomes(organization_id, programme.id, membership, session),
        )
        for programme in programme_rows.all()
    ]
    metric_keys = (
        "enrolments",
        "approved",
        "completed",
        "attendance_records",
        "attendance_sessions",
        "mentorship_assignments",
        "active_mentorships",
        "assessment_submissions",
        "evaluated_submissions",
        "pending_evaluations",
    )
    totals = {key: sum(int(report["totals"][key]) for report in reports) for key in metric_keys}
    organisation_course_ids = [
        str(course["course_id"])
        for programme in reports
        for course in cast(list[dict[str, object]], programme["courses"])
    ]
    enrolment_rows = await session.scalars(
        select(LearningEnrollment).where(LearningEnrollment.course_id.in_(organisation_course_ids))
    )
    enrolments = enrolment_rows.all()
    progress_by_learner: dict[str, list[int]] = {}
    for enrolment in enrolments:
        progress_by_learner.setdefault(enrolment.learner_id, []).append(enrolment.progress_percent)
    learner_count = len(progress_by_learner)
    totals["learners"] = learner_count
    learner_average_progress = [
        sum(progress_values) / len(progress_values)
        for progress_values in progress_by_learner.values()
    ]
    average_progress = (
        round(sum(learner_average_progress) / learner_count, 1) if learner_count else 0.0
    )
    return {
        "organization_id": organization_id,
        "programmes_total": len(reports),
        "courses_total": sum(int(report["course_count"]) for report in reports),
        "average_progress": average_progress,
        "totals": totals,
        "programmes": [
            {
                "programme_id": report["programme_id"],
                "programme_title": report["programme_title"],
                "course_count": report["course_count"],
                "average_progress": report["average_progress"],
                "totals": report["totals"],
            }
            for report in reports
        ],
    }


@router.get("/portfolio-outcomes/export")
async def export_organisation_learning_outcomes(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export organisation learning outcomes as formula-safe UTF-8 CSV."""
    report = await organisation_learning_outcomes(organization_id, membership, session)

    def safe_cell(value: object) -> str:
        rendered = "" if value is None else str(value)
        if rendered.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + rendered
        return rendered

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["section", "metric", "value"])
    writer.writerow(["organisation", "programmes_total", safe_cell(report["programmes_total"])])
    writer.writerow(["organisation", "courses_total", safe_cell(report["courses_total"])])
    writer.writerow(["organisation", "average_progress", safe_cell(report["average_progress"])])
    totals = report["totals"]
    if isinstance(totals, dict):
        for key, value in totals.items():
            writer.writerow(["organisation_total", safe_cell(key), safe_cell(value)])
    writer.writerow([])
    writer.writerow(
        [
            "programme_id",
            "programme_title",
            "course_count",
            "average_progress",
            "learners",
            "enrolments",
            "approved",
            "completed",
            "attendance_records",
            "attendance_sessions",
            "mentorship_assignments",
            "active_mentorships",
            "assessment_submissions",
            "evaluated_submissions",
            "pending_evaluations",
        ]
    )
    programmes = report["programmes"]
    if isinstance(programmes, list):
        for programme in programmes:
            if not isinstance(programme, dict):
                continue
            programme_totals = programme.get("totals", {})
            writer.writerow(
                [
                    safe_cell(programme.get("programme_id")),
                    safe_cell(programme.get("programme_title")),
                    safe_cell(programme.get("course_count")),
                    safe_cell(programme.get("average_progress")),
                    *[
                        safe_cell(programme_totals.get(key))
                        for key in (
                            "learners",
                            "enrolments",
                            "approved",
                            "completed",
                            "attendance_records",
                            "attendance_sessions",
                            "mentorship_assignments",
                            "active_mentorships",
                            "assessment_submissions",
                            "evaluated_submissions",
                            "pending_evaluations",
                        )
                    ],
                ]
            )
    return Response(
        content=chr(0xFEFF) + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="organisation-learning-outcomes.csv"'
        },
    )


def _learning_utc(value: datetime) -> datetime:
    """Normalise database datetimes before comparing SQLite and PostgreSQL values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _learner_reference(learner_id: str) -> str:
    """Return a stable privacy-safe staff reference instead of an account identifier."""
    return f"Learner-{hashlib.sha256(learner_id.encode()).hexdigest()[:16].upper()}"


def _intervention_read(item: LearningIntervention, learner_id: str) -> dict[str, object]:
    """Staff-only representation; never used by learner-facing endpoints."""
    return {
        "id": item.id,
        "cohort_id": item.cohort_id,
        "enrollment_id": item.enrollment_id,
        "learner_ref": _learner_reference(learner_id),
        "assigned_to": item.assigned_to,
        "due_date": item.due_date,
        "note": item.note,
        "status": item.status,
        "resolution_note": item.resolution_note,
        "resolved_at": item.resolved_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


async def _cohort_risk_review(
    session: AsyncSession,
    organization_id: str,
    cohort: LearningCohort,
) -> dict[str, object]:
    """Compute deterministic, explainable signals without treating missing data as risk."""
    now = datetime.now(UTC)
    attendance_cutoff = now.date() - timedelta(days=cohort.absence_window_days - 1)
    enrollments_result = await session.scalars(
        select(LearningEnrollment)
        .join(LearningCourse, LearningCourse.id == LearningEnrollment.course_id)
        .where(
            LearningEnrollment.cohort_id == cohort.id,
            LearningEnrollment.status == "approved",
            LearningCourse.organization_id == organization_id,
        )
        .order_by(LearningEnrollment.applied_at, LearningEnrollment.id)
        .limit(500)
    )
    enrollments = enrollments_result.all()
    enrollment_ids = [item.id for item in enrollments]
    course_ids = sorted({item.course_id for item in enrollments})
    learner_ids = sorted({item.learner_id for item in enrollments})

    lesson_activity: dict[str, datetime] = {}
    assessment_activity: dict[tuple[str, str], datetime] = {}
    attended_activity: dict[tuple[str, str], date] = {}
    attendance_counts: dict[tuple[str, str], tuple[int, int]] = {}
    due_assessments: dict[str, list[LearningAssessment]] = {}
    attempts_by_assessment_learner: dict[tuple[str, str], datetime] = {}

    if enrollment_ids:
        lesson_rows = await session.execute(
            select(
                LearningLessonCompletion.enrollment_id,
                func.max(LearningLessonCompletion.completed_at),
            )
            .where(LearningLessonCompletion.enrollment_id.in_(enrollment_ids))
            .group_by(LearningLessonCompletion.enrollment_id)
        )
        lesson_activity = {
            str(enrollment_id): _learning_utc(last_completed)
            for enrollment_id, last_completed in lesson_rows.all()
            if last_completed is not None
        }

    if course_ids and learner_ids:
        assessment_activity_rows = await session.execute(
            select(
                LearningAssessment.course_id,
                LearningAssessmentAttempt.learner_id,
                func.max(LearningAssessmentAttempt.submitted_at),
            )
            .join(
                LearningAssessmentAttempt,
                LearningAssessmentAttempt.assessment_id == LearningAssessment.id,
            )
            .where(
                LearningAssessment.course_id.in_(course_ids),
                LearningAssessmentAttempt.learner_id.in_(learner_ids),
            )
            .group_by(LearningAssessment.course_id, LearningAssessmentAttempt.learner_id)
        )
        assessment_activity = {
            (str(course_id), str(learner_id)): _learning_utc(last_submitted)
            for course_id, learner_id, last_submitted in assessment_activity_rows.all()
            if last_submitted is not None
        }

        attended_rows = await session.execute(
            select(
                LearningAttendance.course_id,
                LearningAttendance.learner_id,
                func.max(LearningAttendance.session_date),
            )
            .where(
                LearningAttendance.course_id.in_(course_ids),
                LearningAttendance.learner_id.in_(learner_ids),
                LearningAttendance.attendance_status.in_({"present", "late"}),
                LearningAttendance.session_date <= now.date(),
            )
            .group_by(LearningAttendance.course_id, LearningAttendance.learner_id)
        )
        attended_activity = {
            (str(course_id), str(learner_id)): last_attended
            for course_id, learner_id, last_attended in attended_rows.all()
            if last_attended is not None
        }

        attendance_rows = await session.execute(
            select(
                LearningAttendance.course_id,
                LearningAttendance.learner_id,
                func.count(LearningAttendance.id),
                func.sum(case((LearningAttendance.attendance_status == "absent", 1), else_=0)),
            )
            .where(
                LearningAttendance.course_id.in_(course_ids),
                LearningAttendance.learner_id.in_(learner_ids),
                LearningAttendance.session_date >= attendance_cutoff,
                LearningAttendance.session_date <= now.date(),
                LearningAttendance.attendance_status.in_({"present", "late", "absent"}),
            )
            .group_by(LearningAttendance.course_id, LearningAttendance.learner_id)
        )
        for course_id, learner_id, total, absences in attendance_rows.all():
            key = (str(course_id), str(learner_id))
            attendance_counts[key] = (int(total or 0), int(absences or 0))

        assessment_result = await session.scalars(
            select(LearningAssessment).where(
                LearningAssessment.course_id.in_(course_ids),
                LearningAssessment.due_at.is_not(None),
            )
        )
        for assessment in assessment_result.all():
            due_assessments.setdefault(assessment.course_id, []).append(assessment)
        assessment_ids = [item.id for items in due_assessments.values() for item in items]
        if assessment_ids:
            attempt_rows = await session.execute(
                select(
                    LearningAssessmentAttempt.assessment_id,
                    LearningAssessmentAttempt.learner_id,
                    func.max(LearningAssessmentAttempt.submitted_at),
                )
                .where(
                    LearningAssessmentAttempt.assessment_id.in_(assessment_ids),
                    LearningAssessmentAttempt.learner_id.in_(learner_ids),
                )
                .group_by(
                    LearningAssessmentAttempt.assessment_id,
                    LearningAssessmentAttempt.learner_id,
                )
            )
            attempts_by_assessment_learner = {
                (str(assessment_id), str(learner_id)): _learning_utc(last_submitted)
                for assessment_id, learner_id, last_submitted in attempt_rows.all()
                if last_submitted is not None
            }

    learner_reviews: list[dict[str, object]] = []
    for enrollment in enrollments:
        key = (enrollment.course_id, enrollment.learner_id)
        last_activity_candidates = [
            lesson_activity.get(enrollment.id),
            assessment_activity.get(key),
        ]
        attended_on = attended_activity.get(key)
        if attended_on is not None:
            last_activity_candidates.append(
                datetime.combine(attended_on, datetime.min.time(), tzinfo=UTC)
            )
        last_activity = max(
            (value for value in last_activity_candidates if value is not None),
            default=None,
        )
        if last_activity is None:
            inactivity_flag: dict[str, object] = {
                "state": "insufficient_data",
                "reason_code": "no_recorded_learner_activity",
                "threshold_days": cohort.inactivity_threshold_days,
                "last_activity_at": None,
            }
        else:
            days_inactive = max(0, (now.date() - last_activity.date()).days)
            inactivity_flag = {
                "state": (
                    "at_risk" if days_inactive >= cohort.inactivity_threshold_days else "clear"
                ),
                "reason_code": (
                    "inactive_over_threshold"
                    if days_inactive >= cohort.inactivity_threshold_days
                    else None
                ),
                "threshold_days": cohort.inactivity_threshold_days,
                "days_since_activity": days_inactive,
                "last_activity_at": last_activity,
            }

        total_attendance, absence_count = attendance_counts.get(key, (0, 0))
        if total_attendance == 0:
            attendance_flag: dict[str, object] = {
                "state": "insufficient_data",
                "reason_code": "no_attendance_records_in_window",
                "absence_count": 0,
                "threshold": cohort.absence_threshold,
                "window_days": cohort.absence_window_days,
            }
        else:
            attendance_flag = {
                "state": "at_risk" if absence_count >= cohort.absence_threshold else "clear",
                "reason_code": (
                    "repeated_absences" if absence_count >= cohort.absence_threshold else None
                ),
                "absence_count": absence_count,
                "attendance_records": total_attendance,
                "threshold": cohort.absence_threshold,
                "window_days": cohort.absence_window_days,
            }

        assessments = due_assessments.get(enrollment.course_id, [])
        overdue_items: list[dict[str, object]] = []
        for assessment in assessments:
            due_at = _learning_utc(assessment.due_at) if assessment.due_at else None
            if due_at is None or due_at + timedelta(days=cohort.overdue_grace_days) >= now:
                continue
            if (assessment.id, enrollment.learner_id) not in attempts_by_assessment_learner:
                overdue_items.append(
                    {
                        "assessment_id": assessment.id,
                        "title": assessment.title,
                        "due_at": due_at,
                    }
                )
        if not assessments:
            assessment_flag: dict[str, object] = {
                "state": "insufficient_data",
                "reason_code": "no_assessments_with_due_dates",
                "overdue_count": 0,
                "grace_days": cohort.overdue_grace_days,
            }
        else:
            assessment_flag = {
                "state": "at_risk" if overdue_items else "clear",
                "reason_code": "overdue_assessments" if overdue_items else None,
                "overdue_count": len(overdue_items),
                "items": overdue_items,
                "grace_days": cohort.overdue_grace_days,
            }

        flags = {
            "inactivity": inactivity_flag,
            "attendance": attendance_flag,
            "assessments": assessment_flag,
        }
        states = [str(item["state"]) for item in flags.values()]
        risk_state = (
            "at_risk"
            if "at_risk" in states
            else "insufficient_data"
            if "insufficient_data" in states
            else "clear"
        )
        reasons = [
            str(item["reason_code"])
            for item in flags.values()
            if item.get("state") == "at_risk" and item.get("reason_code")
        ]
        learner_reviews.append(
            {
                "enrollment_id": enrollment.id,
                "learner_ref": _learner_reference(enrollment.learner_id),
                "course_id": enrollment.course_id,
                "risk_state": risk_state,
                "reason_codes": reasons,
                "flags": flags,
            }
        )

    open_interventions = int(
        await session.scalar(
            select(func.count(LearningIntervention.id)).where(
                LearningIntervention.organization_id == organization_id,
                LearningIntervention.cohort_id == cohort.id,
                LearningIntervention.status.in_({"open", "in_progress"}),
            )
        )
        or 0
    )
    overdue_interventions = int(
        await session.scalar(
            select(func.count(LearningIntervention.id)).where(
                LearningIntervention.organization_id == organization_id,
                LearningIntervention.cohort_id == cohort.id,
                LearningIntervention.status.in_({"open", "in_progress"}),
                LearningIntervention.due_date.is_not(None),
                LearningIntervention.due_date < now.date(),
            )
        )
        or 0
    )
    risk_by_enrollment = {
        str(item["enrollment_id"]): str(item["risk_state"]) for item in learner_reviews
    }
    at_risk_enrolments = [item for item in learner_reviews if item["risk_state"] == "at_risk"]
    insufficient_enrolments = [
        item for item in learner_reviews if item["risk_state"] == "insufficient_data"
    ]
    clear_enrolments = [item for item in learner_reviews if item["risk_state"] == "clear"]
    unique_learner_counts = {
        state: len(
            {
                enrollment.learner_id
                for enrollment in enrollments
                if risk_by_enrollment.get(enrollment.id) == state
            }
        )
        for state in ("at_risk", "insufficient_data", "clear")
    }
    return {
        "cohort_id": cohort.id,
        "cohort_title": cohort.title,
        "thresholds": {
            "inactivity_threshold_days": cohort.inactivity_threshold_days,
            "absence_threshold": cohort.absence_threshold,
            "absence_window_days": cohort.absence_window_days,
            "overdue_grace_days": cohort.overdue_grace_days,
        },
        "summary": {
            "enrolments_reviewed": len(learner_reviews),
            "unique_learners": len({item.learner_id for item in enrollments}),
            "at_risk_enrolments": len(at_risk_enrolments),
            "insufficient_data_enrolments": len(insufficient_enrolments),
            "clear_enrolments": len(clear_enrolments),
            "at_risk_learners": unique_learner_counts["at_risk"],
            "insufficient_data_learners": unique_learner_counts["insufficient_data"],
            "clear_learners": unique_learner_counts["clear"],
            "open_interventions": open_interventions,
            "overdue_interventions": overdue_interventions,
        },
        "learners": learner_reviews,
    }


@router.get("/cohorts/{cohort_id}/risk-review")
async def cohort_learning_risk_review(
    organization_id: str,
    cohort_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Return advisory cohort signals for authorised programme staff only."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Learner risk review permission required")
    cohort = await session.scalar(
        select(LearningCohort).where(
            LearningCohort.id == cohort_id,
            LearningCohort.organization_id == organization_id,
        )
    )
    if cohort is None:
        raise HTTPException(404, "Cohort not found")
    return await _cohort_risk_review(session, organization_id, cohort)


@router.get("/programmes/{programme_id}/risk-review")
async def programme_learning_risk_review(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Aggregate cohort-level advisory signals without exposing learner private notes."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Programme learner risk review permission required")
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(404, "Programme not found")
    cohort_rows = await session.scalars(
        select(LearningCohort)
        .where(
            LearningCohort.organization_id == organization_id,
            LearningCohort.programme_id == programme_id,
        )
        .order_by(LearningCohort.start_date, LearningCohort.title)
        .limit(100)
    )
    cohorts = cohort_rows.all()
    cohort_reviews = [
        await _cohort_risk_review(session, organization_id, cohort) for cohort in cohorts
    ]
    all_enrolment_reviews = [
        learner
        for review in cohort_reviews
        for learner in cast(list[dict[str, object]], review["learners"])
    ]
    at_risk_rows = [item for item in all_enrolment_reviews if item["risk_state"] == "at_risk"]
    insufficient_rows = [
        item for item in all_enrolment_reviews if item["risk_state"] == "insufficient_data"
    ]
    clear_rows = [item for item in all_enrolment_reviews if item["risk_state"] == "clear"]
    enrollment_rows: list[LearningEnrollment] = []
    if cohorts:
        enrollment_result = await session.scalars(
            select(LearningEnrollment).where(
                LearningEnrollment.cohort_id.in_([cohort.id for cohort in cohorts]),
                LearningEnrollment.status == "approved",
            )
        )
        enrollment_rows = list(enrollment_result.all())
    learner_by_enrollment = {item.id: item.learner_id for item in enrollment_rows}

    def unique_learners(rows: list[dict[str, object]]) -> int:
        return len(
            {
                learner_by_enrollment[str(item["enrollment_id"])]
                for item in rows
                if str(item["enrollment_id"]) in learner_by_enrollment
            }
        )

    summary_keys = ("open_interventions", "overdue_interventions")
    totals: dict[str, int] = {}
    for key in summary_keys:
        totals[key] = sum(
            cast(int, cast(dict[str, object], review["summary"])[key]) for review in cohort_reviews
        )
    totals.update(
        {
            "enrolments_reviewed": len(all_enrolment_reviews),
            "unique_learners": len(set(learner_by_enrollment.values())),
            "at_risk_enrolments": len(at_risk_rows),
            "insufficient_data_enrolments": len(insufficient_rows),
            "clear_enrolments": len(clear_rows),
            "at_risk_learners": unique_learners(at_risk_rows),
            "insufficient_data_learners": unique_learners(insufficient_rows),
            "clear_learners": unique_learners(clear_rows),
        }
    )
    return {
        "programme_id": programme.id,
        "programme_title": programme.title,
        "summary": totals,
        "cohorts": [
            {key: review[key] for key in ("cohort_id", "cohort_title", "thresholds", "summary")}
            for review in cohort_reviews
        ],
    }


@router.get("/cohorts/{cohort_id}/interventions")
async def list_cohort_learning_interventions(
    organization_id: str,
    cohort_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """List staff-only intervention notes for one tenant-scoped cohort."""
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Intervention management permission required")
    cohort = await session.scalar(
        select(LearningCohort).where(
            LearningCohort.id == cohort_id,
            LearningCohort.organization_id == organization_id,
        )
    )
    if cohort is None:
        raise HTTPException(404, "Cohort not found")
    rows = await session.execute(
        select(LearningIntervention, LearningEnrollment.learner_id)
        .join(LearningEnrollment, LearningEnrollment.id == LearningIntervention.enrollment_id)
        .where(
            LearningIntervention.organization_id == organization_id,
            LearningIntervention.cohort_id == cohort_id,
        )
        .order_by(
            LearningIntervention.status,
            LearningIntervention.due_date,
            LearningIntervention.created_at.desc(),
        )
        .limit(500)
    )
    return [_intervention_read(item, learner_id) for item, learner_id in rows.all()]


@router.post("/cohorts/{cohort_id}/interventions", status_code=201)
async def create_cohort_learning_intervention(
    organization_id: str,
    cohort_id: str,
    body: InterventionCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Intervention management permission required")
    cohort = await session.scalar(
        select(LearningCohort).where(
            LearningCohort.id == cohort_id,
            LearningCohort.organization_id == organization_id,
        )
    )
    if cohort is None:
        raise HTTPException(404, "Cohort not found")
    enrollment = await session.scalar(
        select(LearningEnrollment)
        .join(LearningCourse, LearningCourse.id == LearningEnrollment.course_id)
        .where(
            LearningEnrollment.id == body.enrollment_id,
            LearningEnrollment.cohort_id == cohort_id,
            LearningEnrollment.status == "approved",
            LearningCourse.organization_id == organization_id,
        )
    )
    if enrollment is None:
        raise HTTPException(404, "Approved learner enrolment not found in this cohort")
    assignee = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == body.assigned_to,
            Membership.status == "active",
        )
    )
    if assignee is None or not await membership_has_any_role(session, assignee, _MANAGE):
        raise HTTPException(422, "Owner must be an active programme manager or administrator")
    note = body.note.strip()
    if not note:
        raise HTTPException(422, "Intervention note cannot be blank")
    intervention = LearningIntervention(
        organization_id=organization_id,
        cohort_id=cohort_id,
        enrollment_id=enrollment.id,
        assigned_to=body.assigned_to,
        created_by=principal.user_id,
        due_date=body.due_date,
        note=note,
        status="open",
    )
    session.add(intervention)
    await session.flush()
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=enrollment.learner_id,
            action="learning.intervention.created",
            changes={
                "intervention_id": intervention.id,
                "cohort_id": cohort_id,
                "enrollment_id": enrollment.id,
                "assigned_to": body.assigned_to,
                "due_date": body.due_date.isoformat() if body.due_date else None,
                "status": "open",
                "note_recorded": True,
            },
        )
    )
    await session.commit()
    await session.refresh(intervention)
    return _intervention_read(intervention, enrollment.learner_id)


@router.patch("/interventions/{intervention_id}")
async def update_learning_intervention(
    organization_id: str,
    intervention_id: str,
    body: InterventionUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Intervention management permission required")
    intervention = await session.scalar(
        select(LearningIntervention)
        .where(
            LearningIntervention.id == intervention_id,
            LearningIntervention.organization_id == organization_id,
        )
        .with_for_update()
    )
    if intervention is None:
        raise HTTPException(404, "Intervention not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "At least one intervention field must be supplied")
    if intervention.status in {"resolved", "cancelled"}:
        raise HTTPException(409, "Resolved or cancelled interventions are immutable")
    if "status" in changes and changes["status"] is None:
        raise HTTPException(422, "Intervention status cannot be null")
    previous_status = intervention.status
    if previous_status in {"resolved", "cancelled"}:
        raise HTTPException(409, "Terminal interventions cannot be edited")
    next_status = changes.get("status", previous_status)
    allowed_transitions = {
        "open": {"in_progress", "resolved", "cancelled"},
        "in_progress": {"resolved", "cancelled"},
        "resolved": set(),
        "cancelled": set(),
    }
    if next_status != previous_status and next_status not in allowed_transitions[previous_status]:
        raise HTTPException(409, "Invalid intervention status transition")
    if "assigned_to" in changes:
        if not changes["assigned_to"]:
            raise HTTPException(422, "Interventions must remain assigned to an active staff owner")
        assignee = await session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == changes["assigned_to"],
                Membership.status == "active",
            )
        )
        if assignee is None or not await membership_has_any_role(session, assignee, _MANAGE):
            raise HTTPException(422, "Owner must be an active programme manager or administrator")
    if "note" in changes:
        if changes["note"] is None or not changes["note"].strip():
            raise HTTPException(422, "Intervention note cannot be blank")
        changes["note"] = changes["note"].strip()
    if "resolution_note" in changes and changes["resolution_note"] is not None:
        changes["resolution_note"] = changes["resolution_note"].strip() or None
    enrollment = await session.scalar(
        select(LearningEnrollment).where(
            LearningEnrollment.id == intervention.enrollment_id,
            LearningEnrollment.cohort_id == intervention.cohort_id,
        )
    )
    if enrollment is None:
        raise HTTPException(404, "Intervention enrolment not found")
    if next_status == "resolved" and next_status != previous_status:
        resolution_note = changes.get("resolution_note")
        if not isinstance(resolution_note, str) or not resolution_note.strip():
            raise HTTPException(422, "A resolution note is required when resolving an intervention")
        changes["resolution_note"] = resolution_note.strip()
        intervention.resolved_at = datetime.now(UTC)
    if next_status != "resolved" and changes.get("resolution_note"):
        raise HTTPException(409, "Resolution notes are only valid when resolving an intervention")
    for field, value in changes.items():
        if field != "status":
            setattr(intervention, field, value)
    intervention.status = next_status
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=enrollment.learner_id,
            action=(
                "learning.intervention.resolved"
                if next_status == "resolved"
                else "learning.intervention.cancelled"
                if next_status == "cancelled"
                else "learning.intervention.updated"
            ),
            changes={
                "intervention_id": intervention.id,
                "fields": sorted(changes),
                "status": {"before": previous_status, "after": next_status},
                "assigned_to": intervention.assigned_to,
                "due_date": intervention.due_date.isoformat() if intervention.due_date else None,
                "note_changed": "note" in changes,
                "resolution_note_changed": "resolution_note" in changes,
            },
        )
    )
    await session.commit()
    await session.refresh(intervention)
    return _intervention_read(intervention, enrollment.learner_id)
