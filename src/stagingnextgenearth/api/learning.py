"""Tenant-scoped learning management workflows."""

import csv
import io
import secrets
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    LearningAssessment,
    LearningAssessmentAttempt,
    LearningAssessmentEvaluation,
    LearningAttendance,
    LearningCertificate,
    LearningCourse,
    LearningEnrollment,
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
    "admin", "founder", "executive", "programme_manager", "researcher",
    "youth_volunteer", "employee", "institutional_partner", "learner",
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


class AssessmentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    assessment_type: Literal["quiz", "assignment", "evaluation"]
    instructions: str = Field(min_length=1, max_length=10000)
    configuration: dict[str, object] = Field(default_factory=dict)
    pass_mark: int = Field(default=50, ge=0, le=100)
    due_at: datetime | None = None


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
    item = await session.scalar(select(LearningCourse).where(
        LearningCourse.id == course_id, LearningCourse.organization_id == org_id
    ))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return item


async def _enrollment(session: AsyncSession, course_id: str, learner_id: str) -> LearningEnrollment:
    item = await session.scalar(select(LearningEnrollment).where(
        LearningEnrollment.course_id == course_id, LearningEnrollment.learner_id == learner_id
    ))
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
    organization_id: str, body: CourseCreate,
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
        organization_id=organization_id, programme_id=body.programme_id,
        title=body.title.strip(), slug=body.slug,
        description=body.description, category=body.category, delivery_mode=body.delivery_mode,
        status="draft", created_by=principal.user_id,
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


@router.post("/courses/{course_id}/publish", response_model=CourseRead)
async def publish_course(
    organization_id: str, course_id: str,
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
    organization_id: str, course_id: str, body: ModuleCreate,
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
    return {"id": module.id, "course_id": module.course_id, "title": module.title,
            "position": module.position}


@router.post("/modules/{module_id}/lessons", status_code=201)
async def create_lesson(
    organization_id: str, module_id: str, body: LessonCreate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Course management permission required")
    module = await session.scalar(select(LearningModule).join(LearningCourse).where(
        LearningModule.id == module_id, LearningCourse.organization_id == organization_id
    ))
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
    return {"id": lesson.id, "module_id": lesson.module_id, "title": lesson.title,
            "content_type": lesson.content_type, "position": lesson.position}


@router.post("/courses/{course_id}/enrollments", status_code=201)
async def apply_for_course(
    organization_id: str, course_id: str,
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
        course_id=course_id, learner_id=principal.user_id,
        status="applied", progress_percent=0,
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
        select(LearningEnrollment, LearningCourse.title, LearningCourse.slug)
        .join(LearningCourse, LearningCourse.id == LearningEnrollment.course_id)
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
            "status": enrollment.status,
            "progress_percent": enrollment.progress_percent,
            "applied_at": enrollment.applied_at,
        }
        for enrollment, title, slug in rows.all()
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
    rows = await session.scalars(
        select(LearningEnrollment)
        .where(LearningEnrollment.course_id == course_id)
        .order_by(LearningEnrollment.applied_at.desc())
        .limit(500)
    )
    return [
        {
            "id": row.id,
            "learner_id": row.learner_id,
            "status": row.status,
            "progress_percent": row.progress_percent,
            "applied_at": row.applied_at,
            "reviewed_at": row.reviewed_at,
        }
        for row in rows.all()
    ]


@router.post("/courses/{course_id}/enrollments/{learner_id}/decision")
async def decide_enrollment(
    organization_id: str, course_id: str, learner_id: str, body: EnrollmentDecision,
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
            session.add(
                Membership(
                    organization_id=organization_id,
                    user_id=learner_id,
                    role="learner",
                    status="active",
                )
            )
        elif (
            existing_membership.status != "active"
            or not await membership_has_any_role(session, existing_membership, _LEARN)
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
        }
        for row in rows.all()
    ]


@router.post("/courses/{course_id}/assessments", status_code=201)
async def create_assessment(
    organization_id: str, course_id: str, body: AssessmentCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Assessment management permission required")
    await _course(session, organization_id, course_id)
    assessment = LearningAssessment(course_id=course_id, created_by=principal.user_id,
                                    **body.model_dump())
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return {"id": assessment.id, "title": assessment.title,
            "assessment_type": assessment.assessment_type, "pass_mark": assessment.pass_mark}


@router.post("/assessments/{assessment_id}/submissions", status_code=201)
async def submit_assessment(
    organization_id: str, assessment_id: str, body: SubmissionCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _LEARN):
        raise HTTPException(403, "Learner access required")
    assessment = await session.scalar(select(LearningAssessment).join(LearningCourse).where(
        LearningAssessment.id == assessment_id,
        LearningCourse.organization_id == organization_id,
        LearningCourse.status == "published",
    ))
    if assessment is None:
        raise HTTPException(404, "Assessment not found")
    enrollment = await _enrollment(session, assessment.course_id, principal.user_id)
    if enrollment.status != "approved":
        raise HTTPException(403, "An approved enrollment is required")
    if assessment.due_at is not None:
        due_at = assessment.due_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if datetime.now(UTC) > due_at:
            raise HTTPException(409, "The assessment submission deadline has passed")
    attempt = LearningAssessmentAttempt(assessment_id=assessment_id,
                                        learner_id=principal.user_id,
                                        submission=body.submission)
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return {"id": attempt.id, "submitted_at": attempt.submitted_at, "status": "submitted"}


@router.post("/submissions/{attempt_id}/evaluate")
async def evaluate_submission(
    organization_id: str, attempt_id: str, body: Evaluation,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Evaluation permission required")
    attempt = await session.scalar(select(LearningAssessmentAttempt).join(
        LearningAssessment).join(LearningCourse).where(
            LearningAssessmentAttempt.id == attempt_id,
            LearningCourse.organization_id == organization_id,
        ))
    if attempt is None:
        raise HTTPException(404, "Submission not found")
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
    evaluation_rows = await session.scalars(
        select(LearningAssessmentEvaluation)
        .where(LearningAssessmentEvaluation.attempt_id.in_(attempt_ids))
        .order_by(
            LearningAssessmentEvaluation.evaluated_at,
            LearningAssessmentEvaluation.id,
        )
    ) if attempt_ids else []
    history_by_attempt: dict[str, list[dict[str, object]]] = {}
    for evaluation in evaluation_rows:
        history_by_attempt.setdefault(evaluation.attempt_id, []).append({
            "id": evaluation.id,
            "score": evaluation.score,
            "feedback": evaluation.feedback,
            "previous_score": evaluation.previous_score,
            "previous_feedback": evaluation.previous_feedback,
            "evaluated_by": evaluation.evaluated_by,
            "evaluated_at": evaluation.evaluated_at,
        })
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
        writer.writerow([
            "'" + value if value.startswith(("=", "+", "-", "@")) else value
            for value in values
        ])
    return Response(
        content="\\ufeff" + output.getvalue(),
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
    organization_id: str, course_id: str, body: MentorAssign,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Mentorship assignment permission required")
    await _course(session, organization_id, course_id)
    mentor_membership = await session.scalar(select(Membership).where(
        Membership.organization_id == organization_id,
        Membership.user_id == body.mentor_id,
        Membership.status == "active",
    ))
    mentee_membership = await session.scalar(select(Membership.id).where(
        Membership.organization_id == organization_id, Membership.user_id == body.mentee_id,
        Membership.status == "active",
    ))
    eligible_mentor = (
        mentor_membership is not None
        and await membership_has_any_role(session, mentor_membership, _MANAGE | {"researcher"})
    )
    if not eligible_mentor or mentee_membership is None or body.mentor_id == body.mentee_id:
        raise HTTPException(
            422,
            "Mentor and mentee must be distinct active members; "
            "the mentor must hold an eligible role",
        )
    assignment = LearningMentorship(course_id=course_id, mentor_id=body.mentor_id,
        mentee_id=body.mentee_id, notes=body.notes, assigned_by=principal.user_id, status="active")
    session.add(assignment)
    try:
        await session.commit()
        await session.refresh(assignment)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "This mentorship assignment already exists") from exc
    return {"id": assignment.id, "mentor_id": assignment.mentor_id,
            "mentee_id": assignment.mentee_id, "status": assignment.status}


@router.patch("/courses/{course_id}/mentorships/{mentorship_id}/status")
async def update_mentorship_status(
    organization_id: str, course_id: str, mentorship_id: str, body: MentorshipStatusUpdate,
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
    session.add(OrganizationAuditEvent(
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
    ))
    await session.commit()
    return {"id": assignment.id, "status": assignment.status}


@router.post("/courses/{course_id}/attendance/bulk", status_code=201)
async def record_bulk_attendance(
    organization_id: str, course_id: str, body: AttendanceBulkCreate,
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
    organization_id: str, course_id: str, body: AttendanceCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Attendance recording permission required")
    await _course(session, organization_id, course_id)
    enrolled = await session.scalar(select(LearningEnrollment.id).where(
        LearningEnrollment.course_id == course_id, LearningEnrollment.learner_id == body.learner_id,
        LearningEnrollment.status.in_({"approved", "completed"}),
    ))
    if enrolled is None:
        raise HTTPException(422, "Attendance requires an approved learner")
    record = LearningAttendance(course_id=course_id, recorded_by=principal.user_id,
                                 **body.model_dump())
    session.add(record)
    try:
        await session.commit()
        await session.refresh(record)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Attendance for this learner and session already exists") from exc
    return {"id": record.id, "learner_id": record.learner_id,
            "attendance_status": record.attendance_status}


@router.post("/courses/{course_id}/resources", status_code=201)
async def add_resource(
    organization_id: str, course_id: str, body: ResourceCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if not await membership_has_any_role(session, membership, _MANAGE):
        raise HTTPException(403, "Learning resource management permission required")
    await _course(session, organization_id, course_id)
    if body.lesson_id is not None:
        lesson = await session.scalar(select(LearningLesson).join(LearningModule).join(
            LearningCourse).where(LearningLesson.id == body.lesson_id,
                                  LearningCourse.id == course_id,
                                  LearningCourse.organization_id == organization_id))
        if lesson is None:
            raise HTTPException(404, "Lesson not found in this course")
    if body.resource_type == "link" and not body.resource_url:
        raise HTTPException(422, "Link resources require resource_url")
    if body.resource_type != "link" and not body.resource_url and not body.storage_reference:
        raise HTTPException(422, "Provide a resource URL or private storage reference")
    resource = LearningResource(course_id=course_id, uploaded_by=principal.user_id,
                                **body.model_dump())
    session.add(resource)
    await session.commit()
    await session.refresh(resource)
    return {"id": resource.id, "title": resource.title,
            "resource_type": resource.resource_type, "lesson_id": resource.lesson_id}


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
    course_id = (await session.scalar(
        select(LearningModule.course_id).where(LearningModule.id == lesson.module_id)
    )) or ""
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
        select(LearningAssessment).where(
            LearningAssessment.course_id == enrollment.course_id
        )
    )
    assessments = assessment_rows.all()
    attempts = await session.scalars(
        select(LearningAssessmentAttempt).join(LearningAssessment).where(
            LearningAssessment.course_id == enrollment.course_id,
            LearningAssessmentAttempt.learner_id == principal.user_id,
        )
    )
    pass_marks = {item.id: item.pass_mark for item in assessments}
    passed_assessments = {
        attempt.assessment_id
        for attempt in attempts.all()
        if attempt.score is not None
        and attempt.score >= pass_marks.get(attempt.assessment_id, 101)
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
            select(LearningCertificate).where(
                LearningCertificate.enrollment_id == enrollment.id
            )
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


@router.get("/certificates/verify/{verification_code}")
async def verify_certificate(
    organization_id: str, verification_code: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    row = await session.scalar(select(LearningCertificate).join(LearningEnrollment).join(
        LearningCourse).where(
            LearningCertificate.verification_code == verification_code,
            LearningCourse.organization_id == organization_id,
        ))
    if row is None:
        raise HTTPException(404, "Certificate not found")
    enrollment = await session.get(LearningEnrollment, row.enrollment_id)
    if enrollment is None:
        raise HTTPException(404, "Certificate enrollment not found")
    course = await _course(session, organization_id, enrollment.course_id)
    return {"valid": row.status == "valid", "certificate_number": row.certificate_number,
            "course_title": course.title, "issued_at": row.issued_at,
            "status": row.status}


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
        select(LearningModule).where(LearningModule.course_id == course_id)
        .order_by(LearningModule.position)
    )
    module_rows = modules.all()
    result: list[dict[str, object]] = []
    for module in module_rows:
        lessons = await session.scalars(
            select(LearningLesson).where(LearningLesson.module_id == module.id)
            .order_by(LearningLesson.position)
        )
        result.append({
            "id": module.id,
            "title": module.title,
            "description": module.description,
            "position": module.position,
            "lessons": [{
                "id": lesson.id,
                "title": lesson.title,
                "content_type": lesson.content_type,
                "content": lesson.content,
                "resource_url": lesson.resource_url,
                "duration_minutes": lesson.duration_minutes,
                "position": lesson.position,
            } for lesson in lessons.all()],
        })
    return {"course_id": course.id, "title": course.title, "modules": result}


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
        "completed_lesson_ids": list(completed.all()),
        "assessments": [{
            "assessment_id": row.assessment_id,
            "score": row.score,
            "feedback": row.feedback,
            "evaluated_at": row.evaluated_at,
        } for row in attempts],
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
        select(LearningResource).where(LearningResource.course_id == course_id)
        .order_by(LearningResource.title).limit(200)
    )
    return [{
        "id": item.id,
        "lesson_id": item.lesson_id,
        "title": item.title,
        "resource_type": item.resource_type,
        "description": item.description,
        "resource_url": item.resource_url,
    } for item in resources.all()]


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
        await course_progress(organization_id, course.id, membership, session)
        for course in courses
    ]
    learner_count = sum(int(report["learners"]) for report in course_reports)
    weighted_progress = sum(
        float(report["average_progress"]) * int(report["learners"])
        for report in course_reports
    )
    totals = {
        "learners": learner_count,
        "approved": sum(int(report["approved"]) for report in course_reports),
        "completed": sum(int(report["completed"]) for report in course_reports),
        "attendance_records": sum(
            int(report["attendance_records"]) for report in course_reports
        ),
        "attendance_sessions": sum(
            int(report["attendance_sessions"]) for report in course_reports
        ),
        "mentorship_assignments": sum(
            int(report["mentorship_assignments"]) for report in course_reports
        ),
        "active_mentorships": sum(
            int(report["active_mentorships"]) for report in course_reports
        ),
        "assessment_submissions": sum(
            int(report["assessment_submissions"]) for report in course_reports
        ),
        "evaluated_submissions": sum(
            int(report["evaluated_submissions"]) for report in course_reports
        ),
        "pending_evaluations": sum(
            int(report["pending_evaluations"]) for report in course_reports
        ),
    }
    return {
        "programme_id": programme.id,
        "programme_title": programme.title,
        "course_count": len(courses),
        "average_progress": round(weighted_progress / learner_count, 1)
        if learner_count else 0.0,
        "totals": totals,
        "courses": [
            {
                "course_id": course.id,
                "title": course.title,
                "status": course.status,
                **report,
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
    report = await programme_outcomes(
        organization_id, programme_id, membership, session
    )

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
    writer.writerow([
        safe_cell("programme"),
        safe_cell("average_progress"),
        safe_cell(report["average_progress"]),
    ])
    writer.writerow([])
    writer.writerow([
        "course_id", "course_title", "status", "learners", "approved",
        "completed", "average_progress", "attendance_records",
        "attendance_sessions", "mentorship_assignments", "active_mentorships",
        "assessment_submissions", "evaluated_submissions", "pending_evaluations",
    ])
    courses = report["courses"]
    if isinstance(courses, list):
        for course in courses:
            if isinstance(course, dict):
                writer.writerow([
                    safe_cell(course.get("course_id")),
                    safe_cell(course.get("title")),
                    safe_cell(course.get("status")),
                    *[
                        safe_cell(course.get(key))
                        for key in (
                            "learners", "approved", "completed", "average_progress",
                            "attendance_records", "attendance_sessions",
                            "mentorship_assignments", "active_mentorships",
                            "assessment_submissions", "evaluated_submissions",
                            "pending_evaluations",
                        )
                    ],
                ])
    filename = f"programme-{programme_id}-outcomes.csv"
    return Response(
        content="\\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/courses/{course_id}/progress")
async def course_progress(
    organization_id: str, course_id: str,
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
        ) if enrollments else 0.0,
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
            await programme_outcomes(
                organization_id, programme.id, membership, session
            ),
        )
        for programme in programme_rows.all()
    ]
    metric_keys = (
        "learners",
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
    totals = {
        key: sum(int(report["totals"][key]) for report in reports)
        for key in metric_keys
    }
    learner_count = totals["learners"]
    weighted_progress = sum(
        float(report["average_progress"]) * int(report["totals"]["learners"])
        for report in reports
    )
    return {
        "organization_id": organization_id,
        "programmes_total": len(reports),
        "courses_total": sum(int(report["course_count"]) for report in reports),
        "average_progress": round(weighted_progress / learner_count, 1)
        if learner_count else 0.0,
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
    writer.writerow([
        "programme_id", "programme_title", "course_count", "average_progress",
        "learners", "approved", "completed", "attendance_records",
        "attendance_sessions", "mentorship_assignments", "active_mentorships",
        "assessment_submissions", "evaluated_submissions", "pending_evaluations",
    ])
    programmes = report["programmes"]
    if isinstance(programmes, list):
        for programme in programmes:
            if not isinstance(programme, dict):
                continue
            programme_totals = programme.get("totals", {})
            writer.writerow([
                safe_cell(programme.get("programme_id")),
                safe_cell(programme.get("programme_title")),
                safe_cell(programme.get("course_count")),
                safe_cell(programme.get("average_progress")),
                *[
                    safe_cell(programme_totals.get(key))
                    for key in (
                        "learners", "approved", "completed", "attendance_records",
                        "attendance_sessions", "mentorship_assignments",
                        "active_mentorships", "assessment_submissions",
                        "evaluated_submissions", "pending_evaluations",
                    )
                ],
            ])
    return Response(
        content=chr(0xFEFF) + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="organisation-learning-outcomes.csv"'
        },
    )
