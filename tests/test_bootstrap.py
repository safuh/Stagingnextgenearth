"""Regression tests for the learner portion of the founder bootstrap script."""

from typing import Any

import pytest

from scripts.bootstrap_nextgen import ApiError, provision_learners


class FakeApi:
    def __init__(self) -> None:
        self.subject = ""
        self.applications: list[tuple[str, str]] = []
        self.courses = [
            {"id": "course-1", "slug": "climate-literacy", "status": "published"},
            {"id": "course-2", "slug": "draft-course", "status": "draft"},
        ]

    def register_or_reuse(self, identifier: str, password: str) -> None:
        self.subject = identifier
        assert password

    def authenticate(self, identifier: str, password: str) -> None:
        self.subject = identifier
        assert password

    @property
    def request_subject(self) -> str:
        return self.subject

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        if method == "GET" and path.endswith("/learning/courses"):
            return self.courses
        if method == "GET" and path.endswith("/learning/my-enrollments"):
            return [
                {"course_id": course_id}
                for learner, course_id in self.applications
                if learner == self.subject
            ]
        if method == "POST" and path.endswith("/learning/courses/course-1/enrollments"):
            self.applications.append((self.subject, "course-1"))
            assert expected == (201,)
            return {"status": "applied"}
        raise AssertionError(f"Unexpected API call: {method} {path}")


def test_provision_learners_submits_pending_applications_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_LEARNER_PASSWORD", "dedicated-demo-password")
    api = FakeApi()
    learners = [
        {
            "identifier": "learner@example.org",
            "password_env": "DEMO_LEARNER_PASSWORD",
            "course_slug": "climate-literacy",
        }
    ]

    provision_learners(api, "org-1", learners)
    provision_learners(api, "org-1", learners)

    assert api.applications == [("learner@example.org", "course-1")]


def test_provision_learners_rejects_unpublished_or_missing_courses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_LEARNER_PASSWORD", "dedicated-demo-password")
    api = FakeApi()
    with pytest.raises(ApiError, match="Published course"):
        provision_learners(
            api,
            "org-1",
            [{
                "identifier": "learner@example.org",
                "password_env": "DEMO_LEARNER_PASSWORD",
                "course_slug": "draft-course",
            }],
        )
