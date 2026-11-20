"""Regression tests for the learner portion of the founder bootstrap script."""

from typing import Any

import pytest

from scripts.bootstrap_nextgen import ApiError, provision_learners, provision_staff


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
        return "staff-user" if self.subject == "admin@example.org" else "owner-user"

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

    provision_learners(api, "org-1", learners)  # type: ignore[arg-type]
    provision_learners(api, "org-1", learners)  # type: ignore[arg-type]

    assert api.applications == [("learner@example.org", "course-1")]


def test_provision_learners_rejects_unpublished_or_missing_courses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_LEARNER_PASSWORD", "dedicated-demo-password")
    api = FakeApi()
    with pytest.raises(ApiError, match="Published course"):
        provision_learners(
            api,  # type: ignore[arg-type]
            "org-1",
            [
                {
                    "identifier": "learner@example.org",
                    "password_env": "DEMO_LEARNER_PASSWORD",
                    "course_slug": "draft-course",
                }
            ],
        )


class FakeStaffApi:
    def __init__(self, memberships: list[dict[str, Any]] | None = None) -> None:
        self.subject = ""
        self.memberships = memberships or []
        self.calls: list[tuple[str, str, str, dict[str, Any] | None]] = []
        self.next_id = 1

    def register_or_reuse(self, identifier: str, password: str) -> None:
        assert password
        self.subject = identifier

    def authenticate(self, identifier: str, password: str) -> None:
        assert password
        self.subject = identifier

    @property
    def request_subject(self) -> str:
        return "staff-user" if self.subject == "admin@example.org" else "owner-user"

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        self.calls.append((method, path, self.subject, body))
        if method == "GET" and path.endswith("/memberships"):
            assert self.subject == "owner@example.org"
            return self.memberships
        if method == "POST" and path.endswith("/memberships"):
            assert self.subject == "owner@example.org"
            assert body is not None
            invitation = {
                "id": f"invite-{self.next_id}",
                "user_id": "staff-user",
                "role": body["role"],
                "status": "invited",
            }
            self.next_id += 1
            self.memberships.append(invitation)
            assert expected == (201,)
            return invitation
        if method == "POST" and path.endswith("/accept"):
            assert self.subject == "admin@example.org"
            invitation_id = path.rsplit("/", 2)[-2]
            invitation = next(item for item in self.memberships if item["id"] == invitation_id)
            invitation["status"] = "active"
            assert expected == (200,)
            return invitation
        raise AssertionError(f"Unexpected API call: {method} {path} as {self.subject}")


def test_provision_staff_allows_owner_granted_admin_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "dedicated-admin-password")
    api = FakeStaffApi()
    provision_staff(
        api,  # type: ignore[arg-type]
        "org-1",
        "owner@example.org",
        "owner-password",
        [
            {
                "identifier": "admin@example.org",
                "role": "admin",
                "password_env": "BOOTSTRAP_ADMIN_PASSWORD",
            }
        ],
    )
    assert api.memberships == [
        {
            "id": "invite-1",
            "user_id": "staff-user",
            "role": "admin",
            "status": "active",
        }
    ]
    assert any(call[0] == "POST" and call[2] == "owner@example.org" for call in api.calls)
    assert any(call[0] == "POST" and call[2] == "admin@example.org" for call in api.calls)


def test_provision_staff_does_not_accept_an_invitation_with_a_different_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "dedicated-admin-password")
    api = FakeStaffApi(
        [
            {
                "id": "invite-existing",
                "user_id": "staff-user",
                "role": "employee",
                "status": "invited",
            }
        ]
    )
    with pytest.raises(ApiError, match="already exists.*employee"):
        provision_staff(
            api,  # type: ignore[arg-type]
            "org-1",
            "owner@example.org",
            "owner-password",
            [
                {
                    "identifier": "admin@example.org",
                    "role": "admin",
                    "password_env": "BOOTSTRAP_ADMIN_PASSWORD",
                }
            ],
        )
    assert not any(call[1].endswith("/accept") for call in api.calls)
