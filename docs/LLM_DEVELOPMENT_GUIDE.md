# LLM and Coding-Agent Instructions — NextGen For Earth

These instructions apply to AI coding assistants, automated agents and human contributors working in this repository.

## 1. Mission and product priorities

Build NextGen For Earth as an organisational operating platform, not merely a public website. Connect people, roles, programmes, learning, research, climate intelligence, partners and impact evidence.

Current order of product priority:
1. Research intelligence workflows and presentation.
2. Complete, substantive curricula and learning-content workflows.
3. Founder/admin workspace.
4. Programme operations.
5. Assessments and learner progress.
6. Certificates.
7. Leadership impact dashboard.
8. Partner/funder reporting.
9. Production hardening continuously.

Do not let presentation polish displace workflow correctness, data provenance, security or operational reliability.

## 2. Source-of-truth hierarchy

When information conflicts, use this order:
1. Current code, migrations, tests and API contracts on the active branch.
2. Current operational documentation and acceptance evidence.
3. Product status and workflow specifications under `docs/`.
4. Source-attributed public website content and approved organisational records.
5. External provider documentation for provider-specific behaviour.
6. Inference, which must be labelled as a proposal rather than a fact.

Never treat a previous conversation summary, pitch slide, seeded record or website claim as proof that a feature is implemented or an impact figure is audited.

## 3. Required working method

Before changing a feature:
- Inspect the active branch and recent commit history.
- Read the relevant API route, model, migration, schemas, tests, frontend page and operational runbook.
- Identify existing patterns and reuse them; avoid parallel implementations.
- Confirm whether the feature is already present but missing UI, wiring, tests, configuration or acceptance.
- Define a narrow user journey and acceptance criteria.
- Preserve tenant isolation and role policy at the API boundary.
- Add/adjust tests before declaring completion.
- Update docs and demo materials in the same change set.
- Run relevant lint, typecheck, tests and frontend production build when the environment permits.
- Report commands not run and reasons; do not claim tests passed without actual output.

## 4. Architecture constraints

- Keep the modular monolith unless independent scaling/deployment is justified.
- FastAPI owns business rules and authorization.
- PostgreSQL/PostGIS owns durable relational and spatial state.
- Next.js provides public and authenticated experiences through the same-origin BFF.
- Do not put access/refresh tokens, provider secrets, storage credentials or private download URLs in browser storage or client code.
- Run migrations as explicit release operations, not automatically in each API worker.
- Keep long-running provider ingestion and scanning in dedicated durable workers.
- Use typed request/response schemas and bounded pagination.
- Use idempotency for external ingestion and repeatable seed operations.

## 5. Security, privacy and governance

- Every tenant-owned read and mutation must enforce organisation membership and role permissions server-side.
- UI role checks are for presentation only, never authorization.
- Preserve owner, last-admin, separation-of-duty and independent-review safeguards.
- Never let a dataset owner approve their own restricted submission.
- Keep private dataset metadata and object storage keys out of general lists.
- Files remain quarantined until the configured scanner returns a clean verdict.
- Use short-lived, authorised download grants and audit each grant.
- Do not expose participant-level health information or child PII in public reporting.
- Before enrolling minors, require safeguarding review, age-appropriate assent and guardian consent where required.
- Do not publish community/Indigenous knowledge without the relevant community permissions and agreed attribution/use terms.
- Never commit credentials, real secrets, production personal data or private demo invitation URLs.

## 6. Research workflow rules

Treat research as a governed lifecycle:
`concept → protocol → active → completed → published → archived`.

- Study creation starts at concept; it does not activate a study.
- Protocol approval and required ethics/safeguarding decisions are prerequisites to activation.
- Preserve proposal/protocol versions and append-only review history.
- External literature metadata is a discovery/enrichment source, not evidence of organisational ownership or authorship.
- Use DOI/ORCID/provider identifiers for reconciliation where available; ambiguous matches require human review.
- Preserve raw provider metadata, source URL, retrieval time and selected-field import decisions.
- Dataset ingestion is not dataset approval.
- Analysis outputs must identify exact dataset versions, parameters, software and checksums.
- Distinguish descriptive analysis from inference and causal attribution.
- Cite external research and climate providers in exported outputs.

## 7. Climate intelligence rules

The product must combine provider-backed data and organisation field observations. Initial adapters include NASA POWER and CHIRPS; Copernicus ERA5 has optional adapter code and requires deployment configuration and dataset terms acceptance. World Bank CCKP, ICPAC and NASA GPM are candidates for future adapters, not implemented features.

- Provider names, variables, units, coverage, cadence, licence and operational status must be explicit.
- Record request geometry, time range, provider product/version, source, retrieval time and transformations.
- Keep station observations, satellite estimates, reanalysis and model projections distinct.
- Preserve native values and units; conversions must be documented.
- Missing data stays missing unless a documented method explicitly handles it.
- Pending field observations are provisional; require independent quality review.
- Never infer a continuous spatial surface from point observations without an explicit validated method.
- Never claim causal attribution from descriptive summaries.
- Large provider jobs must be durable background tasks with retry, cancellation, quotas and idempotency.
- If a provider is unavailable, display its status and last successful run; do not fabricate values.

## Public climate intelligence publication boundary

The public website must include a dedicated climate intelligence hub at `/climate-intelligence`. Follow [PUBLIC_CLIMATE_INTELLIGENCE.md](PUBLIC_CLIMATE_INTELLIGENCE.md) for the public API, publication workflow and acceptance criteria.

- Do not expose `ClimateObservation` rows directly through anonymous endpoints.
- A verified observation is not automatically public. Explicit release approval and publication are separate governance states.
- Public climate responses must be sourced from published, versioned release records with immutable lineage and public-safe schemas.
- Public endpoints are anonymous GET-only, organisation-scoped, bounded, rate-limited and cacheable. Never expose credentials, private provider errors, raw metadata, participant data, restricted dataset paths or sensitive coordinates.
- Keep in-situ observations, satellite estimates, reanalysis, forecasts, projections and synthetic demo data distinct.
- Every public chart/map must disclose source/product, data class, unit, geography/resolution, time period, baseline, missingness, method, uncertainty/limitations, licence and retrieval/update time.
- Require a different authorised reviewer for release approval; author self-approval is prohibited.
- Retraction must remove the release from public responses while preserving audit/version history.
- If no approved release exists or a provider is unavailable, show an honest no-data/stale state. Never fabricate a public value.

### Climate Studio UX and workflow

The authenticated Climate Studio is the browser workflow for bounded provider ingestion, ingestion history, sample inspection, independent batch quality review and versioned public release governance. Keep the public hub and authenticated studio on one provenance model but separate their permissions and presentation. The public experience is editorial and evidence-led; the research studio is an operational dark interface. Both require responsive layouts, keyboard-visible focus, semantic labels, accessible tables, loading/error/empty states and reduced-motion support.

A batch review is an explicit reviewer decision over every pending observation in one provider run. Explain the batch scope before confirmation and preserve per-observation audit events. A provider run is eligible for a release only when every inserted observation is verified by a reviewer other than its submitter and a provider licence is recorded.

## 8. Curriculum and learning rules

The default staging demo seed contains four published pilot tracks, 28 modules and 86 substantive lessons, with four formative quizzes and four private staff authoring drafts and official further-reading links. The material is a subject-matter review pilot, not accredited training, clinical guidance or ethics approval.

Use `docs/learning/NEXTGEN_CURRICULUM_BLUEPRINT.md` as the proposed initial content design:
- Research Methods and Evidence Practice.
- Climate and Health Resilience.
- Youth Climate Stewardship and Community Action.
- Indigenous and Community Knowledge for Climate Resilience.

Before cohort delivery, obtain research, clinical, safeguarding, accessibility and community-lead review as appropriate. Improve the pilot using reviewer feedback, confirm local applicability and verify all source links and reuse permissions. Course completion requires explicit criteria; certificates must not imply accreditation or professional licensure unless formally approved.

## 9. Demo and presentation integrity

Use the following labels consistently:
- Website import.
- External provider.
- Organisation record.
- Synthetic demo.
- Pending review.
- Verified.

Never:
- present synthetic ODK data as live ODK Central data;
- present a configured provider as returning live data without a successful run;
- present a public website metric as audited impact;
- present website-listed partners as verified agreements;
- present public directory entries as active portal accounts;
- present a draft course as an approved curriculum;
- present a code path as production-accepted without test evidence.

Keep `docs/PRODUCT_STATUS_AND_ROADMAP.md`, `docs/RESEARCH_AND_CLIMATE_INTELLIGENCE_BLUEPRINT.md`, `docs/FOUNDER_DEMONSTRATION.md`, `docs/FOUNDER_PRESENTATION.md` and `docs/pitch/DEMO_PITCH.md` aligned with the current build.

## 10. Completion report format

For each work item report:
1. User-visible change.
2. API/data changes and migrations.
3. Security/authorization impact.
4. Tests run and exact outcome.
5. Deployment/configuration requirements.
6. Documentation updated.
7. Known limitations and follow-up acceptance work.

Use “implemented” only for code present, “tested” only for checks actually run, “deployed” only after deployment confirmation, and “accepted” only after the relevant user journey passes.


## Public climate editorial insight rules

- Treat `climate_insight` as a governed CMS content type, not a free-form public blog post.
- Every public climate insight must link to a currently published climate release and a separately published research publication in the same organisation.
- Never infer or write a causal climate-health claim from co-location or temporal overlap alone.
- State geography, indicator and evidence limitations in the editorial record.
- A release retraction or unpublication must remove linked insights from the anonymous public endpoint.
- Keep internal review notes and arbitrary CMS metadata out of public responses; only explicitly allow-listed fields may be exposed.
- If no eligible evidence pair exists, retain the public empty state rather than seeding an example insight.


## Learning content authoring and safeguarding

- Treat `scripts/data/nextgen_curriculum_content.json` as versioned pilot content, not as an accreditation standard.
- Keep each lesson outcome, explanation, applied practice and self-check explicit; link to authoritative source material through `resource_url`.
- Do not present general climate-health material as diagnosis or clinical protocols. Defer to current national and facility guidance.
- Youth learning activities require age-appropriate consent, adult supervision and organisation-approved safeguarding procedures.
- Indigenous/community knowledge content must prioritise community authority, prior informed consent, knowledge sovereignty, minimisation and benefit-sharing. Never seed or publish restricted community knowledge as example data.
- Keep the pilot label visible until subject-matter, clinical, research, safeguarding and community leads approve the relevant material.
- The Render API container currently runs `scripts/seed_nextgen_demo.py --organization-slug next-gen-for-earth-demo` on startup after migrations. This is a staging demo bootstrap, not a production content workflow: it overwrites managed demo lesson and quiz content from the versioned JSON catalogue. Do not add startup seeding for staff-authored production content or other tenants without an explicit, reviewed migration/seed design.
