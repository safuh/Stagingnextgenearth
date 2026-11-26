# ruff: noqa: E501, I001
# fmt: off
"""Idempotently seed a reviewable NextGen for Earth demo catalogue."""
import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.core.config import get_settings
from stagingnextgenearth.platform.models import (
    InstitutionalPartner, LearningAssessment, LearningCourse, LearningLesson, LearningModule,
    Organization, OrganizationPerson, Programme, PublicContentEntry,
)

SOURCE = "https://nextgenforearth.org/"
ROOT = Path(__file__).resolve().parents[1]
MEDIA_MANIFEST = ROOT / "scripts" / "data" / "nextgen_website_assets.json"
GALLERY_TERMS = (
    "early career",
    "restoration",
    "stewardship",
    "conference",
    "tree planting",
    "team",
)


def _normalise_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _public_media() -> tuple[dict[str, str], list[dict[str, str]]]:
    """Read committed website media metadata for repeatable DB-to-web image links."""
    if not MEDIA_MANIFEST.is_file():
        raise RuntimeError(f"Required website media manifest is missing: {MEDIA_MANIFEST}")
    manifest = json.loads(MEDIA_MANIFEST.read_text(encoding="utf-8"))
    images = manifest.get("images", [])
    if not isinstance(images, list):
        raise RuntimeError("Website media manifest 'images' must be a list")

    people_images: dict[str, str] = {}
    gallery: list[dict[str, str]] = []
    for item in images:
        if not isinstance(item, dict):
            continue
        alt = item.get("alt")
        image_path = item.get("alias") or item.get("path")
        if (
            not isinstance(alt, str)
            or not alt.strip()
            or not isinstance(image_path, str)
            or not image_path.startswith("/media/nextgen-source/")
            or ".." in Path(image_path).parts
        ):
            continue
        if _normalise_name(alt) in {_normalise_name(name) for name, _, _ in PEOPLE}:
            people_images[_normalise_name(alt)] = image_path
        if any(term in alt.casefold() for term in GALLERY_TERMS):
            gallery.append({"alt": alt.strip(), "image_url": image_path})
    return people_images, gallery


PEOPLE = [
("Esperant Fumyunga","Acting CEO","executive"),
("Prof Adelaide Lusambili","Senior Scientist & Founder","founder,researcher"),
("Dr Fr Kizito Muchanga","President; Senior Mentor","executive,mentor"),
("Rev Fr Boniface Silayo Tanael","Board Member","board_member"),
("Prof Maria Ameria Viteri","Senior Strategist & Advisor","advisor"),
("Dr Rose Wishall Ediger","Senior Advisor & Mentor","advisor,mentor"),
("Dr Ken Dunn MBE","Entrepreneur / Trainer","mentor"),
("Patience Musalia","Executive Assistant to CEO","employee"),
("Mr Felix Shyaba","CSR Manager","employee"),
("Dr Gloria Maimela","Senior Mentor","mentor"),
("Dr Sammy Khagai","Senior Mentor","mentor"),
("Dr Isiomi Igweike","Senior Mentor","mentor"),
("Dan Oginga","HR","employee"),
("Dr Dora Oduor","Senior Mentor","mentor"),
("Dr Dinah Makuba Kassaman","Senior Mentor","mentor"),
("Prof Caroline Mulinya","Senior Mentor","mentor"),
("Claire Wiraka","Knowledge Translation","employee"),
("Cheryl Matilda Shirwatso","Social Media Assistant","employee"),
("John Njoroge","Website Manager","employee"),
("Moses Masika Wamukota","Lead Ambassador & Researcher","ambassador,researcher"),
("Tsion Mekonen Hailu","Lead Ambassador — Ethiopia; Social Media Manager","ambassador,employee"),
("Annastacia Kimani","Regional Ambassador — Ukambani","ambassador"),
("Anastasha Cherotich","Regional Ambassador — South Rift","ambassador"),
("Joram Joe Ihure Macharia","Regional Ambassador — Central Kenya","ambassador"),
("Emmanuel Lago","Regional Ambassador — Nyanza","ambassador"),
("Abdihakim Adan","Regional Ambassador — North Eastern","ambassador"),
("Jacob Kinyua Nderitu","Environmental Mentee","trainee"),
("Hedwick Nyangayi Matwang'a","Environmental Research Intern","intern,researcher"),
("Babra Shibichila","Environmental Mentee","trainee"),
("Achieng Regan Odero","Environmental Mentee — Nairobi","trainee"),
("Cynthia Mueni","Environmental Mentee — Ukambani","trainee"),
("Ronald Galileo Okang'a","Environmental Mentee — Western","trainee"),
("Mercy Muema","Environmental Mentee","trainee"),
("Ronald Nasiali","Environmental Mentee","trainee"),
]
PARTNERS = [
("University of Nairobi","university"),("Medical College of Wisconsin","university"),
("Men In Health","ngo"),("Eternal Flame Worldwide","ngo"),
("Kilifi County Health Department","government"),("Masinde Muliro University (MMUST)","university"),
("CHANCE Network","network"),("Busia County Health Department","government"),
("Ministry of Environment & Climate Change — Kilifi","government"),
]
CONTENT = [
("programme","research-capacity-building","Research Capacity Building","Weekly training for early-career researchers in methods, systematic reviews, grant writing, data synthesis and research ethics."),
("programme","healthcare-worker-training","Healthcare Worker Training","Monthly training equipping frontline health workers to understand and respond to climate-driven health challenges."),
("programme","youth-climate-stewardship","Youth Climate Stewardship","School students mentored by trained youth peers on climate literacy, tree planting and environmental action."),
("programme","indigenous-knowledge-transfer","Indigenous Knowledge Transfer","Preserving and amplifying traditional ecological wisdom as a cornerstone of climate adaptation and resilience."),
("training_track","early-career-researchers","Early Career Researchers","Weekly workshops covering research methods, study design, systematic reviews, data management, evidence synthesis, grant writing and research ethics."),
("training_track","healthcare-workers","Healthcare Workers","Monthly workshops on climate and health, heat impacts, extreme weather, service delivery, resilience and climate stress."),
("training_track","youth-climate-stewards","Youth Climate Stewards","Weekly workshops on climate science, environmental stewardship, restoration, peer mentorship and community engagement."),
("initiative","youth-research-fellowship","Youth Research Fellowship","US$7,000 fellowship supporting an early-career researcher through a year of mentorship, training and a first peer-reviewed publication."),
("initiative","school-climate-stewardship","School Climate Stewardship","US$1,000–5,000 initiative supporting weekly climate workshops and tree-planting drives; website states 500 children per school and 1,000 trees per term."),
("initiative","healthcare-training-initiative","Healthcare Worker Training","US$4,000–10,000 initiative to train healthcare-worker cohorts; the website describes 20 workers trained and service to 5,000+ patients."),
("initiative","global-youth-science-network","Global Youth Science Network","US$5,000–10,000 initiative connecting 15 youth ambassadors across four countries through networking and international collaboration."),
("research_area","climate-health","Climate and Health","Research at the intersection of climate and health."),
("research_area","maternal-health","Maternal Health","Research focused on maternal health."),
("research_area","youth-health","Youth Health","Research focused on youth health."),
("research_area","climate-science","Climate Science","Climate science and environmental research."),
("research_area","community-engagement","Community Engagement","Community-engaged research and implementation."),
("research_area","ageing","Ageing","Research on ageing and related health outcomes."),
("impact_metric","youth-trained","100+ youth trained","Website-reported claim; verify before publication."),
("impact_metric","children-reached","4,000+ children reached","Website-reported claim; verify before publication."),
("impact_metric","publications","12 publications","Website-reported total; all 12 entries currently listed on the website are loaded below."),
("impact_metric","youth-mentored","35+ youth mentored","Website-reported claim for systematic data synthesis; verify before publication."),
("impact_metric","trees-planted","40,000+ trees planted","Website-reported claim; verify before publication."),
]


# Stable CMS story cards used by the public homepage. These records are reconciled
# on every demo seed so the homepage never depends on scraped heading slugs.
STORY = [
    (
        "website-we-are-on-a-mission",
        "Our Mission",
        "We empower young people to lead climate research, policy and community action. We connect youth with communities, educators, civil society and decision-makers so that local knowledge and youth voices help shape practical, equitable climate solutions.",
        "Build youth capacity in climate research, climate literacy and community action through training, peer mentorship, collaborative research and the communication of evidence.",
    ),
    (
        "website-we-have-a-vision",
        "Our Vision",
        "A future in which young people lead bold, inclusive climate action—from local initiatives to global platforms—and communities generate evidence, transform behaviours and co-create sustainable solutions rooted in their lived realities.",
        "A regenerative and climate-resilient world shaped by youth leadership, community knowledge and intergenerational collaboration.",
    ),
    (
        "website-our-approach",
        "Our Approach",
        "We combine research capacity building, climate and health learning, peer mentorship, community engagement and nature-based action. We work alongside educators, researchers and local communities, connecting scientific evidence with lived experience and practical action.",
        "Train and mentor emerging researchers and youth; strengthen climate literacy; support community-led environmental action; and share research and learning so that evidence can inform decisions.",
    ),
    (
        "website-our-logic",
        "How We Create Change",
        "Our model links knowledge to action: build skills and confidence, connect people through mentorship and partnerships, generate and share evidence, then support communities to apply that knowledge through locally relevant climate and health initiatives.",
        "Research and learning strengthen people; empowered people work with communities; community action generates experience and evidence; shared evidence informs better practice and policy.",
    ),
]


PUBLICATIONS = [
("aware-but-unprepared-healthcare-workers-africa","Aware but unprepared: climate change impacts on healthcare workers in Africa — a scoping review","Lusambili A et al. · Frontiers in Public Health · 13, 1693703","https://doi.org/10.3389/fpubh.2025.1693703"),
("youth-inclusive-climate-health-research","Towards youth-inclusive strategies for climate change and health research in sub-Saharan Africa","Lusambili AM et al. · Journal of Climate Change and Health · 22, 100418","https://doi.org/10.1016/j.joclim.2025.100418"),
("seniors-climate-seasonality-busia-kilifi","Climate seasonality and health of older adults in rural Busia and Kilifi, Kenya: SENIORS study","Shumba CS et al. · BMJ Open · 15(10), e103956","https://doi.org/10.1136/bmjopen-2025-103956"),
("ten-new-insights-climate-science-2024","Ten new insights in climate science 2024","Schaeffer R et al. · One Earth · 8(6)","https://doi.org/10.1016/j.oneear.2025.101285"),
("extreme-heat-pregnant-women-infants-kilifi","Reducing extreme heat impacts on pregnant women and infants: community intervention in Kilifi, Kenya","Lusambili A et al. · Health Policy and Planning · 40(9), 943–954","https://doi.org/10.1093/heapol/czaf028"),
("heat-weather-warnings-pregnant-postpartum-kilifi","Community perspectives of heat and weather warnings for pregnant and postpartum women in Kilifi, Kenya","Lusambili A et al. · PLOS ONE · 19(11), e0313781","https://doi.org/10.1371/journal.pone.0313781"),
("art-adherence-barriers-nairobi","Socio-ecological barriers to ART adherence: qualitative insights from Nairobi’s informal settlements","Muhenje O et al. · Frontiers in Public Health · 13, 1650966","https://doi.org/10.3389/fpubh.2025.1650966"),
("art-adherence-young-adults-kibera","Resilient in adversity: ART adherence interventions among young adults in Kibera, Nairobi","Muhenje O et al. · PLOS ONE · 21(3), e0322823","https://doi.org/10.1371/journal.pone.0322823"),
("too-hot-to-thrive-postpartum-kilifi","Too hot to thrive: community perspectives on high ambient temperature for postpartum women in Kilifi","Lusambili A et al. · BMC Pediatrics · 24(1), 36","https://doi.org/10.1186/s12887-023-04517-w"),
("mothers-get-really-exhausted-pregnancy-heat","‘Mothers get really exhausted!’ Lived experience of pregnancy in extreme heat: Kilifi, Kenya","Scorgie F et al. · Social Science & Medicine · 335, 116223","https://doi.org/10.1016/j.socscimed.2023.116223"),
("community-codesign-heat-exposure-kilifi","Community co-design workshop on reducing heat exposure impacts on pregnant and postpartum women and newborns in Kilifi, Kenya","Lusambili A et al. · Frontiers in Public Health · 11, 1146048","https://doi.org/10.3389/fpubh.2023.1146048"),
("dehydration-pregnant-women-newborns-rural-kenya","Awareness and interventions to reduce dehydration in pregnant women and newborns in rural Kenya","Lusambili A, Nakstad B · African Journal of Primary Health Care & Family Medicine · 15(1), e1–e3","https://doi.org/10.4102/phcfm.v15i1.3991"),
]


async def seed(slug: str) -> None:
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await session.scalar(select(Organization).where(Organization.slug == slug))
        if org is None:
            raise SystemExit(f"Organisation {slug!r} not found. Create it in the portal first.")
        actor = org.owner_user_id
        people_images, gallery_images = _public_media()
        for name, position, kinds in PEOPLE:
            person = await session.scalar(select(OrganizationPerson).where(
                OrganizationPerson.organization_id == org.id, OrganizationPerson.full_name == name
            ))
            if person is None:
                person = OrganizationPerson(
                    organization_id=org.id, full_name=name, positions=[x.strip() for x in position.split(";")],
                    person_types=kinds.split(","), country_code="KE",
                    profile_image_url=people_images.get(_normalise_name(name)),
                    source_url=SOURCE,
                    source_label="NextGen For Earth public website", review_state="verified",
                    visibility="public", status="active", created_by=actor, updated_by=actor,
                )
                session.add(person)
            else:
                person.positions = [x.strip() for x in position.split(";")]
                person.person_types = kinds.split(",")
                person.profile_image_url = people_images.get(_normalise_name(name))
                person.review_state, person.visibility, person.status = "verified", "public", "active"
                person.source_url, person.source_label, person.updated_by = SOURCE, "NextGen For Earth public website", actor
        for name, kind in PARTNERS:
            partner = await session.scalar(select(InstitutionalPartner).where(
                InstitutionalPartner.organization_id == org.id, InstitutionalPartner.name == name
            ))
            if partner is None:
                partner = InstitutionalPartner(
                    organization_id=org.id, name=name, partner_type=kind, country_code="KE",
                    source_url=SOURCE, source_label="NextGen For Earth public website",
                    relationship_status="prospect", verification_state="pending", visibility="public",
                    created_by=actor, updated_by=actor,
                )
                session.add(partner)
            else:
                partner.visibility = "public"
                partner.source_url, partner.source_label, partner.updated_by = SOURCE, "NextGen For Earth public website", actor

        legacy_tracks = {
            "research-methods": ("early-career-researchers", "Early Career Researchers", "Weekly research methods, systematic review, data synthesis, grant writing and ethics workshops."),
            "healthcare-training": ("healthcare-workers", "Healthcare Workers", "Monthly climate-health training for frontline healthcare workers."),
            "climate-stewardship-training": ("youth-climate-stewards", "Youth Climate Stewards", "Weekly climate science, stewardship, restoration and peer-mentorship workshops."),
        }
        for old_slug, (new_slug, new_title, new_summary) in legacy_tracks.items():
            legacy = await session.scalar(select(PublicContentEntry).where(
                PublicContentEntry.organization_id == org.id,
                PublicContentEntry.content_type == "training_track",
                PublicContentEntry.slug == old_slug,
            ))
            if legacy is not None:
                new_exists = await session.scalar(select(PublicContentEntry.id).where(
                    PublicContentEntry.organization_id == org.id,
                    PublicContentEntry.content_type == "training_track",
                    PublicContentEntry.slug == new_slug,
                ))
                if new_exists is None:
                    legacy.slug = new_slug
                    legacy.title = new_title
                    legacy.summary = new_summary
                else:
                    legacy.publication_state = "archived"
                legacy.updated_by = actor

        now = datetime.now(UTC)
        # Keep media references in the public CMS feed in sync with files shipped
        # in web/public. Without this record, the static images exist but the
        # homepage gallery has no published image list to render.
        gallery_entry = await session.scalar(select(PublicContentEntry).where(
            PublicContentEntry.organization_id == org.id,
            PublicContentEntry.content_type == "page",
            PublicContentEntry.slug == "website-gallery",
        ))
        gallery_metadata = {
            "gallery": gallery_images,
            "source_status": "source-attributed public website media; confirm reuse rights",
            "source_capture": SOURCE,
        }
        if gallery_entry is None:
            session.add(PublicContentEntry(
                organization_id=org.id, content_type="page", slug="website-gallery",
                title="In the field — gallery",
                summary="Photographs from NextGen for Earth research, training and community activities.",
                body="Images are maintained as organisation website assets and displayed from the public media catalogue.",
                metadata_json=gallery_metadata, publication_state="published",
                source_url=SOURCE, source_label="NextGen For Earth public website",
                created_by=actor, updated_by=actor,
                approved_by=actor, approved_at=now, published_at=now,
            ))
        else:
            gallery_entry.title = "In the field — gallery"
            gallery_entry.summary = "Photographs from NextGen for Earth research, training and community activities."
            gallery_entry.body = "Images are maintained as organisation website assets and displayed from the public media catalogue."
            gallery_entry.metadata_json = {**(gallery_entry.metadata_json or {}), **gallery_metadata}
            gallery_entry.publication_state = "published"
            gallery_entry.source_url = SOURCE
            gallery_entry.source_label = "NextGen For Earth public website"
            gallery_entry.approved_by, gallery_entry.approved_at, gallery_entry.published_at = actor, now, now
            gallery_entry.updated_by = actor

        for kind, item_slug, title, summary in CONTENT:
            entry = await session.scalar(select(PublicContentEntry).where(
                PublicContentEntry.organization_id == org.id,
                PublicContentEntry.content_type == kind, PublicContentEntry.slug == item_slug,
            ))
            activity_images = {
                "youth-research-fellowship": "/media/nextgen-source/programme-research-capacity.jpg",
                "school-climate-stewardship": "/media/nextgen-source/programme-youth-stewardship.jpg",
                "healthcare-training-initiative": "/media/nextgen-source/programme-healthcare-workers.jpg",
                "global-youth-science-network": "/media/nextgen-source/gallery-early-career.jpg",
                "early-career-researchers": "/media/nextgen-source/programme-research-capacity.jpg",
                "healthcare-workers": "/media/nextgen-source/programme-healthcare-workers.jpg",
                "youth-climate-stewards": "/media/nextgen-source/programme-youth-stewardship.jpg",
            }
            source_metadata = {
                "source_status": "transcribed from the organisation's existing public website; not independently verified",
                "source_capture": SOURCE,
            }
            if kind in {"initiative", "training_track"} and item_slug in activity_images:
                source_metadata["image_url"] = activity_images[item_slug]
            if entry is None:
                entry = PublicContentEntry(
                    organization_id=org.id, content_type=kind, slug=item_slug, title=title,
                    summary=summary, metadata_json=source_metadata,
                    publication_state="published", source_url=SOURCE,
                    source_label="NextGen For Earth public website", created_by=actor, updated_by=actor,
                    approved_by=actor, approved_at=now, published_at=now,
                )
                session.add(entry)
            else:
                entry.title, entry.summary = title, summary
                entry.metadata_json = {**(entry.metadata_json or {}), **source_metadata}
                entry.source_url = SOURCE
                entry.source_label = "NextGen For Earth public website"
                entry.publication_state = "published"
                entry.approved_by, entry.approved_at, entry.published_at = actor, now, now
                entry.updated_by = actor

        for item_slug, title, summary, body in STORY:
            entry = await session.scalar(select(PublicContentEntry).where(
                PublicContentEntry.organization_id == org.id,
                PublicContentEntry.content_type == "page",
                PublicContentEntry.slug == item_slug,
            ))
            now = datetime.now(UTC)
            if entry is None:
                entry = PublicContentEntry(
                    organization_id=org.id, content_type="page", slug=item_slug,
                    title=title, summary=summary, body=body,
                    metadata_json={
                        "source_status": "organisation_public_website_and_mission_summary",
                        "source_capture": SOURCE,
                        "homepage_section": "nextgen_story",
                    },
                    publication_state="published", source_url=SOURCE,
                    source_label="NextGen For Earth public website",
                    created_by=actor, updated_by=actor,
                    approved_by=actor, approved_at=now, published_at=now,
                )
                session.add(entry)
            else:
                entry.title, entry.summary, entry.body = title, summary, body
                entry.metadata_json = {
                    **(entry.metadata_json or {}),
                    "source_status": "organisation_public_website_and_mission_summary",
                    "source_capture": SOURCE,
                    "homepage_section": "nextgen_story",
                }
                entry.publication_state = "published"
                entry.source_url, entry.source_label = SOURCE, "NextGen For Earth public website"
                entry.approved_by, entry.approved_at, entry.published_at = actor, now, now
                entry.updated_by = actor

        for item_slug, title, summary, doi in PUBLICATIONS:
            entry = await session.scalar(select(PublicContentEntry).where(
                PublicContentEntry.organization_id == org.id,
                PublicContentEntry.content_type == "publication",
                PublicContentEntry.slug == item_slug,
            ))
            publication_metadata = {
                "source_status": "listed on the organisation's public website",
                "source_capture": SOURCE,
            }
            if entry is None:
                entry = PublicContentEntry(
                    organization_id=org.id, content_type="publication", slug=item_slug,
                    title=title, summary=summary,
                    metadata_json=publication_metadata,
                    publication_state="published", source_url=doi,
                    source_label="NextGen For Earth publication listing",
                    created_by=actor, updated_by=actor,
                    approved_by=actor, approved_at=now, published_at=now,
                )
                session.add(entry)
            else:
                entry.title, entry.summary = title, summary
                entry.metadata_json = {**(entry.metadata_json or {}), **publication_metadata}
                entry.publication_state = "published"
                entry.source_url, entry.source_label = doi, "NextGen For Earth publication listing"
                entry.approved_by, entry.approved_at, entry.published_at = actor, now, now
                entry.updated_by = actor

        for title, item_slug, summary in [
            ("Research Capacity Building","research-capacity-building","Research capacity building."),
            ("Healthcare Worker Training","healthcare-worker-training","Healthcare worker training."),
            ("Youth Climate Stewardship","youth-climate-stewardship","Youth climate stewardship."),
            ("Indigenous Knowledge Transfer","indigenous-knowledge-transfer","Indigenous knowledge transfer."),
        ]:
            programme = await session.scalar(select(Programme).where(
                Programme.organization_id == org.id, Programme.slug == item_slug
            ))
            if programme is None:
                programme = Programme(
                    organization_id=org.id, title=title, slug=item_slug, summary=summary,
                    status="planned", created_by=actor,
                )
                session.add(programme)
            else:
                programme.title, programme.summary = title, summary
                if programme.status == "draft":
                    programme.status = "planned"
        curriculum = json.loads(
            (ROOT / "scripts" / "data" / "nextgen_curriculum_content.json").read_text(
                encoding="utf-8"
            )
        )
        course_specs = curriculum["courses"]
        for course_spec in course_specs:
            programme = await session.scalar(select(Programme).where(
                Programme.organization_id == org.id,
                Programme.slug == course_spec["programme_slug"],
            ))
            course = await session.scalar(select(LearningCourse).where(
                LearningCourse.organization_id == org.id,
                LearningCourse.slug == course_spec["slug"],
            ))
            if course is None:
                course = LearningCourse(
                    organization_id=org.id,
                    programme_id=programme.id if programme else None,
                    title=course_spec["title"],
                    slug=course_spec["slug"],
                    description=course_spec["description"],
                    category=course_spec["category"],
                    delivery_mode="blended",
                    status="published",
                    created_by=actor,
                )
                session.add(course)
                await session.flush()
            else:
                course.title = course_spec["title"]
                course.description = course_spec["description"]
                course.category = course_spec["category"]
                course.status = "published"
                if programme is not None:
                    course.programme_id = programme.id

            for module_position, module_spec in enumerate(course_spec["modules"], start=1):
                module = await session.scalar(select(LearningModule).where(
                    LearningModule.course_id == course.id,
                    LearningModule.position == module_position,
                ))
                if module is None:
                    module = LearningModule(
                        course_id=course.id,
                        title=module_spec["title"],
                        description=module_spec["description"],
                        position=module_position,
                    )
                    session.add(module)
                    await session.flush()
                else:
                    module.title = module_spec["title"]
                    module.description = module_spec["description"]

                for lesson_position, lesson_spec in enumerate(module_spec["lessons"], start=1):
                    lesson = await session.scalar(select(LearningLesson).where(
                        LearningLesson.module_id == module.id,
                        LearningLesson.position == lesson_position,
                    ))
                    if lesson is None:
                        lesson = LearningLesson(
                            module_id=module.id,
                            title=lesson_spec["title"],
                            content_type="text",
                            content=lesson_spec["content"],
                            resource_url=lesson_spec.get("resource_url"),
                            duration_minutes=lesson_spec["duration_minutes"],
                            position=lesson_position,
                        )
                        session.add(lesson)
                    else:
                        lesson.title = lesson_spec["title"]
                        lesson.content_type = "text"
                        lesson.content = lesson_spec["content"]
                        lesson.resource_url = lesson_spec.get("resource_url")
                        lesson.duration_minutes = lesson_spec["duration_minutes"]

            assessment_spec = course_spec["assessment"]
            assessment = await session.scalar(select(LearningAssessment).where(
                LearningAssessment.course_id == course.id,
                LearningAssessment.title == assessment_spec["title"],
            ))
            configuration = {"questions": assessment_spec["questions"]}
            if assessment is None:
                assessment = LearningAssessment(
                    course_id=course.id,
                    title=assessment_spec["title"],
                    assessment_type="quiz",
                    instructions=assessment_spec["instructions"],
                    configuration=configuration,
                    pass_mark=assessment_spec["pass_mark"],
                    created_by=actor,
                )
                session.add(assessment)
            else:
                assessment.instructions = assessment_spec["instructions"]
                assessment.configuration = configuration
                assessment.pass_mark = assessment_spec["pass_mark"]
        await session.commit()
        print(f"Loaded {len(PEOPLE)} people, {len(PARTNERS)} partners, {len(CONTENT) + len(PUBLICATIONS) + len(STORY)} CMS entries including {len(PUBLICATIONS)} publications, four programmes and {len(course_specs)} published learning courses with reviewed pilot lesson content.")
    await engine.dispose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--organization-slug", required=True)
    asyncio.run(seed(parser.parse_args().organization_slug))

# fmt: on
