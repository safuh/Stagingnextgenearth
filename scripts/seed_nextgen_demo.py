# ruff: noqa: E501, I001
# fmt: off
"""Idempotently seed a reviewable NextGen for Earth demo catalogue."""
import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.core.config import get_settings
from stagingnextgenearth.platform.models import (
    InstitutionalPartner, Organization, OrganizationPerson, Programme, PublicContentEntry,
)

SOURCE = "https://nextgenforearth.org/"
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
        for name, position, kinds in PEOPLE:
            exists = await session.scalar(select(OrganizationPerson.id).where(
                OrganizationPerson.organization_id == org.id, OrganizationPerson.full_name == name
            ))
            if exists is None:
                session.add(OrganizationPerson(
                    organization_id=org.id, full_name=name, positions=[x.strip() for x in position.split(";")],
                    person_types=kinds.split(","), country_code="KE", source_url=SOURCE,
                    source_label="NextGen For Earth public website", review_state="pending",
                    visibility="private", status="active", created_by=actor, updated_by=actor,
                ))
        for name, kind in PARTNERS:
            exists = await session.scalar(select(InstitutionalPartner.id).where(
                InstitutionalPartner.organization_id == org.id, InstitutionalPartner.name == name
            ))
            if exists is None:
                session.add(InstitutionalPartner(
                    organization_id=org.id, name=name, partner_type=kind, country_code="KE",
                    source_url=SOURCE, source_label="NextGen For Earth public website",
                    relationship_status="prospect", verification_state="pending", visibility="private",
                    created_by=actor, updated_by=actor,
                ))

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

        for kind, item_slug, title, summary in CONTENT:
            exists = await session.scalar(select(PublicContentEntry.id).where(
                PublicContentEntry.organization_id == org.id,
                PublicContentEntry.content_type == kind, PublicContentEntry.slug == item_slug,
            ))
            if exists is None:
                session.add(PublicContentEntry(
                    organization_id=org.id, content_type=kind, slug=item_slug, title=title,
                    summary=summary, metadata_json={"source_status": "website-listed; not independently verified"},
                    publication_state="draft", source_url=SOURCE,
                    source_label="NextGen For Earth public website", created_by=actor, updated_by=actor,
                ))

        for item_slug, title, summary, doi in PUBLICATIONS:
            exists = await session.scalar(select(PublicContentEntry.id).where(
                PublicContentEntry.organization_id == org.id,
                PublicContentEntry.content_type == "publication",
                PublicContentEntry.slug == item_slug,
            ))
            if exists is None:
                session.add(PublicContentEntry(
                    organization_id=org.id, content_type="publication", slug=item_slug,
                    title=title, summary=summary,
                    metadata_json={"source_status": "listed on the public website"},
                    publication_state="draft", source_url=doi,
                    source_label="NextGen For Earth publication listing",
                    created_by=actor, updated_by=actor,
                ))

        for title, item_slug, summary in [
            ("Research Capacity Building","research-capacity-building","Research capacity building."),
            ("Healthcare Worker Training","healthcare-worker-training","Healthcare worker training."),
            ("Youth Climate Stewardship","youth-climate-stewardship","Youth climate stewardship."),
            ("Indigenous Knowledge Transfer","indigenous-knowledge-transfer","Indigenous knowledge transfer."),
        ]:
            exists = await session.scalar(select(Programme.id).where(
                Programme.organization_id == org.id, Programme.slug == item_slug
            ))
            if exists is None:
                session.add(Programme(
                    organization_id=org.id, title=title, slug=item_slug, summary=summary,
                    status="draft", created_by=actor,
                ))
        await session.commit()
        print(f"Loaded {len(PEOPLE)} people, {len(PARTNERS)} partners, {len(CONTENT) + len(PUBLICATIONS)} CMS entries including {len(PUBLICATIONS)} publications, and four programme records.")
    await engine.dispose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--organization-slug", required=True)
    asyncio.run(seed(parser.parse_args().organization_slug))

# fmt: on
