# Product readiness and presentation index

Use this index to keep implementation, acceptance and external presentation aligned.

## Product planning and status
- [Product status and priority roadmap](PRODUCT_STATUS_AND_ROADMAP.md)
- [Research and climate intelligence workflow blueprint](RESEARCH_AND_CLIMATE_INTELLIGENCE_BLUEPRINT.md)
- [Initial four-track curriculum blueprint](learning/NEXTGEN_CURRICULUM_BLUEPRINT.md)
- [Substantive curriculum pilot source data](../scripts/data/nextgen_curriculum_content.json)
- Four-track seed command: `python scripts/seed_nextgen_demo.py --organization-slug nextgen-for-earth` (run explicitly; not part of deployment)
- [LLM and coding-agent instructions](LLM_DEVELOPMENT_GUIDE.md)

- [Public climate intelligence product/API specification](PUBLIC_CLIMATE_INTELLIGENCE.md)
- Authenticated Climate Studio: `web/app/workspace/research/climate/page.tsx`
- Public climate experience: `web/app/climate-intelligence/`
- Research-linked climate insights: moderated CMS records linked to a published release and publication.

## Founder and partner presentation
- [Updated founder presentation](FOUNDER_PRESENTATION.md)
- [Seven-minute founder demo runbook](pitch/DEMO_RUNBOOK_7_MIN.md)
- [Short demo pitch](pitch/DEMO_PITCH.md)
- [Extended founder demonstration and handover](FOUNDER_DEMONSTRATION.md)
- [Staging and founder acceptance checklist](operations/founder-demo-acceptance.md)

## Operational references
- [Research workspace operations](operations/research-workspace.md)
- [Research governance](operations/research-governance.md)
- [Climate provider ingestion](operations/climate-provider-ingestion.md)
- [Learning management](operations/learning-management.md)
- [Database backup and restore](operations/database-backup-restore.md)

## Status language

- **Implemented:** code is present in the active branch.
- **Tested:** relevant tests/checks were executed and passed.
- **Deployed:** a deployment for the identified commit completed successfully.
- **Accepted:** the complete user journey passed in the target environment.
- **Seeded:** demonstration or imported records exist; this does not imply verification.
- **Synthetic demo:** generated fixture data, not live provider or field data.
