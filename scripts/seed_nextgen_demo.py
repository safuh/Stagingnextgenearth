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
("programme","research-capacity-building","Research Capacity Building","Research capability and locally relevant research."),
("programme","healthcare-worker-training","Healthcare Worker Training","Capacity strengthening for healthcare workers."),
("programme","youth-climate-stewardship","Youth Climate Stewardship","Youth-led climate stewardship and environmental action."),
("programme","indigenous-knowledge-transfer","Indigenous Knowledge Transfer","Intergenerational knowledge exchange and community learning."),
("training_track","research-methods","Research Methods Training","Research skills and methods training."),
("training_track","healthcare-training","Healthcare Worker Training Track","Professional development for healthcare workers."),
("training_track","climate-stewardship-training","Climate Stewardship Training","Climate and environmental stewardship learning."),
("initiative","youth-research-fellowship","Youth Research Fellowship","Support young researchers and emerging leaders."),
("initiative","school-climate-stewardship","School Climate Stewardship","Support school-based climate stewardship."),
("initiative","healthcare-training-initiative","Healthcare Worker Training","Support training for healthcare workers."),
("initiative","global-youth-science-network","Global Youth Science Network","Connect young people through science."),
("research_area","climate-health","Climate and Health","Research at the intersection of climate and health."),
("research_area","maternal-health","Maternal Health","Research focused on maternal health."),
("research_area","youth-health","Youth Health","Research focused on youth health."),
("research_area","climate-science","Climate Science","Climate science and environmental research."),
("research_area","community-engagement","Community Engagement","Community-engaged research and implementation."),
("research_area","ageing","Ageing","Research on ageing and related health outcomes."),
("impact_metric","youth-trained","100+ youth trained","Website-reported claim; verify before publication."),
("impact_metric","children-reached","4,000+ children reached","Website-reported claim; verify before publication."),
("impact_metric","publications","12 publications","Website-reported total; 10 individually identifiable entries were extracted."),
("impact_metric","trees-planted","40,000+ trees planted","Website-reported claim; verify before publication."),
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
        print(f"Loaded {len(PEOPLE)} people, {len(PARTNERS)} partners, {len(CONTENT)} CMS entries and four programme records.")
    await engine.dispose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--organization-slug", required=True)
    asyncio.run(seed(parser.parse_args().organization_slug))
