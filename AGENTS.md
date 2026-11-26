# Repository agent instructions

All coding agents and LLM-assisted contributors must read and follow [docs/LLM_DEVELOPMENT_GUIDE.md](docs/LLM_DEVELOPMENT_GUIDE.md) before changing application code, tests, migrations, configuration or product documentation.

The current product priorities, feature acceptance criteria and distinction between implemented, seeded, synthetic and production-accepted behaviour are maintained in [docs/PRODUCT_STATUS_AND_ROADMAP.md](docs/PRODUCT_STATUS_AND_ROADMAP.md).

For research and climate intelligence work, follow [docs/RESEARCH_AND_CLIMATE_INTELLIGENCE_BLUEPRINT.md](docs/RESEARCH_AND_CLIMATE_INTELLIGENCE_BLUEPRINT.md). For curriculum content, follow [docs/learning/NEXTGEN_CURRICULUM_BLUEPRINT.md](docs/learning/NEXTGEN_CURRICULUM_BLUEPRINT.md).

Never claim a feature is tested, deployed or accepted without the corresponding evidence. Preserve tenant isolation, API-side authorization, research governance, safeguarding and source provenance.


## Milestone completion and staging deployment

A milestone is complete only when its acceptance criteria, migration checks, backend tests, frontend type-check/lint/tests/build, security/authorization checks and presentation updates pass. Once a milestone is complete, deploy that exact commit to the designated Render staging services for live acceptance. Confirm the deployed commit SHA, deployment status, health endpoints and critical browser journeys before reporting it as deployed. Do not deploy a partial or failing milestone; do not report a deployment based only on a successful GitHub merge or CI run.

## UX and presentation quality

User-facing work must be responsive, accessible, information-dense without clutter, and visually coherent across public and authenticated experiences. Prefer strong editorial hierarchy, purposeful motion, clear data provenance, explicit empty/loading/error states, legible tables/charts, and deliberate visual contrast. Avoid generic admin-template layouts, decorative metrics without evidence, misleading live-status labels, and placeholder data presented as real. Update the founder presentation, short pitch and demo runbook whenever the user-visible product changes.
