#!/usr/bin/env python3
"""Idempotently bootstrap Next Gen For Earth's canonical organisation via the API.

Passwords are read from environment variables and are never written to the manifest.
The script deliberately uses public API workflows rather than direct database writes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class ApiError(RuntimeError):
    """An API request failed with a useful, non-secret diagnostic."""


class Api:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self._subject: str | None = None

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=payload, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                if response.status not in expected:
                    raise ApiError(f"{method} {path}: unexpected HTTP {response.status}")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            raise ApiError(f"{method} {path}: HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"{method} {path}: cannot reach API ({exc.reason})") from exc

    def register_or_reuse(self, identifier: str, password: str) -> None:
        try:
            self.request(
                "POST", "/auth/register",
                {"identifier": identifier, "password": password},
                expected=(201,),
            )
        except ApiError as exc:
            if "HTTP 409" not in str(exc):
                raise
        result = self.request(
            "POST", "/auth/login",
            {"identifier": identifier, "password": password},
            expected=(200,),
        )
        self.token = result["access_token"]
        self._subject = result["subject"]

    def organization(self, name: str, slug: str, country_code: str) -> dict[str, Any]:
        organizations = self.request("GET", "/organizations", expected=(200,))
        matches = [item for item in organizations if item["slug"] == slug]
        if matches:
            organization = matches[0]
            summary = self.request(
                "GET", f"/organizations/{organization['id']}/administration-summary",
                expected=(200,),
            )
            if summary["owner_user_id"] != self.request_subject:
                raise ApiError(
                    "The canonical organisation already exists but is owned by another "
                    "account. Refusing to take ownership automatically."
                )
            return organization
        return self.request(
            "POST", "/organizations",
            {
                "name": name,
                "slug": slug,
                "description": "The canonical organisation workspace for Next Gen For Earth.",
                "country_code": country_code,
            },
            expected=(201,),
        )

    @property
    def request_subject(self) -> str:
        # The API login response subject is captured separately by authenticate().
        if self._subject is None:
            raise ApiError("Internal error: authenticated subject is unavailable")
        return self._subject

    def authenticate(self, identifier: str, password: str) -> None:
        result = self.request(
            "POST", "/auth/login",
            {"identifier": identifier, "password": password},
            expected=(200,),
        )
        self.token = result["access_token"]
        self._subject = result["subject"]


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ApiError(f"Required environment variable {name} is not set")
    return value


def load_manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parent / "data" / "nextgen_for_earth.seed.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError(f"Cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ApiError("Manifest root must be a JSON object")
    return value


def provision_staff(
    api: Api,
    organization_id: str,
    owner_identifier: str,
    owner_password: str,
    staff: list[dict[str, Any]],
) -> None:
    """Create accounts and activate their own tenant invitations idempotently."""
    for item in staff:
        identifier = str(item["identifier"]).strip()
        role = str(item["role"]).strip()
        password = env_required(str(item["password_env"]).strip())
        if role not in {
            "founder", "executive", "employee", "programme_manager",
            "researcher", "youth_volunteer", "institutional_partner",
        }:
            raise ApiError(f"Unsupported staff role for {identifier}: {role}")

        # Register-or-reuse and capture the account subject from its login response.
        api.register_or_reuse(identifier, password)
        staff_user_id = api.request_subject

        # Only the canonical organisation owner can invite founder/executive roles.
        api.authenticate(owner_identifier, owner_password)
        memberships = api.request(
            "GET", f"/organizations/{organization_id}/memberships", expected=(200,)
        )
        current = next(
            (m for m in memberships if m.get("user_id") == staff_user_id), None
        )
        if current and current["status"] == "active":
            if current["role"] != role:
                print(
                    f"Membership already active for {identifier} with role "
                    f"{current['role']}; leaving it unchanged."
                )
            continue
        if current and current["status"] == "invited":
            invitation = current
        elif current is None:
            invitation = api.request(
                "POST", f"/organizations/{organization_id}/memberships",
                {"identifier": identifier, "role": role},
                expected=(201,),
            )
        else:
            raise ApiError(
                f"Membership for {identifier} is suspended; reactivate it through "
                "the audited administration workflow."
            )

        # Invitation acceptance is performed while authenticated as the invitee.
        api.authenticate(identifier, password)
        api.request(
            "POST",
            f"/organizations/{organization_id}/memberships/{invitation['id']}/accept",
            expected=(200,),
        )
        print(f"Staff membership active: {identifier} ({role})")


def _transition_programme_status(
    api: Api, organization_id: str, programme: dict[str, Any], target_status: str
) -> None:
    """Move an existing programme forward to its declared operational status."""
    transitions = {
        "draft": [],
        "planned": ["planned"],
        "active": ["planned", "active"],
        "completed": ["planned", "active", "completed"],
        "archived": ["archived"],
    }
    if target_status not in transitions:
        raise ApiError(
            f"Unsupported programme status for {programme.get('slug')}: {target_status}"
        )
    current_status = str(programme.get("status", "draft"))
    if current_status == target_status:
        return
    if current_status not in {"draft", "planned", "active", "completed", "archived"}:
        raise ApiError(
            f"Cannot safely transition programme {programme.get('slug')} "
            f"from unknown status {current_status!r}"
        )
    order = ["draft", "planned", "active", "completed"]
    if current_status == "archived" or target_status == "archived":
        if target_status != "archived":
            raise ApiError(
                f"Refusing to unarchive programme {programme.get('slug')} automatically"
            )
        sequence = ["archived"] if current_status != "archived" else []
    else:
        if order.index(target_status) < order.index(current_status):
            raise ApiError(
                f"Refusing to move programme {programme.get('slug')} backwards "
                f"from {current_status} to {target_status}"
            )
        sequence = order[order.index(current_status) + 1 : order.index(target_status) + 1]
    for next_status in sequence:
        api.request(
            "POST",
            f"/organizations/{organization_id}/programmes/{programme['id']}/status",
            {"status": next_status},
            expected=(200,),
        )


def provision_programmes(api: Api, organization_id: str, programmes: list[dict[str, Any]]) -> None:
    existing = api.request(
        "GET", f"/organizations/{organization_id}/programmes", expected=(200,)
    )
    by_slug = {item["slug"]: item for item in existing}
    for item in programmes:
        slug = str(item["slug"]).strip()
        target_status = str(item.get("status", "active"))
        current = by_slug.get(slug)
        if current is not None:
            _transition_programme_status(api, organization_id, current, target_status)
            continue
        created = api.request(
            "POST", f"/organizations/{organization_id}/programmes",
            {
                "title": item["title"],
                "slug": slug,
                "summary": item.get("summary"),
                "start_date": item.get("start_date")
                or os.environ.get("BOOTSTRAP_ORGANIZATION_FOUNDATION_DATE"),
                "end_date": item.get("end_date"),
            },
            expected=(201,),
        )
        created["slug"] = slug
        _transition_programme_status(api, organization_id, created, target_status)
        created["status"] = target_status
        by_slug[slug] = created


def provision_people(api: Api, organization_id: str, people: list[dict[str, Any]]) -> None:
    existing = api.request(
        "GET", f"/organizations/{organization_id}/people", expected=(200,)
    )
    names = {item["full_name"].casefold() for item in existing}
    for item in people:
        name = str(item["full_name"]).strip()
        if name.casefold() in names:
            continue
        payload = {
            "full_name": name,
            "biography": item.get("biography"),
            "positions": item.get("positions", []),
            "person_types": item.get("person_types", []),
            "country_code": item.get("country_code") or os.environ.get("BOOTSTRAP_ORGANIZATION_COUNTRY_CODE", "KE"),
            "region": item.get("region"),
            "profile_image_url": item.get("profile_image_url"),
            "website_url": item.get("website_url"),
            "source_url": item.get("source_url"),
            "source_label": item.get("source_label", "Next Gen For Earth website"),
        }
        api.request(
            "POST", f"/organizations/{organization_id}/people",
            payload, expected=(201,),
        )
        names.add(name.casefold())


def provision_partners(api: Api, organization_id: str, partners: list[dict[str, Any]]) -> None:
    """Create verified-source partner candidates without auto-verifying or publishing."""
    existing = api.request(
        "GET", f"/organizations/{organization_id}/partners", expected=(200,)
    )
    names = {item["name"].casefold() for item in existing}
    for item in partners:
        name = str(item["name"]).strip()
        if name.casefold() in names:
            continue
        api.request(
            "POST", f"/organizations/{organization_id}/partners",
            {
                "name": name,
                "partner_type": item.get("partner_type", "other"),
                "description": item.get("description"),
                "website_url": item.get("website_url"),
                "country_code": item.get("country_code") or os.environ.get("BOOTSTRAP_ORGANIZATION_COUNTRY_CODE", "KE"),
                "region": item.get("region"),
                "source_url": item.get("source_url"),
            },
            expected=(201,),
        )
        names.add(name.casefold())


def provision_research_studies(
    api: Api, organization_id: str, studies: list[dict[str, Any]]
) -> None:
    """Create concept-stage research records; no ethics or approval state is inferred."""
    existing = api.request(
        "GET", f"/organizations/{organization_id}/research-studies", expected=(200,)
    )
    titles = {item["title"].casefold() for item in existing}
    for item in studies:
        title = str(item["title"]).strip()
        if title.casefold() in titles:
            continue
        api.request(
            "POST", f"/organizations/{organization_id}/research-studies",
            {
                "title": title,
                "abstract": item.get("abstract"),
                "study_type": item.get("study_type"),
                "project_id": item.get("project_id"),
                "ethics_reference": item.get("ethics_reference"),
            },
            expected=(201,),
        )
        titles.add(title.casefold())


def normalize_slug(value: Any) -> str:
    """Convert source identifiers into API-safe, lowercase hyphenated slugs."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", str(value).strip().casefold()).strip("-")
    if not slug:
        raise ApiError(f"Cannot derive a valid CMS slug from {value!r}")
    return slug


def provision_content(api: Api, organization_id: str, entries: list[dict[str, Any]]) -> None:
    """Create source-attributed CMS entries with manifest-controlled publication state."""
    existing = api.request(
        "GET", f"/organizations/{organization_id}/content", expected=(200,)
    )
    existing_by_slug = {item["slug"]: item for item in existing}
    slugs = set(existing_by_slug)
    source_slugs: dict[str, str] = {}
    for item in entries:
        source_slug = str(item["slug"]).strip()
        slug = normalize_slug(source_slug)
        previous = source_slugs.get(slug)
        if previous is not None and previous != source_slug:
            raise ApiError(
                f"CMS slug collision after normalization: {previous!r} and "
                f"{source_slug!r} both become {slug!r}"
            )
        source_slugs[slug] = source_slug
    allowed_types = {
        "page", "programme", "training_track", "initiative",
        "research_area", "impact_metric", "publication",
    }
    for item in entries:
        source_slug = str(item["slug"]).strip()
        slug = normalize_slug(source_slug)
        if slug != source_slug:
            print(f"Normalised CMS slug: {source_slug!r} -> {slug!r}")
        content_type = str(item["content_type"]).strip()
        if content_type not in allowed_types:
            raise ApiError(f"Unsupported CMS content type for {slug}: {content_type}")
        created = existing_by_slug.get(slug)
        if created is None:
            created = api.request(
                "POST", f"/organizations/{organization_id}/content",
                {
                    "content_type": content_type,
                    "slug": slug,
                    "title": item["title"],
                    "summary": item.get("summary"),
                    "body": item.get("body"),
                    "metadata_json": item.get("metadata_json", {}),
                    "source_url": item.get("source_url"),
                },
                expected=(201,),
            )
            slugs.add(slug)
            existing_by_slug[slug] = created
        publication_state = str(item.get("publication_state", "review")).strip()
        if publication_state not in {"draft", "review", "published", "archived"}:
            raise ApiError(
                f"Unsupported CMS publication state for {slug}: {publication_state}"
            )
        api.request(
            "PATCH",
            f"/organizations/{organization_id}/content/{created['id']}",
            {"publication_state": publication_state},
            expected=(200,),
        )
        slugs.add(slug)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="Private JSON data manifest")
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        base_url = os.environ.get(
            "BOOTSTRAP_API_URL", "http://127.0.0.1:8000/api"
        ).rstrip("/")
        identifier = env_required("BOOTSTRAP_ADMIN_IDENTIFIER")
        password = env_required("BOOTSTRAP_ADMIN_PASSWORD")
        api = Api(base_url)
        api.register_or_reuse(identifier, password)
        api.authenticate(identifier, password)
        organization = api.organization(
            os.environ.get("BOOTSTRAP_ORGANIZATION_NAME", "Next Gen For Earth"),
            os.environ.get("BOOTSTRAP_ORGANIZATION_SLUG", "next-gen-for-earth"),
            os.environ.get("BOOTSTRAP_ORGANIZATION_COUNTRY_CODE", "KE"),
        )
        organization_id = organization["id"]
        print(f"Canonical organisation ready: {organization['name']} ({organization_id})")
        print("Owner account authenticated and organisation administrator membership confirmed.")
        provision_people(api, organization_id, manifest.get("people", []))
        provision_partners(api, organization_id, manifest.get("partners", []))
        provision_programmes(api, organization_id, manifest.get("programmes", []))
        provision_research_studies(
            api, organization_id, manifest.get("research_studies", [])
        )
        provision_content(api, organization_id, manifest.get("content", []))
        provision_staff(
            api, organization_id, identifier, password, manifest.get("staff", [])
        )
        print("Bootstrap complete. Review people and programme publication states in the portal.")
        return 0
    except (ApiError, KeyError, TypeError) as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
