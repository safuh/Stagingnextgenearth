"""End-to-end tests for tenant-scoped learning management."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def _register(client: TestClient, identifier: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"identifier": identifier, "password": "correct horse battery staple"},
    )
    assert response.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"identifier": identifier, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_learning_course_lifecycle_and_certificate_verification(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'learning.db'}"
    engine = create_async_engine(database_url)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare_database())
    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
    )

    with TestClient(create_app(settings)) as client:
        admin_headers = _register(client, "learning-admin@example.org")
        learner_headers = _register(client, "learning-learner@example.org")
        organisation = client.post(
            "/api/organizations",
            headers=admin_headers,
            json={"name": "Learning Lab", "slug": "learning-lab"},
        )
        assert organisation.status_code == 201
        org_id = organisation.json()["id"]
        public_organisation = client.get(
            "/api/public/organizations/learning-lab",
        )
        assert public_organisation.status_code == 200
        assert public_organisation.json() == {
            "id": org_id,
            "name": "Learning Lab",
            "slug": "learning-lab",
        }
        invitation = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=admin_headers,
            json={"identifier": "learning-learner@example.org", "role": "youth_volunteer"},
        )
        assert invitation.status_code == 201
        invited_context = client.get("/api/auth/context", headers=learner_headers)
        assert invited_context.status_code == 200
        assert invited_context.json()["memberships"][0]["status"] == "invited"
        assert invited_context.json()["memberships"][0]["roles"] == ["youth_volunteer"]
        accepted = client.post(
            f"/api/organizations/{org_id}/memberships/{invitation.json()['id']}/accept",
            headers=learner_headers,
        )
        assert accepted.status_code == 200
        own_membership = client.get(
            f"/api/organizations/{org_id}/memberships/me",
            headers=learner_headers,
        )
        assert own_membership.status_code == 200
        assert own_membership.json()["role"] == "youth_volunteer"
        assert own_membership.json()["user_id"]
        staff_directory = client.get(
            f"/api/organizations/{org_id}/memberships/directory",
            headers=admin_headers,
        )
        assert staff_directory.status_code == 200
        assert {item["role"] for item in staff_directory.json()} == {
            "admin",
            "youth_volunteer",
        }
        assert all(set(item) == {"user_id", "role", "roles"} for item in staff_directory.json())
        assert all(item["roles"] == [item["role"]] for item in staff_directory.json())
        learner_directory = client.get(
            f"/api/organizations/{org_id}/memberships/directory",
            headers=learner_headers,
        )
        assert learner_directory.status_code == 403

        programme_response = client.post(
            f"/api/organizations/{org_id}/programmes",
            headers=admin_headers,
            json={
                "title": "Climate Learning Programme",
                "slug": "climate-learning-programme",
                "summary": "Programme containing the learning curriculum.",
            },
        )
        assert programme_response.status_code == 201
        programme_id = programme_response.json()["id"]
        planned_programme = client.post(
            f"/api/organizations/{org_id}/programmes/{programme_id}/status",
            headers=admin_headers,
            json={"status": "planned"},
        )
        assert planned_programme.status_code == 200

        base = f"/api/organizations/{org_id}/learning"
        cohort_response = client.post(
            f"{base}/cohorts",
            headers=admin_headers,
            json={
                "programme_id": programme_id,
                "code": "CLIMATE-INTAKE-01",
                "title": "Climate Action Intake 01",
                "start_date": "2026-11-01",
                "end_date": "2027-03-31",
                "capacity": 2,
            },
        )
        assert cohort_response.status_code == 201
        cohort_id = cohort_response.json()["id"]
        assert cohort_response.json()["status"] == "draft"
        invalid_cohort_dates = client.post(
            f"{base}/cohorts",
            headers=admin_headers,
            json={
                "programme_id": programme_id,
                "code": "BAD-DATES",
                "title": "Invalid date cohort",
                "start_date": "2027-04-01",
                "end_date": "2027-03-01",
            },
        )
        assert invalid_cohort_dates.status_code == 422
        unknown_programme_cohort = client.post(
            f"{base}/cohorts",
            headers=admin_headers,
            json={
                "programme_id": "00000000-0000-0000-0000-000000000000",
                "code": "UNKNOWN-PROGRAMME",
                "title": "Invalid programme cohort",
            },
        )
        assert unknown_programme_cohort.status_code == 404
        denied_cohort_list = client.get(f"{base}/cohorts", headers=learner_headers)
        assert denied_cohort_list.status_code == 403
        opened_cohort = client.patch(
            f"{base}/cohorts/{cohort_id}",
            headers=admin_headers,
            json={"status": "open"},
        )
        assert opened_cohort.status_code == 200
        assert opened_cohort.json()["status"] == "open"
        course_response = client.post(
            f"{base}/courses",
            headers=admin_headers,
            json={
                "title": "Community Climate Action",
                "slug": "community-climate-action",
                "description": "Practical climate literacy and community action.",
                "category": "climate",
                "programme_id": programme_id,
                "delivery_mode": "blended",
            },
        )
        assert course_response.status_code == 201
        course_id = course_response.json()["id"]
        assert course_response.json()["programme_id"] == programme_id

        module = client.post(
            f"{base}/courses/{course_id}/modules",
            headers=admin_headers,
            json={"title": "Climate foundations", "position": 1},
        )
        assert module.status_code == 201
        lesson = client.post(
            f"{base}/modules/{module.json()['id']}/lessons",
            headers=admin_headers,
            json={
                "title": "Local climate risks",
                "content_type": "text",
                "content": "Identify locally observed climate risks.",
                "position": 1,
            },
        )
        assert lesson.status_code == 201

        # Draft curriculum remains editable before publication.
        course_update = client.patch(
            f"{base}/courses/{course_id}",
            headers=admin_headers,
            json={"description": "Updated draft description."},
        )
        assert course_update.status_code == 200
        assert course_update.json()["description"] == "Updated draft description."
        module_update = client.patch(
            f"{base}/courses/{course_id}/modules/{module.json()['id']}",
            headers=admin_headers,
            json={"title": "Climate foundations and local risk"},
        )
        assert module_update.status_code == 200
        assert module_update.json()["title"] == "Climate foundations and local risk"
        lesson_update = client.patch(
            f"{base}/courses/{course_id}/lessons/{lesson.json()['id']}",
            headers=admin_headers,
            json={
                "title": "Assessing local climate risks",
                "duration_minutes": 35,
            },
        )
        assert lesson_update.status_code == 200
        assert lesson_update.json()["title"] == "Assessing local climate risks"
        assert lesson_update.json()["duration_minutes"] == 35


        published = client.post(
            f"{base}/courses/{course_id}/publish",
            headers=admin_headers,
        )
        assert published.status_code == 200
        immutable_course_update = client.patch(
            f"{base}/courses/{course_id}",
            headers=admin_headers,
            json={"description": "This must not mutate published content."},
        )
        assert immutable_course_update.status_code == 409
        immutable_lesson_update = client.patch(
            f"{base}/courses/{course_id}/lessons/{lesson.json()['id']}",
            headers=admin_headers,
            json={"title": "This must not mutate published content."},
        )
        assert immutable_lesson_update.status_code == 409


        # Staff membership alone must not grant access to learner curriculum.
        employee_headers = _register(client, "learning-employee@example.org")
        employee_invitation = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=admin_headers,
            json={"identifier": "learning-employee@example.org", "role": "employee"},
        )
        assert employee_invitation.status_code == 201
        employee_acceptance = client.post(
            f"/api/organizations/{org_id}/memberships/{employee_invitation.json()['id']}/accept",
            headers=employee_headers,
        )
        assert employee_acceptance.status_code == 200
        employee_curriculum = client.get(
            f"{base}/courses/{course_id}/curriculum",
            headers=employee_headers,
        )
        assert employee_curriculum.status_code == 403

        # A public learner can self-register and apply without being pre-invited.
        public_learner_headers = _register(client, "public-learner@example.org")
        public_application = client.post(
            f"{base}/courses/{course_id}/enrollments",
            headers=public_learner_headers,
        )
        assert public_application.status_code == 201
        own_applications = client.get(
            f"{base}/my-enrollments",
            headers=public_learner_headers,
        )
        assert own_applications.status_code == 200
        assert own_applications.json()[0]["course_id"] == course_id
        assert own_applications.json()[0]["status"] == "applied"
        pending_context = client.get("/api/auth/context", headers=public_learner_headers)
        assert pending_context.status_code == 200
        assert pending_context.json()["memberships"] == []
        pending_membership = client.get(
            f"/api/organizations/{org_id}/memberships/me",
            headers=public_learner_headers,
        )
        assert pending_membership.status_code == 404
        pending_curriculum = client.get(
            f"{base}/courses/{course_id}/curriculum",
            headers=public_learner_headers,
        )
        assert pending_curriculum.status_code == 404
        from stagingnextgenearth.auth import TokenService

        public_learner_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "public-learner@example.org",
                "password": "correct horse battery staple",
            },
        )
        public_learner_id = TokenService(settings.jwt_secret_key.get_secret_value()).decode(
            public_learner_login.json()["access_token"], expected_type="access"
        )["sub"]
        public_approval = client.post(
            f"{base}/courses/{course_id}/enrollments/{public_learner_id}/decision",
            headers=admin_headers,
            json={"decision": "approved"},
        )
        assert public_approval.status_code == 200
        public_cohort_assignment = client.post(
            f"{base}/courses/{course_id}/enrollments/{public_learner_id}/cohort",
            headers=admin_headers,
            json={"cohort_id": cohort_id},
        )
        assert public_cohort_assignment.status_code == 200
        public_my_enrollments = client.get(
            f"{base}/my-enrollments",
            headers=public_learner_headers,
        )
        assert public_my_enrollments.status_code == 200
        assert public_my_enrollments.json()[0]["cohort_id"] == cohort_id
        assert public_my_enrollments.json()[0]["cohort_title"] == "Climate Action Intake 01"
        public_membership = client.get(
            f"/api/organizations/{org_id}/memberships/me",
            headers=public_learner_headers,
        )
        assert public_membership.status_code == 200
        assert public_membership.json()["role"] == "learner"
        assert public_membership.json()["roles"] == ["learner"]
        learner_context = client.get("/api/auth/context", headers=public_learner_headers)
        assert learner_context.status_code == 200
        assert learner_context.json()["identifier"] == "public-learner@example.org"
        assert learner_context.json()["memberships"] == [
            {
                "membership_id": public_membership.json()["id"],
                "organization_id": org_id,
                "organization_name": "Learning Lab",
                "organization_slug": "learning-lab",
                "role": "learner",
                "roles": ["learner"],
                "status": "active",
            }
        ]

        public_courses = client.get(
            "/api/public/organizations/learning-lab/courses",
        )
        assert public_courses.status_code == 200
        assert [item["id"] for item in public_courses.json()] == [course_id]
        assert public_courses.json()[0]["programme_id"] == programme_id
        programme_courses = client.get(
            "/api/public/organizations/learning-lab/programmes/climate-learning-programme/courses",
        )
        assert programme_courses.status_code == 200
        assert [item["id"] for item in programme_courses.json()] == [course_id]
        assert all("created_by" not in item for item in public_courses.json())
        assert all("configuration" not in item for item in public_courses.json())

        resource = client.post(
            f"{base}/courses/{course_id}/resources",
            headers=admin_headers,
            json={
                "title": "Climate field guide",
                "resource_type": "research",
                "description": "Reference material for learners.",
                "storage_reference": "private-object-key-should-never-be-returned",
            },
        )
        assert resource.status_code == 201
        application = client.post(
            f"{base}/courses/{course_id}/enrollments",
            headers=learner_headers,
        )
        assert application.status_code == 201
        pending_enrollments = client.get(
            f"{base}/courses/{course_id}/enrollments",
            headers=admin_headers,
        )
        assert pending_enrollments.status_code == 200
        assert pending_enrollments.json()[0]["status"] == "applied"
        learner_enrollment_access = client.get(
            f"{base}/courses/{course_id}/enrollments",
            headers=learner_headers,
        )
        assert learner_enrollment_access.status_code == 403
        from stagingnextgenearth.auth import TokenService

        learner_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "learning-learner@example.org",
                "password": "correct horse battery staple",
            },
        )
        assert learner_login.status_code == 200
        learner_id = TokenService(settings.jwt_secret_key.get_secret_value()).decode(
            learner_login.json()["access_token"], expected_type="access"
        )["sub"]
        decision = client.post(
            f"{base}/courses/{course_id}/enrollments/{learner_id}/decision",
            headers=admin_headers,
            json={"decision": "approved"},
        )
        assert decision.status_code == 200
        learner_cohort_assignment = client.post(
            f"{base}/courses/{course_id}/enrollments/{learner_id}/cohort",
            headers=admin_headers,
            json={"cohort_id": cohort_id},
        )
        assert learner_cohort_assignment.status_code == 200
        cohort_roster = client.get(f"{base}/cohorts", headers=admin_headers)
        assert cohort_roster.status_code == 200
        assert cohort_roster.json()[0]["assigned_count"] == 2
        promoted_membership = client.get(
            f"/api/organizations/{org_id}/memberships/me",
            headers=learner_headers,
        )
        assert promoted_membership.status_code == 200
        assert promoted_membership.json()["role"] == "youth_volunteer"
        assert "learner" in promoted_membership.json()["roles"]
        membership_audit = client.get(
            f"/api/organizations/{org_id}/audit-events",
            headers=admin_headers,
        )
        assert membership_audit.status_code == 200
        learner_role_event = next(
            event
            for event in membership_audit.json()
            if event["action"] == "membership.roles_changed"
            and event["subject_user_id"] == learner_id
        )
        assert learner_role_event["changes"]["reason"] == "course_enrollment_approved"

        curriculum = client.get(f"{base}/courses/{course_id}/curriculum", headers=learner_headers)
        assert curriculum.status_code == 200
        assert curriculum.json()["title"] == "Community Climate Action"
        assert curriculum.json()["description"] == (
            "Updated draft description."
        )
        assert curriculum.json()["modules"][0]["lessons"][0]["title"] == (
            "Assessing local climate risks"
        )

        resources = client.get(f"{base}/courses/{course_id}/resources", headers=learner_headers)
        assert resources.status_code == 200
        assert resources.json()[0]["title"] == "Climate field guide"
        assert "storage_reference" not in resources.json()[0]

        assessment = client.post(
            f"{base}/courses/{course_id}/assessments",
            headers=admin_headers,
            json={
                "title": "Climate foundations quiz",
                "assessment_type": "quiz",
                "instructions": "Submit your responses.",
                "pass_mark": 60,
            },
        )
        assert assessment.status_code == 201
        submission = client.post(
            f"{base}/assessments/{assessment.json()['id']}/submissions",
            headers=learner_headers,
            json={"submission": {"answers": ["risk", "adaptation"]}},
        )
        assert submission.status_code == 201
        evaluated = client.post(
            f"{base}/submissions/{submission.json()['id']}/evaluate",
            headers=admin_headers,
            json={"score": 85, "feedback": "Good application of the concepts."},
        )
        assert evaluated.status_code == 200
        first_evaluation_id = evaluated.json()["evaluation_id"]
        revised_evaluation = client.post(
            f"{base}/submissions/{submission.json()['id']}/evaluate",
            headers=admin_headers,
            json={"score": 92, "feedback": "Excellent improvement."},
        )
        assert revised_evaluation.status_code == 200
        evaluation_history = client.get(
            f"{base}/submissions/{submission.json()['id']}/evaluations",
            headers=admin_headers,
        )
        assert evaluation_history.status_code == 200
        assert len(evaluation_history.json()) == 2
        assert evaluation_history.json()[0]["id"] == first_evaluation_id
        assert evaluation_history.json()[1]["score"] == 92
        assert evaluation_history.json()[1]["previous_score"] == 85
        assert evaluation_history.json()[1]["previous_feedback"] == (
            "Good application of the concepts."
        )
        learner_evaluation_history = client.get(
            f"{base}/submissions/{submission.json()['id']}/evaluations",
            headers=learner_headers,
        )
        assert learner_evaluation_history.status_code == 403
        assessments = client.get(
            f"{base}/courses/{course_id}/assessments",
            headers=learner_headers,
        )
        assert assessments.status_code == 200
        assert assessments.json()[0]["title"] == "Climate foundations quiz"
        assert "configuration" not in assessments.json()[0]
        staff_submissions = client.get(
            f"{base}/courses/{course_id}/submissions",
            headers=admin_headers,
        )
        assert staff_submissions.status_code == 200
        assert staff_submissions.json()[0]["id"] == submission.json()["id"]
        assert staff_submissions.json()[0]["submission"]["answers"] == ["risk", "adaptation"]

        automated_quiz = client.post(
            f"{base}/courses/{course_id}/assessments",
            headers=admin_headers,
            json={
                "title": "Climate decision-making quiz",
                "assessment_type": "quiz",
                "instructions": "Choose the best answer for each question.",
                "pass_mark": 60,
                "configuration": {
                    "questions": [
                        {
                            "id": "q1",
                            "prompt": "Which action reduces flood exposure?",
                            "options": [
                                {"id": "a", "text": "Restore wetlands"},
                                {"id": "b", "text": "Build on floodplains"},
                            ],
                            "correct_option_id": "a",
                            "points": 2,
                        },
                        {
                            "id": "q2",
                            "prompt": "What supports climate adaptation?",
                            "options": [
                                {"id": "a", "text": "Risk-informed planning"},
                                {"id": "b", "text": "Ignoring local evidence"},
                            ],
                            "correct_option_id": "a",
                            "points": 1,
                        },
                    ]
                },
            },
        )
        assert automated_quiz.status_code == 201
        quiz_id = automated_quiz.json()["id"]
        automated_catalog = client.get(
            f"{base}/courses/{course_id}/assessments", headers=learner_headers
        )
        quiz_summary = next(item for item in automated_catalog.json() if item["id"] == quiz_id)
        assert quiz_summary["automated"] is True
        assert "configuration" not in quiz_summary
        quiz = client.get(f"{base}/assessments/{quiz_id}/quiz", headers=learner_headers)
        assert quiz.status_code == 200
        assert len(quiz.json()["questions"]) == 2
        assert "correct_option_id" not in quiz.text
        assert (
            client.post(
                f"{base}/assessments/{quiz_id}/submissions",
                headers=learner_headers,
                json={"submission": {"answers": {"q1": "a", "q2": "a"}}},
            ).status_code
            == 409
        )
        incomplete_quiz = client.post(
            f"{base}/assessments/{quiz_id}/quiz-attempts",
            headers=learner_headers,
            json={"answers": {"q1": "a"}},
        )
        assert incomplete_quiz.status_code == 422
        invalid_option = client.post(
            f"{base}/assessments/{quiz_id}/quiz-attempts",
            headers=learner_headers,
            json={"answers": {"q1": "unknown", "q2": "a"}},
        )
        assert invalid_option.status_code == 422
        quiz_result = client.post(
            f"{base}/assessments/{quiz_id}/quiz-attempts",
            headers=learner_headers,
            json={"answers": {"q1": "a", "q2": "b"}},
        )
        assert quiz_result.status_code == 201
        assert quiz_result.json()["score"] == 67
        assert quiz_result.json()["passed"] is True
        assert quiz_result.json()["earned_points"] == 2
        assert quiz_result.json()["total_points"] == 3
        assert (
            client.post(
                f"{base}/submissions/{quiz_result.json()['id']}/evaluate",
                headers=admin_headers,
                json={"score": 100, "feedback": "Attempted override."},
            ).status_code
            == 409
        )

        learner_submission_access = client.get(
            f"{base}/courses/{course_id}/submissions",
            headers=learner_headers,
        )
        assert learner_submission_access.status_code == 403

        learner_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "learning-learner@example.org",
                "password": "correct horse battery staple",
            },
        )
        assert learner_login.status_code == 200
        from stagingnextgenearth.auth import TokenService

        learner_id = TokenService(settings.jwt_secret_key.get_secret_value()).decode(
            learner_login.json()["access_token"], expected_type="access"
        )["sub"]
        # The former caller-supplied percentage endpoint is no longer available.
        forged_progress = client.post(
            f"{base}/courses/{course_id}/enrollments/{learner_id}/progress",
            headers=learner_headers,
            params={"progress_percent": 100},
        )
        assert forged_progress.status_code == 404

        # Completion is recorded against an actual lesson and evaluated assessment.
        premature = client.post(
            f"{base}/lessons/{lesson.json()['id']}/complete",
            headers=learner_headers,
        )
        assert premature.status_code == 200
        assert premature.json()["status"] == "completed"
        assert premature.json()["progress_percent"] == 100
        assert premature.json()["certificate_number"].startswith("NGE-")
        certificate_id = premature.json()["certificate_id"]
        certificate_pdf = client.get(
            f"{base}/certificates/{certificate_id}/download",
            headers=learner_headers,
        )
        assert certificate_pdf.status_code == 200
        assert certificate_pdf.headers["content-type"] == "application/pdf"
        assert certificate_pdf.headers["cache-control"] == "private, no-store"
        assert certificate_pdf.headers["content-disposition"].endswith('.pdf"')
        assert certificate_pdf.content.startswith(b"%PDF-")
        manager_pdf = client.get(
            f"{base}/certificates/{certificate_id}/download",
            headers=admin_headers,
        )
        assert manager_pdf.status_code == 200
        outsider_headers = _register(client, "learning-outsider@example.org")
        assert (
            client.get(
                f"{base}/certificates/{certificate_id}/download",
                headers=outsider_headers,
            ).status_code
            == 404
        )
        learner_progress = client.get(
            f"{base}/courses/{course_id}/my-progress",
            headers=learner_headers,
        )
        assert learner_progress.status_code == 200
        assert learner_progress.json()["progress_percent"] == 100
        assert learner_progress.json()["certificate_id"] == certificate_id
        assert learner_progress.json()["certificate_status"] == "valid"
        assert lesson.json()["id"] in learner_progress.json()["completed_lesson_ids"]
        learner_detail = client.get(
            f"{base}/courses/{course_id}/learners/{learner_id}/progress",
            headers=admin_headers,
        )
        assert learner_detail.status_code == 200
        learner_detail_body = learner_detail.json()
        assert learner_detail_body["learner_id"] == learner_id
        assert learner_detail_body["enrollment"]["progress_percent"] == 100
        assert any(
            item["lesson_id"] == lesson.json()["id"] and item["completed"]
            for item in learner_detail_body["lessons"]
        )
        assert isinstance(learner_detail_body["assessments"], list)
        assert isinstance(learner_detail_body["attendance"], list)
        assert isinstance(learner_detail_body["mentorships"], list)
        denied_learner_detail = client.get(
            f"{base}/courses/{course_id}/learners/{learner_id}/progress",
            headers=learner_headers,
        )
        assert denied_learner_detail.status_code == 403
        missing_learner_detail = client.get(
            f"{base}/courses/{course_id}/learners/00000000-0000-0000-0000-000000000000/progress",
            headers=admin_headers,
        )
        assert missing_learner_detail.status_code == 404
        verified = client.get(
            f"{base}/certificates/verify/{premature.json()['verification_code']}",
        )
        assert verified.status_code == 200
        assert verified.json()["valid"] is True
        revoked = client.post(
            f"{base}/certificates/{premature.json()['certificate_id']}/revoke",
            headers=admin_headers,
        )
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        revoked_pdf = client.get(
            f"{base}/certificates/{certificate_id}/download",
            headers=learner_headers,
        )
        assert revoked_pdf.status_code == 410
        revoked_verification = client.get(
            f"{base}/certificates/verify/{premature.json()['verification_code']}"
        )
        assert revoked_verification.status_code == 200
        assert revoked_verification.json()["valid"] is False

        overdue = client.post(
            f"{base}/courses/{course_id}/assessments",
            headers=admin_headers,
            json={
                "title": "Late submission check",
                "assessment_type": "assignment",
                "instructions": "This deadline has passed.",
                "due_at": "2020-01-01T00:00:00Z",
            },
        )
        assert overdue.status_code == 201

        late_learner_headers = _register(client, "learning-late@example.org")
        late_invitation = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=admin_headers,
            json={"identifier": "learning-late@example.org", "role": "youth_volunteer"},
        )
        assert late_invitation.status_code == 201
        late_acceptance = client.post(
            f"/api/organizations/{org_id}/memberships/{late_invitation.json()['id']}/accept",
            headers=late_learner_headers,
        )
        assert late_acceptance.status_code == 200
        late_application = client.post(
            f"{base}/courses/{course_id}/enrollments",
            headers=late_learner_headers,
        )
        assert late_application.status_code == 201
        late_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "learning-late@example.org",
                "password": "correct horse battery staple",
            },
        )
        late_learner_id = TokenService(settings.jwt_secret_key.get_secret_value()).decode(
            late_login.json()["access_token"], expected_type="access"
        )["sub"]
        late_approval = client.post(
            f"{base}/courses/{course_id}/enrollments/{late_learner_id}/decision",
            headers=admin_headers,
            json={"decision": "approved"},
        )
        assert late_approval.status_code == 200
        full_cohort_assignment = client.post(
            f"{base}/courses/{course_id}/enrollments/{late_learner_id}/cohort",
            headers=admin_headers,
            json={"cohort_id": cohort_id},
        )
        assert full_cohort_assignment.status_code == 409

        rejected_late = client.post(
            f"{base}/assessments/{overdue.json()['id']}/submissions",
            headers=late_learner_headers,
            json={"submission": {"text": "late"}},
        )
        assert rejected_late.status_code == 409

        attendance = client.post(
            f"{base}/courses/{course_id}/attendance",
            headers=admin_headers,
            json={
                "session_key": "workshop-2026-01",
                "session_title": "Community climate workshop",
                "session_date": "2026-11-10",
                "learner_id": learner_id,
                "attendance_status": "present",
            },
        )
        assert attendance.status_code == 201
        bulk_attendance = client.post(
            f"{base}/courses/{course_id}/attendance/bulk",
            headers=admin_headers,
            json={
                "session_key": "workshop-2026-02",
                "session_title": "Second community climate workshop",
                "session_date": "2026-11-17",
                "learners": [
                    {"learner_id": learner_id, "attendance_status": "late"},
                ],
            },
        )
        assert bulk_attendance.status_code == 201
        assert bulk_attendance.json()["recorded"] == 1
        duplicate_bulk = client.post(
            f"{base}/courses/{course_id}/attendance/bulk",
            headers=admin_headers,
            json={
                "session_key": "workshop-2026-02",
                "session_title": "Second community climate workshop",
                "session_date": "2026-11-17",
                "learners": [
                    {"learner_id": learner_id, "attendance_status": "present"},
                    {"learner_id": learner_id, "attendance_status": "late"},
                ],
            },
        )
        assert duplicate_bulk.status_code == 422

        attendance_rows = client.get(
            f"{base}/courses/{course_id}/attendance",
            headers=admin_headers,
        )
        assert attendance_rows.status_code == 200
        assert attendance_rows.json()[0]["learner_id"] == learner_id
        attendance_export = client.get(
            f"{base}/courses/{course_id}/attendance/export",
            headers=admin_headers,
        )
        assert attendance_export.status_code == 200
        assert "text/csv" in attendance_export.headers["content-type"]
        assert (
            "session_key,session_title,session_date,learner_id,attendance_status"
            in attendance_export.text
        )
        assert learner_id in attendance_export.text
        learner_attendance_access = client.get(
            f"{base}/courses/{course_id}/attendance",
            headers=learner_headers,
        )
        assert learner_attendance_access.status_code == 403
        own_attendance = client.get(f"{base}/my-attendance", headers=learner_headers)
        assert own_attendance.status_code == 200
        assert len(own_attendance.json()) == 2
        assert {row["attendance_status"] for row in own_attendance.json()} == {"present", "late"}

        employee_membership = client.get(
            f"/api/organizations/{org_id}/memberships/me",
            headers=employee_headers,
        )
        assert employee_membership.status_code == 200
        employee_membership_id = employee_membership.json()["id"]
        grant_researcher = client.patch(
            f"/api/organizations/{org_id}/memberships/{employee_membership_id}/roles",
            headers=admin_headers,
            json={"roles": ["employee", "researcher"]},
        )
        assert grant_researcher.status_code == 200
        secondary_role_mentor = client.post(
            f"{base}/courses/{course_id}/mentorships",
            headers=admin_headers,
            json={
                "mentor_id": employee_membership.json()["user_id"],
                "mentee_id": learner_id,
                "notes": "Mentor eligibility through secondary researcher role.",
            },
        )
        assert secondary_role_mentor.status_code == 201

        admin_id = TokenService(settings.jwt_secret_key.get_secret_value()).decode(
            client.post(
                "/api/auth/login",
                json={
                    "identifier": "learning-admin@example.org",
                    "password": "correct horse battery staple",
                },
            ).json()["access_token"],
            expected_type="access",
        )["sub"]
        mentorship = client.post(
            f"{base}/courses/{course_id}/mentorships",
            headers=admin_headers,
            json={
                "mentor_id": admin_id,
                "mentee_id": learner_id,
                "notes": "Monthly learning support.",
            },
        )
        assert mentorship.status_code == 201
        closed_mentorship = client.patch(
            f"{base}/courses/{course_id}/mentorships/{mentorship.json()['id']}/status",
            headers=admin_headers,
            json={"status": "completed"},
        )
        assert closed_mentorship.status_code == 200
        assert closed_mentorship.json()["status"] == "completed"
        repeated_close = client.patch(
            f"{base}/courses/{course_id}/mentorships/{mentorship.json()['id']}/status",
            headers=admin_headers,
            json={"status": "ended"},
        )
        assert repeated_close.status_code == 409
        mentorship_rows = client.get(
            f"{base}/courses/{course_id}/mentorships",
            headers=admin_headers,
        )
        assert mentorship_rows.status_code == 200
        assert mentorship_rows.json()[0]["mentee_id"] == learner_id
        learner_mentorship_access = client.get(
            f"{base}/courses/{course_id}/mentorships",
            headers=learner_headers,
        )
        assert learner_mentorship_access.status_code == 403
        own_mentorships = client.get(f"{base}/my-mentorships", headers=learner_headers)
        assert own_mentorships.status_code == 200
        assert len(own_mentorships.json()) == 2
        assert own_mentorships.json()[0]["relationship"] == "mentee"
        assert own_mentorships.json()[0]["course_title"] == "Community Climate Action"

        summary = client.get(
            f"{base}/courses/{course_id}/progress",
            headers=admin_headers,
        )
        assert summary.status_code == 200
        assert summary.json()["completed"] == 1
        assert summary.json()["attendance_records"] == 2
        assert summary.json()["attendance_by_status"]["present"] == 1
        assert summary.json()["attendance_by_status"]["late"] == 1
        assert summary.json()["attendance_sessions"] == 2
        assert summary.json()["mentorship_assignments"] >= 1
        assert summary.json()["assessment_submissions"] >= 1
        assert summary.json()["pending_evaluations"] == 0

        # The same learner may enrol in multiple courses. Portfolio metrics must
        # count one unique learner and two course-enrolment records.
        second_course = client.post(
            f"{base}/courses",
            headers=admin_headers,
            json={
                "title": "Youth Climate Practice",
                "slug": "youth-climate-practice",
                "description": "Practical exercises for community climate action.",
                "category": "climate",
                "programme_id": programme_id,
                "delivery_mode": "online",
            },
        )
        assert second_course.status_code == 201
        second_course_id = second_course.json()["id"]
        second_module = client.post(
            f"{base}/courses/{second_course_id}/modules",
            headers=admin_headers,
            json={"title": "Community practice", "position": 1},
        )
        assert second_module.status_code == 201
        second_lesson = client.post(
            f"{base}/modules/{second_module.json()['id']}/lessons",
            headers=admin_headers,
            json={
                "title": "Community climate exercises",
                "content_type": "text",
                "content": "Complete practical community exercises.",
                "position": 1,
            },
        )
        assert second_lesson.status_code == 201
        second_course_publish = client.post(
            f"{base}/courses/{second_course_id}/publish",
            headers=admin_headers,
        )
        assert second_course_publish.status_code == 200
        second_application = client.post(
            f"{base}/courses/{second_course_id}/enrollments",
            headers=learner_headers,
        )
        assert second_application.status_code == 201
        second_approval = client.post(
            f"{base}/courses/{second_course_id}/enrollments/{learner_id}/decision",
            headers=admin_headers,
            json={"decision": "approved"},
        )
        assert second_approval.status_code == 200
        same_learner_second_course_assignment = client.post(
            f"{base}/courses/{second_course_id}/enrollments/{learner_id}/cohort",
            headers=admin_headers,
            json={"cohort_id": cohort_id},
        )
        assert same_learner_second_course_assignment.status_code == 200
        cohort_after_second_course = client.get(f"{base}/cohorts", headers=admin_headers)
        assert cohort_after_second_course.status_code == 200
        assert cohort_after_second_course.json()[0]["assigned_count"] == 2

        programme_outcomes = client.get(
            f"{base}/programmes/{programme_id}/outcomes",
            headers=admin_headers,
        )
        assert programme_outcomes.status_code == 200
        outcomes = programme_outcomes.json()
        assert outcomes["programme_id"] == programme_id
        assert outcomes["course_count"] == 2
        assert outcomes["totals"]["learners"] == 3
        assert outcomes["totals"]["enrolments"] == 4
        assert outcomes["totals"]["completed"] == 1
        assert outcomes["totals"]["attendance_records"] == 2
        assert outcomes["totals"]["pending_evaluations"] == 0
        assert {item["course_id"] for item in outcomes["courses"]} == {
            course_id,
            second_course_id,
        }
        assert sum(item["enrolments"] for item in outcomes["courses"]) == 4
        assert all(item["learners"] == item["enrolments"] for item in outcomes["courses"])
        denied_programme_outcomes = client.get(
            f"{base}/programmes/{programme_id}/outcomes",
            headers=learner_headers,
        )
        assert denied_programme_outcomes.status_code == 403
        missing_programme_outcomes = client.get(
            f"{base}/programmes/00000000-0000-0000-0000-000000000000/outcomes",
            headers=admin_headers,
        )
        assert missing_programme_outcomes.status_code == 404
        exported_outcomes = client.get(
            f"{base}/programmes/{programme_id}/outcomes/export",
            headers=admin_headers,
        )
        assert exported_outcomes.status_code == 200
        assert exported_outcomes.headers["content-type"].startswith("text/csv")
        assert "programme_total,learners,3" in exported_outcomes.text
        assert "programme_total,enrolments,4" in exported_outcomes.text
        assert "enrolments,approved,completed,average_progress" in exported_outcomes.text
        denied_outcomes_export = client.get(
            f"{base}/programmes/{programme_id}/outcomes/export",
            headers=learner_headers,
        )
        assert denied_outcomes_export.status_code == 403

        learning_portfolio = client.get(
            f"{base}/portfolio-outcomes",
            headers=admin_headers,
        )
        assert learning_portfolio.status_code == 200
        learning_portfolio_body = learning_portfolio.json()
        assert learning_portfolio_body["programmes_total"] == 1
        assert learning_portfolio_body["courses_total"] == 2
        assert learning_portfolio_body["totals"]["learners"] == 3
        assert learning_portfolio_body["totals"]["enrolments"] == 4
        assert learning_portfolio_body["totals"]["completed"] == 1
        assert learning_portfolio_body["totals"]["attendance_records"] == 2
        assert learning_portfolio_body["totals"]["pending_evaluations"] == 0
        assert learning_portfolio_body["programmes"][0]["programme_id"] == programme_id
        denied_learning_portfolio = client.get(
            f"{base}/portfolio-outcomes",
            headers=learner_headers,
        )
        assert denied_learning_portfolio.status_code == 403

        learning_portfolio_export = client.get(
            f"{base}/portfolio-outcomes/export",
            headers=admin_headers,
        )
        assert learning_portfolio_export.status_code == 200
        assert learning_portfolio_export.headers["content-type"].startswith("text/csv")
        assert learning_portfolio_export.content.startswith(b"\xef\xbb\xbf")
        assert "organisation_total,learners,3" in learning_portfolio_export.text
        assert "organisation_total,enrolments,4" in learning_portfolio_export.text
        assert "Climate Learning Programme" in learning_portfolio_export.text
        denied_learning_portfolio_export = client.get(
            f"{base}/portfolio-outcomes/export",
            headers=learner_headers,
        )
        assert denied_learning_portfolio_export.status_code == 403
