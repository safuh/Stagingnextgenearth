"""Tenant-scoped learning management workflows."""

import secrets
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    LearningAssessment,
    LearningAssessmentAttempt,
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
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(prefix="/organizations/{organization_id}/learning", tags=["learning"])
_MANAGE = {"admin", "programme_manager"}
_LEARN = {"admin", "programme_manager", "researcher", "youth_volunteer", "institutional_partner"}


class CourseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    slug: str = Field(min_length=2, max_length=140, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1, max_length=12000)
    category: str | None = Field(default=None, max_length=100)
    delivery_mode: Literal["online", "in_person", "blended"] = "blended"


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
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


class AttendanceCreate(BaseModel):
    session_key: str = Field(min_length=1, max_length=100)
    session_title: str = Field(min_length=2, max_length=240)
    session_date: date
    learner_id: str
    attendance_status: Literal["present", "late", "excused", "absent"]


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


@router.post("/courses", response_model=CourseRead, status_code=201)
async def create_course(
    organization_id: str, body: CourseCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CourseRead:
    if membership.role not in _MANAGE:
        raise HTTPException(403, "Course management permission required")
    course = LearningCourse(
        organization_id=organization_id, title=body.title.strip(), slug=body.slug,
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
    if not include_drafts or membership.role not in _MANAGE:
        statement = statement.where(LearningCourse.status == "published")
    result = await session.scalars(statement.order_by(LearningCourse.title).limit(200))
    return [CourseRead.model_validate(row) for row in result.all()]


@router.post("/courses/{course_id}/publish", response_model=CourseRead)
async def publish_course(
    organization_id: str, course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CourseRead:
    if membership.role not in _MANAGE:
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
    if membership.role not in _MANAGE:
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
    if membership.role not in _MANAGE:
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
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if membership.role not in _LEARN:
        raise HTTPException(403, "Learner access required")
    course = await _course(session, organization_id, course_id)
    if course.status != "published":
        raise HTTPException(409, "Applications are open only for published courses")
    enrollment = LearningEnrollment(course_id=course_id, learner_id=principal.user_id,
                                    status="applied", progress_percent=0)
    session.add(enrollment)
    try:
        await session.commit()
        await session.refresh(enrollment)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "An application already exists for this course") from exc
    return {"id": enrollment.id, "status": enrollment.status, "applied_at": enrollment.applied_at}


@router.post("/courses/{course_id}/enrollments/{learner_id}/decision")
async def decide_enrollment(
    organization_id: str, course_id: str, learner_id: str, body: EnrollmentDecision,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if membership.role not in _MANAGE:
        raise HTTPException(403, "Enrollment approval permission required")
    await _course(session, organization_id, course_id)
    enrollment = await _enrollment(session, course_id, learner_id)
    if enrollment.status != "applied":
        raise HTTPException(409, "Only pending applications can be decided")
    enrollment.status = body.decision
    enrollment.reviewed_by = principal.user_id
    enrollment.reviewed_at = datetime.now(UTC)
    await session.commit()
    return {"id": enrollment.id, "status": enrollment.status}


@router.post("/courses/{course_id}/assessments", status_code=201)
async def create_assessment(
    organization_id: str, course_id: str, body: AssessmentCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if membership.role not in _MANAGE:
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
    if membership.role not in _LEARN:
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
    if membership.role not in _MANAGE:
        raise HTTPException(403, "Evaluation permission required")
    attempt = await session.scalar(select(LearningAssessmentAttempt).join(
        LearningAssessment).join(LearningCourse).where(
            LearningAssessmentAttempt.id == attempt_id,
            LearningCourse.organization_id == organization_id,
        ))
    if attempt is None:
        raise HTTPException(404, "Submission not found")
    attempt.score = body.score
    attempt.feedback = body.feedback
    attempt.evaluated_by = principal.user_id
    attempt.evaluated_at = datetime.now(UTC)
    await session.commit()
    return {"id": attempt.id, "score": attempt.score, "evaluated_at": attempt.evaluated_at}


@router.post("/courses/{course_id}/mentorships", status_code=201)
async def assign_mentor(
    organization_id: str, course_id: str, body: MentorAssign,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if membership.role not in _MANAGE:
        raise HTTPException(403, "Mentorship assignment permission required")
    await _course(session, organization_id, course_id)
    mentor_membership = await session.scalar(select(Membership.id).where(
        Membership.organization_id == organization_id, Membership.user_id == body.mentor_id,
        Membership.status == "active", Membership.role.in_(_MANAGE | {"researcher"}),
    ))
    mentee_membership = await session.scalar(select(Membership.id).where(
        Membership.organization_id == organization_id, Membership.user_id == body.mentee_id,
        Membership.status == "active",
    ))
    if mentor_membership is None or mentee_membership is None or body.mentor_id == body.mentee_id:
        raise HTTPException(422, "Mentor and mentee must be distinct active organisation members")
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


@router.post("/courses/{course_id}/attendance", status_code=201)
async def record_attendance(
    organization_id: str, course_id: str, body: AttendanceCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if membership.role not in _MANAGE:
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
    if membership.role not in _MANAGE:
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
    enrollment = await _enrollment(
        session,
        (await session.scalar(
            select(LearningModule.course_id).where(LearningModule.id == lesson.module_id)
        )) or "",
        principal.user_id,
    )
    if enrollment.status not in {"approved", "completed"}:
        raise HTTPException(403, "An approved enrollment is required")

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
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Return ordered modules and lessons without exposing draft content to learners."""
    course = await _course(session, organization_id, course_id)
    if course.status != "published" and membership.role not in _MANAGE:
        raise HTTPException(404, "Course not found")
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
    if membership.role not in _LEARN:
        raise HTTPException(403, "Learner access required")
    course = await _course(session, organization_id, course_id)
    if course.status != "published":
        raise HTTPException(404, "Course not found")
    enrollment = await _enrollment(session, course_id, principal.user_id)
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
    if course.status != "published" and membership.role not in _MANAGE:
        raise HTTPException(404, "Course not found")
    if membership.role not in _MANAGE:
        enrollment = await _enrollment(session, course_id, principal.user_id)
        if enrollment.status not in {"approved", "completed"}:
            raise HTTPException(403, "An approved enrollment is required")
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
    if membership.role not in _MANAGE:
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


@router.get("/courses/{course_id}/progress")
async def course_progress(
    organization_id: str, course_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if membership.role not in _MANAGE:
        raise HTTPException(403, "Course reporting permission required")
    await _course(session, organization_id, course_id)
    rows = await session.scalars(select(LearningEnrollment).where(
        LearningEnrollment.course_id == course_id))
    enrollments = rows.all()
    return {"course_id": course_id, "learners": len(enrollments),
            "approved": sum(x.status in {"approved", "completed"} for x in enrollments),
            "completed": sum(x.status == "completed" for x in enrollments),
            "average_progress": round(sum(x.progress_percent for x in enrollments) /
                                      len(enrollments), 1) if enrollments else 0.0}
