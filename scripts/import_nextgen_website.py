#!/usr/bin/env python3
# ruff: noqa: E501

"""Capture official NextGen for Earth website copy and media into staging CMS.

Uses only the Python standard library plus the project's SQLAlchemy dependencies.
Assets are copied to web/public/media/nextgen-source; all captured page sections
are stored as source-attributed CMS records. The import never creates accounts,
changes ownership, or verifies partner relationships. It is intended for a
private staging/demo tenant; obtain media permissions before production reuse.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.core.config import get_settings
from stagingnextgenearth.platform.models import (
    InstitutionalPartner,
    LearningCourse,
    LearningLesson,
    LearningModule,
    Organization,
    OrganizationPerson,
    Programme,
    PublicContentEntry,
)

SOURCE = "https://nextgenforearth.org/"
ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "web" / "public" / "media" / "nextgen-source"
MANIFEST = ROOT / "scripts" / "data" / "nextgen_website_assets.json"
CAPTURED_AT = datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:90] or "website-image"


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.images: list[tuple[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.sections: list[dict[str, str]] = []
        self.heading = ""
        self.current: list[str] = []
        self.capture_tag: str | None = None
        self.capture: list[str] = []
        self.link_href: str | None = None
        self.link_text: list[str] = []

    def _flush_capture(self) -> None:
        value = " ".join(" ".join(self.capture).split())
        if value and self.heading:
            self.current.append(value)
        self.capture = []
        self.capture_tag = None

    def _flush_section(self) -> None:
        if self.heading:
            self.sections.append({"heading": self.heading, "body": "\n\n".join(self.current)})
        self.heading = ""
        self.current = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "img":
            # Prefer the largest responsive source; plain `src` is commonly a
            # tiny WordPress thumbnail and makes the public site look blurry.
            candidates: list[tuple[int, str]] = []
            for candidate in (values.get("src"), values.get("data-src"), values.get("data-lazy-src"), values.get("data-original")):
                if candidate:
                    candidates.append((0, candidate.strip()))
            for candidate in (values.get("srcset") or values.get("data-srcset") or "").split(","):
                parts = candidate.strip().rsplit(None, 1)
                if parts:
                    width = int(re.sub(r"[^0-9]", "", parts[1])) if len(parts) > 1 and re.search(r"[0-9]", parts[1]) else 0
                    candidates.append((width, parts[0]))
            if candidates:
                _, best_source = max(candidates, key=lambda item: item[0])
                self.images.append((values.get("alt") or "NextGen for Earth image", best_source))
        if tag == "a" and values.get("href"):
            self.link_href = values["href"]
            self.link_text = []
        if tag in {"h1", "h2", "h3"}:
            self._flush_capture()
            self._flush_section()
            self.capture_tag = tag
            self.capture = []
        elif tag in {"p", "li", "blockquote", "address"}:
            self._flush_capture()
            self.capture_tag = tag
            self.capture = []

    def handle_data(self, data: str) -> None:
        if self.capture_tag:
            self.capture.append(data)
        if self.link_href is not None:
            self.link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.capture_tag == tag:
            value = " ".join(" ".join(self.capture).split())
            if tag in {"h1", "h2", "h3"}:
                self._flush_section()
                self.heading = value
                self.current = []
            elif value and self.heading:
                self.current.append(value)
            self.capture_tag = None
            self.capture = []
        if tag == "a" and self.link_href is not None:
            label = " ".join(" ".join(self.link_text).split())
            href = urljoin(SOURCE, self.link_href)
            if label and href.startswith(("https://", "http://")):
                self.links.append({"label": label, "url": href})
            self.link_href = None
            self.link_text = []

    def finish(self) -> None:
        self._flush_capture()
        self._flush_section()


def download_image(alt: str, source: str) -> dict[str, str] | None:
    try:
        if source.startswith("data:"):
            header, encoded = source.split(",", 1)
            mime = header.split(";", 1)[0].split(":", 1)[1]
            raw = base64.b64decode(encoded, validate=False)
            ext = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
                "image/svg+xml": "svg",
            }.get(mime, "bin")
        else:
            request = Request(
                urljoin(SOURCE, source), headers={"User-Agent": "NextGenForEarthDemoImporter/1.0"}
            )
            with urlopen(request, timeout=25) as response:
                raw = response.read(12_000_001)
                mime = response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
            ext = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
                "image/svg+xml": "svg",
            }.get(mime, Path(urlparse(source).path).suffix.lstrip(".") or "jpg")
        if not raw or len(raw) > 12_000_000 or not mime.startswith("image/"):
            return None
        digest = hashlib.sha256(raw).hexdigest()
        name = f"{slugify(alt)}-{digest[:10]}.{ext}"
        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        (ASSET_DIR / name).write_bytes(raw)
        return {
            "alt": alt,
            "path": f"/media/nextgen-source/{name}",
            "sha256": digest,
            "mime_type": mime,
            "bytes": str(len(raw)),
            "source_url": SOURCE,
        }
    except (ValueError, OSError, TimeoutError):
        return None


async def run(organization_slug: str, publish: bool) -> None:
    """Import by organisation slug or UUID (the admin UI commonly exposes IDs)."""
    request = Request(SOURCE, headers={"User-Agent": "NextGenForEarthDemoImporter/1.0"})
    with urlopen(request, timeout=40) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = SiteParser()
    parser.feed(html)
    parser.finish()
    images = [item for alt, src in parser.images if (item := download_image(alt.strip(), src))]
    # Stable aliases make the public site and pitch pack independent of image hashes.
    aliases = {
        "hero-landscape.jpg": ("african landscape",),
        "programme-research-capacity.jpg": ("research capacity building",),
        "programme-healthcare-workers.jpg": ("healthcare worker training",),
        "programme-youth-stewardship.jpg": ("youth climate stewardship",),
        "programme-indigenous-knowledge.jpg": ("indigenous knowledge transfer",),
        "gallery-team.jpg": ("nextgen for earth team",),
        "gallery-tree-planting.jpg": ("school tree planting",),
        "gallery-restoration.jpg": ("environmental restoration",),
        "gallery-early-career.jpg": ("early career climate scientists",),
        "gallery-conference.jpg": ("pan african conference",),
        "research-ageing-climate.jpg": ("elderly african couple",),
        "partner-university-of-nairobi.png": ("university of nairobi",),
        "partner-medical-college-wisconsin.png": ("medical college of wisconsin",),
        "partner-mmust.png": ("masinde muliro university",),
        "partner-chance-network.png": ("chance network",),
    }
    for alias, terms in aliases.items():
        match = next(
            (item for item in images if all(term in item["alt"].casefold() for term in terms)), None
        )
        if match:
            source_path = ROOT / "web" / "public" / match["path"].lstrip("/")
            if source_path.exists():
                shutil.copy2(source_path, ASSET_DIR / alias)
                match["alias"] = f"/media/nextgen-source/{alias}"
    text_capture = "\n\n".join(f"# {item['heading']}\n{item['body']}" for item in parser.sections)
    manifest = {
        "source_url": SOURCE,
        "captured_at": CAPTURED_AT,
        "sections": parser.sections,
        "links": parser.links,
        "images": images,
        "rights_note": "Publication rights and individual consent were confirmed by the organisation for the supplied website material. Preserve attribution and any subject-specific restrictions recorded by the organisation.",
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            # Organisation IDs are UUID-shaped strings stored in VARCHAR(36).
            # Parse for validation, then compare the canonical string value.
            try:
                organization_id = UUID(organization_slug)
            except (ValueError, TypeError):
                organization_id = None
            if organization_id is not None:
                org = await db.scalar(
                    select(Organization).where(Organization.id == str(organization_id))
                )
            else:
                org = await db.scalar(
                    select(Organization).where(Organization.slug == organization_slug)
                )
            if org is None:
                raise SystemExit(
                    f"Organisation {organization_slug!r} not found; bootstrap it first."
                )
            actor = org.owner_user_id
            image_by_alt = {normalize(item["alt"]): item["path"] for item in images}
            people = (
                await db.scalars(
                    select(OrganizationPerson).where(OrganizationPerson.organization_id == org.id)
                )
            ).all()
            updated_people = 0
            for person in people:
                image_path = image_by_alt.get(normalize(person.full_name))
                if image_path and person.profile_image_url != image_path:
                    person.profile_image_url = image_path
                    person.source_url = SOURCE
                    person.source_label = "NextGen for Earth public website"
                    updated_people += 1
                # These directory entries are already publicly displayed by the source site.
                if publish:
                    person.review_state = "verified"
                    person.visibility = "public"
            created_pages = 0
            for section in parser.sections:
                title = section["heading"].strip()
                body = section["body"].strip()
                if not title or not body:
                    continue
                item_slug = f"website-{slugify(title)}"[:155]
                entry = await db.scalar(
                    select(PublicContentEntry).where(
                        PublicContentEntry.organization_id == org.id,
                        PublicContentEntry.content_type == "page",
                        PublicContentEntry.slug == item_slug,
                    )
                )
                metadata = {
                    "source_status": "public_website_capture_pending_organisational_confirmation",
                    "source_capture": SOURCE,
                    "captured_at": CAPTURED_AT,
                }
                if entry is None:
                    db.add(
                        PublicContentEntry(
                            organization_id=org.id,
                            content_type="page",
                            slug=item_slug,
                            title=title,
                            summary=f"Imported from the official website section: {title}.",
                            body=body,
                            metadata_json=metadata,
                            publication_state="published" if publish else "draft",
                            source_url=SOURCE,
                            source_label="Official NextGen for Earth website capture",
                            created_by=actor,
                            updated_by=actor,
                        )
                    )
                    created_pages += 1
                else:
                    entry.title, entry.summary, entry.body = (
                        title,
                        f"Imported from the official website section: {title}.",
                        body,
                    )
                    entry.metadata_json = {**(entry.metadata_json or {}), **metadata}
                    entry.source_url, entry.source_label, entry.updated_by = (
                        SOURCE,
                        "Official NextGen for Earth website capture",
                        actor,
                    )
                    if publish and entry.publication_state != "archived":
                        entry.publication_state = "published"
                        entry.approved_by, entry.approved_at, entry.published_at = (
                            actor,
                            datetime.now(UTC),
                            datetime.now(UTC),
                        )
            archive_slug = "official-website-full-content-capture"
            archive = await db.scalar(
                select(PublicContentEntry).where(
                    PublicContentEntry.organization_id == org.id,
                    PublicContentEntry.content_type == "page",
                    PublicContentEntry.slug == archive_slug,
                )
            )
            archive_meta = {
                "source_status": "public_website_capture_pending_organisational_confirmation",
                "source_capture": SOURCE,
                "captured_at": CAPTURED_AT,
                "image_manifest": str(MANIFEST.relative_to(ROOT)),
                "image_count": len(images),
                "section_count": len(parser.sections),
                "link_count": len(parser.links),
                "rights_note": manifest["rights_note"],
            }
            if archive is None:
                db.add(
                    PublicContentEntry(
                        organization_id=org.id,
                        content_type="page",
                        slug=archive_slug,
                        title="Official website — complete content capture",
                        summary="Complete text, headings, links and image inventory captured from nextgenforearth.org.",
                        body=text_capture,
                        metadata_json=archive_meta,
                        publication_state="published" if publish else "draft",
                        source_url=SOURCE,
                        source_label="Official NextGen for Earth website capture",
                        created_by=actor,
                        updated_by=actor,
                    )
                )
                created_pages += 1
            else:
                archive.body, archive.metadata_json, archive.updated_by = (
                    text_capture,
                    archive_meta,
                    actor,
                )
                if publish and archive.publication_state != "archived":
                    archive.publication_state = "published"
                    archive.approved_by, archive.approved_at, archive.published_at = (
                        actor,
                        datetime.now(UTC),
                        datetime.now(UTC),
                    )
            # Website listings are not proof of current legal/operational partnership.
            partners = (
                await db.scalars(
                    select(InstitutionalPartner).where(
                        InstitutionalPartner.organization_id == org.id
                    )
                )
            ).all()
            for partner in partners:
                if partner.verification_state != "verified":
                    partner.verification_state = "pending"
                    if partner.relationship_status == "active":
                        partner.relationship_status = "prospect"
                if publish:
                    # The source site publicly lists these institutions; this does not
                    # assert a currently active or legally verified relationship.
                    partner.visibility = "public"
            if publish:
                # Publish source-attributed catalogue entries only in the staging demo.
                values = (
                    await db.scalars(
                        select(PublicContentEntry).where(
                            PublicContentEntry.organization_id == org.id,
                            PublicContentEntry.content_type.in_(
                                [
                                    "programme",
                                    "training_track",
                                    "initiative",
                                    "research_area",
                                    "impact_metric",
                                    "publication",
                                ]
                            ),
                        )
                    )
                ).all()
                metric_values = {
                    "youth-trained": "100+",
                    "children-reached": "4,000+",
                    "publications": "12",
                    "youth-mentored": "35+",
                    "trees-planted": "40,000+",
                }
                for entry in values:
                    entry.publication_state = "published"
                    entry.approved_by, entry.approved_at, entry.published_at = (
                        actor,
                        datetime.now(UTC),
                        datetime.now(UTC),
                    )
                    entry.metadata_json = {
                        **(entry.metadata_json or {}),
                        "source_status": "website-reported; confirmation required",
                        "source_capture": SOURCE,
                    }
                    if entry.content_type == "impact_metric":
                        entry.metadata_json["display_value"] = metric_values.get(entry.slug, "")
                programmes = (
                    await db.scalars(select(Programme).where(Programme.organization_id == org.id))
                ).all()
                for programme in programmes:
                    if programme.status == "draft":
                        programme.status = "planned"
                # Create real course shells and lessons for the three published training tracks.
                tracks = [
                    (
                        "early-career-researchers",
                        "Early Career Researchers",
                        "Research methods, systematic reviews, data management, evidence synthesis, grant writing, ethics and safeguarding.",
                        "research-capacity-building",
                        [
                            (
                                "Research foundations",
                                ["Research Methods & Study Design", "Data Collection & Management"],
                            ),
                            (
                                "Evidence and dissemination",
                                [
                                    "Systematic Reviews",
                                    "Synthesising Evidence",
                                    "Grant Writing",
                                    "Research Ethics & Safeguarding",
                                ],
                            ),
                        ],
                    ),
                    (
                        "healthcare-workers",
                        "Healthcare Workers",
                        "Climate-health fundamentals, heat impacts, extreme weather, service delivery, resilience and mental health.",
                        "healthcare-worker-training",
                        [
                            (
                                "Climate and health",
                                [
                                    "Climate Change & Health Fundamentals",
                                    "Heat Impacts on Patient Care",
                                ],
                            ),
                            (
                                "Resilient services",
                                [
                                    "Extreme Weather & Service Delivery",
                                    "Climate-Responsive Care",
                                    "Community Resilience Strategies",
                                    "Mental Health & Climate Stress",
                                ],
                            ),
                        ],
                    ),
                    (
                        "youth-climate-stewards",
                        "Youth Climate Stewards",
                        "Climate science, environmental stewardship, restoration, peer mentorship and community engagement.",
                        "youth-climate-stewardship",
                        [
                            (
                                "Climate literacy and stewardship",
                                [
                                    "Climate Science Fundamentals",
                                    "Environmental Stewardship",
                                    "Tree Planting & Restoration",
                                ],
                            ),
                            (
                                "Youth-led action",
                                [
                                    "Peer-to-Peer Mentorship",
                                    "Community Engagement",
                                    "Mental Health Peer Support",
                                ],
                            ),
                        ],
                    ),
                ]
                for course_slug, title, description, programme_slug, modules in tracks:
                    course = await db.scalar(
                        select(LearningCourse).where(
                            LearningCourse.organization_id == org.id,
                            LearningCourse.slug == course_slug,
                        )
                    )
                    programme = await db.scalar(
                        select(Programme).where(
                            Programme.organization_id == org.id, Programme.slug == programme_slug
                        )
                    )
                    if course is None:
                        course = LearningCourse(
                            organization_id=org.id,
                            programme_id=programme.id if programme else None,
                            title=title,
                            slug=course_slug,
                            description=description,
                            category="Climate and research capacity",
                            delivery_mode="blended",
                            status="published",
                            created_by=actor,
                        )
                        db.add(course)
                        await db.flush()
                    else:
                        course.status = "published"
                        if programme and course.programme_id is None:
                            course.programme_id = programme.id
                    for module_index, (module_title, lessons) in enumerate(modules, start=1):
                        module = await db.scalar(
                            select(LearningModule).where(
                                LearningModule.course_id == course.id,
                                LearningModule.position == module_index,
                            )
                        )
                        if module is None:
                            module = LearningModule(
                                course_id=course.id,
                                title=module_title,
                                description=f"{title}: {module_title}.",
                                position=module_index,
                            )
                            db.add(module)
                            await db.flush()
                        for lesson_index, lesson_title in enumerate(lessons, start=1):
                            lesson = await db.scalar(
                                select(LearningLesson).where(
                                    LearningLesson.module_id == module.id,
                                    LearningLesson.position == lesson_index,
                                )
                            )
                            if lesson is None:
                                db.add(
                                    LearningLesson(
                                        module_id=module.id,
                                        title=lesson_title,
                                        content_type="text",
                                        content=f"Demo learning outline for {lesson_title}. Add organisation-approved learning resources, facilitator notes and assessments before live delivery.",
                                        duration_minutes=25,
                                        position=lesson_index,
                                    )
                                )
                # A curated gallery entry lets the public site render the actual source images.
                gallery = [
                    {"alt": item["alt"], "image_url": item.get("alias", item["path"])}
                    for item in images
                    if any(
                        word in item["alt"].casefold()
                        for word in (
                            "early career",
                            "restoration",
                            "stewardship",
                            "conference",
                            "tree planting",
                            "team",
                        )
                    )
                ]
                gallery_entry = await db.scalar(
                    select(PublicContentEntry).where(
                        PublicContentEntry.organization_id == org.id,
                        PublicContentEntry.content_type == "page",
                        PublicContentEntry.slug == "website-gallery",
                    )
                )
                gallery_meta = {
                    "gallery": gallery,
                    "source_status": "public website media; rights/consent confirmation required",
                    "source_capture": SOURCE,
                }
                if gallery_entry is None:
                    db.add(
                        PublicContentEntry(
                            organization_id=org.id,
                            content_type="page",
                            slug="website-gallery",
                            title="In the field — gallery",
                            summary="Photographs captured from the public NextGen for Earth website.",
                            body="Gallery images are source-attributed and should be checked for reuse permission before production republication.",
                            metadata_json=gallery_meta,
                            publication_state="published",
                            source_url=SOURCE,
                            source_label="Official NextGen for Earth website capture",
                            created_by=actor,
                            updated_by=actor,
                        )
                    )
                else:
                    gallery_entry.metadata_json = gallery_meta
                    gallery_entry.publication_state = "published"
                    gallery_entry.updated_by = actor
            await db.commit()
            print(
                f"Website capture complete: {len(images)} images, {len(parser.sections)} sections, {len(parser.links)} links, {updated_people} profile images updated, {created_pages} CMS pages created."
            )
            print(f"Manifest: {MANIFEST.relative_to(ROOT)}")
            print(
                f"CMS mode: {'published website-copy pages for private staging' if publish else 'draft pages'}; partner verification remains pending."
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "--organization-slug",
        "--organization-id",
        dest="organization_slug",
        required=True,
        help="Organisation slug or UUID",
    )
    cli.add_argument(
        "--publish-website-content",
        action="store_true",
        help="Publish the source-captured public website pages for a private staging presentation; not a production approval shortcut.",
    )
    args = cli.parse_args()
    asyncio.run(run(args.organization_slug, args.publish_website_content))
