

class LearningCourse(Base):
    """Organisation-owned course published to learner portals."""

    __tablename__ = "learning_courses"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_learning_course_org_slug"),
        CheckConstraint("status IN ('draft', 'published', 'archived')",
                        name="ck_learning_course_status"),
        Index("ix_learning_courses_org_status", "organization_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="blended")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearningModule(Base):
    """Ordered course module."""

    __tablename__ = "learning_modules"
    __table_args__ = (
        UniqueConstraint("course_id", "position", name="uq_learning_module_position"),
        Index("ix_learning_modules_course", "course_id", "position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningLesson(Base):
    """Ordered lesson with a resource reference rather than public object credentials."""

    __tablename__ = "learning_lessons"
    __table_args__ = (
        UniqueConstraint("module_id", "position", name="uq_learning_lesson_position"),
        CheckConstraint("content_type IN ('text', 'video', 'document', 'link', 'workshop')",
                        name="ck_learning_lesson_content_type"),
        Index("ix_learning_lessons_module", "module_id", "position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    module_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_modules.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    position: Mapped[int] = mapped_column(nullable=False)


class LearningEnrollment(Base):
    """Learner application and approved course registration."""

    __tablename__ = "learning_enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "learner_id", name="uq_learning_enrollment_learner"),
        CheckConstraint("status IN ('applied', 'approved', 'rejected', 'completed', 'withdrawn')",
                        name="ck_learning_enrollment_status"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100",
                        name="ck_learning_enrollment_progress"),
        Index("ix_learning_enrollments_course_status", "course_id", "status"),
        Index("ix_learning_enrollments_learner_status", "learner_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="applied")
    progress_percent: Mapped[int] = mapped_column(nullable=False, default=0)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningAssessment(Base):
    """Course assessment definition; configuration contains rubric or quiz metadata."""

    __tablename__ = "learning_assessments"
    __table_args__ = (
        CheckConstraint("assessment_type IN ('quiz', 'assignment', 'evaluation')",
                        name="ck_learning_assessment_type"),
        CheckConstraint("pass_mark >= 0 AND pass_mark <= 100",
                        name="ck_learning_assessment_pass_mark"),
        Index("ix_learning_assessments_course", "course_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(16), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    pass_mark: Mapped[int] = mapped_column(nullable=False, default=50)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class LearningAssessmentAttempt(Base):
    """Learner submission and staff evaluation."""

    __tablename__ = "learning_assessment_attempts"
    __table_args__ = (
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)",
                        name="ck_learning_attempt_score"),
        Index("ix_learning_attempts_assessment_learner", "assessment_id", "learner_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_assessments.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    submission: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    score: Mapped[int | None] = mapped_column(nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    evaluated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningMentorship(Base):
    """Course-scoped mentor assignment."""

    __tablename__ = "learning_mentorships"
    __table_args__ = (
        UniqueConstraint("course_id", "mentor_id", "mentee_id", name="uq_learning_mentorship"),
        CheckConstraint("status IN ('active', 'completed', 'ended')",
                        name="ck_learning_mentorship_status"),
        Index("ix_learning_mentorship_mentor", "mentor_id", "status"),
        Index("ix_learning_mentorship_mentee", "mentee_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    mentor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    mentee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningAttendance(Base):
    """Workshop attendance record."""

    __tablename__ = "learning_attendance"
    __table_args__ = (
        UniqueConstraint("course_id", "session_key", "learner_id", name="uq_learning_attendance"),
        CheckConstraint("attendance_status IN ('present', 'late', 'excused', 'absent')",
                        name="ck_learning_attendance_status"),
        Index("ix_learning_attendance_course_date", "course_id", "session_date"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    session_key: Mapped[str] = mapped_column(String(100), nullable=False)
    session_title: Mapped[str] = mapped_column(String(240), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attendance_status: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningResource(Base):
    """Course or lesson resource metadata; private file access stays in storage grants."""

    __tablename__ = "learning_resources"
    __table_args__ = (
        CheckConstraint("resource_type IN ('document', 'video', 'research', 'link')",
                        name="ck_learning_resource_type"),
        Index("ix_learning_resources_course", "course_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("learning_lessons.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    storage_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class LearningCertificate(Base):
    """Revocable, publicly verifiable course completion credential."""

    __tablename__ = "learning_certificates"
    __table_args__ = (
        UniqueConstraint("enrollment_id", name="uq_learning_certificate_enrollment"),
        UniqueConstraint("certificate_number", name="uq_learning_certificate_number"),
        UniqueConstraint("verification_code", name="uq_learning_certificate_verification"),
        CheckConstraint("status IN ('valid', 'revoked')", name="ck_learning_certificate_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_enrollments.id", ondelete="CASCADE"), nullable=False
    )
    certificate_number: Mapped[str] = mapped_column(String(48), nullable=False)
    verification_code: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="valid")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
