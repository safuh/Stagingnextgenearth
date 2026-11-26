# NextGen For Earth — Product Status, Priorities and Acceptance Roadmap

**Working baseline:** `feat/admin-workspace-ui-polish-m116`  
**Roadmap branch:** `feat/research-curriculum-product-blueprint-m117`  
**Review date:** 26 November 2026

This document is the product-facing source of truth for what the repository currently implements, what is only seeded or demonstrated, and what remains to be accepted. A checked item means the implementation and its acceptance evidence have been verified; code presence or a successful build alone is not sufficient.

## Product proposition

NextGen For Earth is being developed as the organisation's digital operating platform: a public experience connected to governed internal workflows for people, programmes, learning, research, climate intelligence, partners and evidence of impact.

The public website communicates the mission. The authenticated workspace operates the organisation. Public claims must remain traceable to approved source records and evidence.

## Verified repository baseline

The feature branch already contains substantial backend and portal foundations:

- Organisation-scoped identity, memberships, role governance, invitations, ownership controls and audit history.
- Programmes, projects, activities, deliverables, goals, milestones, assignments, participation and volunteer workflows.
- Research study and dataset registries, proposals, versioned protocols, ethics review, collaborators, publications, dataset review, file versioning, quarantine/scanning, download grants, export manifests and analysis-run provenance.
- OpenAlex lookup/import and publication metadata refresh with provenance.
- Climate provider contracts and ingestion adapters for NASA POWER and CHIRPS v3; a Copernicus ERA5 adapter exists behind optional runtime dependencies and CDS configuration.
- Climate quality review, spatial/time filtering, descriptive statistics, screening/coverage reports and anomaly workflows.
- ODK Central connection configuration, form discovery/mapping, paginated OData sync, idempotency and sync history; live Central acceptance still requires a separately configured test Central account and worker.
- Learning course/module/lesson authoring, enrolment, assessments, progress, mentorship, attendance and certificate workflows.
- Public CMS, partner registry, people directory and role-specific portal foundations.
- FastAPI, PostgreSQL/PostGIS, Next.js, Docker and Render deployment architecture.

Repository documentation and tests establish implementation intent and local/CI coverage. They do not establish that every workflow is currently configured, populated or accepted on the live staging deployment.

## Important distinction: seeded versus production-quality content

The idempotent demo seed currently creates three published learning courses:
1. Early Career Researchers
2. Healthcare Workers
3. Youth Climate Stewards

It creates ordered modules and lessons, but lesson bodies are explicitly generic demo placeholders asking operators to add approved learning resources, facilitator notes and assessments. The seed does not yet provide a complete instructional curriculum. Indigenous Knowledge Transfer is a programme pillar but is not yet represented as a seeded course.

The seed also imports website-listed people, partners, programmes, publications and impact claims. These are source-attributed records, not proof of current employment, signed partner agreements, audited impact or scientific validation. Review and correct these records with organisational owners before using them as authoritative evidence.

## Priority 1 — Research intelligence workflow

### Product outcome

A researcher or administrator can move a research record from discovery or creation through planning, governance, data acquisition, analysis, publication and evidence-backed reporting. A leadership user can understand the status and evidence without confusing imported metadata with approved research.

### Required user journey

1. **Research library:** browse imported website publications and organisation research records. Distinguish publication, study, proposal, dataset, field observation and external literature.
2. **Import and enrich:** search OpenAlex by DOI, title, author, ORCID or institution; preview candidates; explicitly select fields to import; retain provider ID, retrieval time, source URL and original metadata snapshot.
3. **Create research:** create a new study with title, plain-language summary, research question, objectives, theme, geography, lead researcher, collaborators, intended outputs and proposed dates. Save as concept/draft.
4. **Plan:** create proposal versions, milestones, tasks, protocol versions, methods, sampling, instruments, data-management plan, risk and safeguarding notes.
5. **Govern:** route protocol and ethics/safeguarding decisions to independent reviewers. Record decision, reviewer, date, conditions and version. Block activation until required approvals exist.
6. **Collect/register data:** register dataset metadata and dictionary; attach source/provider/licence and collection period; upload through private storage; quarantine and scan; submit for independent review.
7. **Analyse:** create reproducible analysis runs from approved dataset versions; record parameters, software, random seed, output checksums and limitations.
8. **Publish:** link DOI/ORCID/OpenAlex metadata, select approved outputs and publish only after editorial/research governance checks.
9. **Report:** show workflow state, milestones, outputs, datasets, collaborators, quality flags, analysis lineage and evidence. Never equate record counts with research quality or impact.

### Research workspace views

- **Portfolio overview:** studies by lifecycle, theme, region, lead, risk and due date.
- **Research record:** overview, objectives, collaborators, proposal/protocol versions, ethics, milestones, datasets, publications, analysis runs and audit trail.
- **Discovery:** OpenAlex search/preview/import with explicit field selection and duplicate resolution.
- **Create study wizard:** progressive sections, save draft, validation and confirmation.
- **Review queues:** proposal, protocol, ethics and dataset decisions with separation-of-duty controls.
- **Dataset workspace:** metadata, dictionary, versions, scan state, review history and authorised download action.
- **Analysis workspace:** selected dataset/version, bounded filters, descriptive outputs, charts/maps where supported, provenance and caveats.
- **Publication workspace:** publication registry, external metadata refresh preview and selected-field import.
- **Evidence ledger:** source, actor, timestamp, record/version, approval and immutable event references.

### Research acceptance criteria

- Imported website publications remain visibly source-attributed and can be reconciled with DOI/provider metadata.
- Duplicate matching uses persistent identifiers first and a reviewable title/author/year fallback; no silent destructive merge.
- Study creation saves a concept record and binds the lead researcher to the authenticated caller.
- Protocol/ethics gates are enforced server-side; the UI cannot advance a study by hiding controls.
- Dataset upload, scan, review and download preserve quarantine and independent approval semantics.
- Analysis outputs identify the exact source dataset versions and configuration.
- All lists, charts and maps are tenant-scoped and state their time window, unit, quality filter and missing-data policy.
- A complete demo can use imported public research plus clearly labelled synthetic records without claiming live ODK data.

## Public climate intelligence — required public product surface

Climate intelligence must be available from the public website, not only the authenticated researcher portal. This is a product requirement and a separate publication surface over the same provider/evidence infrastructure.

- Public route: `/climate-intelligence`, with insight detail and methodology pages.
- Public API: anonymous, read-only, bounded endpoints for overview, published releases, time series, regional summaries, insights and public provider/source metadata.
- Public data is served only through an explicit `ClimatePublicRelease` publication workflow. Existing `ClimateObservation.quality_status='verified'` means quality reviewed; it does not grant permission for public disclosure.
- A different authorised reviewer must approve a candidate release before publication. Public API must never return pending, rejected, synthetic, restricted, participant-level or unapproved data.
- Release records preserve provider/product/version, data class, unit, geography, period, baseline, method, coverage, missing-data policy, uncertainty, licence, citation, retrieval time and source lineage.
- Homepage navigation and feature card link to the public climate hub. No "live" wording unless provider latency has been measured and disclosed.

The detailed public data model, API contract, release workflow, security requirements, implementation sequence and definition of done are in [PUBLIC_CLIMATE_INTELLIGENCE.md](PUBLIC_CLIMATE_INTELLIGENCE.md). This is a specification only until the model, routes, frontend and tests are implemented.

## Priority 2 — Curriculum and learning content

### Product outcome

The platform ships four coherent, editable, organisation-owned curriculum templates aligned to the published programme pillars. Each course has measurable outcomes, modules, lesson plans, activities, assessment rubrics, safeguarding notes and certificate criteria. Templates remain drafts until organisational review.

### Initial curriculum catalogue

1. Research Methods and Evidence Practice — early-career researchers.
2. Climate and Health Resilience — healthcare workers.
3. Youth Climate Stewardship and Community Action — youth participants.
4. Indigenous and Community Knowledge for Climate Resilience — community facilitators and knowledge partners.

The detailed curriculum blueprint is in [NEXTGEN_CURRICULUM_BLUEPRINT.md](learning/NEXTGEN_CURRICULUM_BLUEPRINT.md).

### Learning acceptance criteria

- Each course has an audience, prerequisites, workload, delivery mode, measurable outcomes and completion rules.
- Modules contain substantive lesson plans rather than placeholder text.
- Lessons include learning objectives, facilitator guidance, learner activity, resources, reflection and evidence of completion.
- Assessments map to course outcomes and use transparent rubrics; objective quizzes are scored server-side.
- Learner access requires approved enrolment; staff review permissions remain API-enforced.
- Attendance, mentorship, progress and assessment outcomes are attributable to a course cohort.
- Certificates are issued only after explicit completion criteria and are verifiable/revocable.
- Minors' safeguarding, consent and retention requirements are reviewed before live enrolment.

## Priority 3 — Founder and administration workspace

Complete a single operational cockpit for organisation profile, people/roles, invitations, governance, partner verification, CMS approvals, programmes, funding records, research and learning oversight. Add actionable queues, audit context, safe exports and clear data freshness.

Acceptance requires owner-controlled elevated roles, independent approval, no client-side authorization assumptions, and a demonstrable audit trail for privileged changes.

## Priority 4 — Programme operations

Complete the programme lifecycle from planning to delivery: programme owner, geography, target cohort, activities, schedules, assignments, outputs, milestones, indicator definitions, evidence and close-out. Link participation and learning records without exposing sensitive participant data.

## Priority 5 — Assessments and progress

Complete learner and staff views for outcomes, assessment attempts, feedback, attendance, mentorship and cohort progression. Preserve immutable attempt history and make completion rules explicit.

## Priority 6 — Certificates

Complete PDF issuance, unique verification code/QR, public minimal verification response, revocation, reissue policy and audit history. A certificate must not reveal private learner information.

## Priority 7 — Leadership impact

Build a leadership dashboard that separates:
- Inputs and resources.
- Activities and reach.
- Outputs and deliverables.
- Outcomes and changes.
- Longer-term impact.

Every metric must carry definition, unit, reporting period, geography, source, verification state, owner and last-updated timestamp. Website-reported figures must be labelled as such until evidence is reviewed. Never sum incompatible indicators or infer causation from activity counts.

## Priority 8 — Partner and funder reporting

Create partner-specific programme views, grant/opportunity records, budgets, commitments, deliverables, indicator snapshots, evidence attachments and exportable reports. Apply minimum-cohort suppression and strict tenant/partner access. Do not add payment processing without a separately approved scope.

## Priority 9 — Production hardening (continuous)

- Browser end-to-end tests for founder, researcher, learner, programme manager and partner journeys.
- Security and privacy review, safeguarding review and threat modelling.
- Edge/API rate limits, abuse protection, CSRF/session review and dependency scanning.
- Staging/production separation, secret rotation, least privilege and audit-log retention.
- Database backup automation, off-site retention and tested restore drills; object storage recovery plan.
- Health/readiness checks, structured logs, metrics, alerts and incident runbooks.
- Explicit migration/release process, rollback plan and immutable deployed commit record.
- Load testing for provider ingestion and background workers.
- Accessibility, responsive/mobile QA and reduced-motion checks.

## Climate intelligence provider strategy

The platform must not rely only on user-submitted observations. Build a provider registry and scheduled, bounded ingestion workflows with source attribution and quality review.

| Provider/source | Best use | Status in current repository | Next action |
|---|---|---|---|
| NASA POWER | Daily meteorological and solar point series | Adapter implemented for selected parameters | Validate operational quotas, coverage and provenance in staging |
| CHIRPS v3 | Satellite/gauge precipitation grids and area extraction | Adapter implemented | Validate variant, spatial extraction, licence and time semantics |
| Copernicus ERA5 | Reanalysis fields and derived climate indicators | Adapter code exists; optional libraries/CDS credentials and dataset acceptance required | Complete deployment profile, credential handling, queue and acceptance tests |
| World Bank Climate Change Knowledge Portal | Country/subnational historical context and CMIP6 projections | Not integrated | Add curated indicator/period/scenario adapter with explicit model and ensemble metadata |
| ICPAC | East Africa regional climate outlooks, drought and early-warning products | Not integrated | Establish data access, licensing and update contract with provider |
| NASA GPM IMERG | Satellite precipitation and event-scale rainfall context | Not integrated | Evaluate use for rainfall event validation and temporal complement to CHIRPS |
| ODK Central | Organisation field observations and survey submissions | Connector and sync workflow implemented; live Central endpoint not available for acceptance | Use simulator for deterministic demo; require a separate test Central project for live acceptance |

Provider ingestion should run asynchronously for large jobs. The current climate ingestion endpoint is a bounded synchronous MVP; do not use it for large backfills. Add durable jobs with retries, cancellation, per-tenant quotas, idempotency, run status and alerting.

Climate dashboard outputs must expose provider, dataset/version, units, spatial resolution, temporal resolution, requested and actual coverage, transformations, missingness, quality status, licence/citation and limitations. Never interpolate or impute silently. Keep pending field observations visibly provisional and require independent review before treating them as verified.

## Public climate intelligence implementation status

The current climate implementation branch adds:
- Public climate catalogue, source register, release detail and methodology pages with an editorial high-contrast visual system.
- Authenticated Climate Studio at `/workspace/research/climate`, linked from the research workspace.
- Bounded CHIRPS v3 area ingestion form and organisation-scoped ingestion ledger.
- Per-run pending/verified/rejected counts and sample inspection.
- Audited batch quality review, with submitter self-review blocked.
- Release authoring from completed runs only when every inserted observation has an independent reviewer identity, a verified quality state and a recorded licence.
- Versioned release workflow with independent approval, publication, supersession and retraction.

The CHIRPS UI currently uses the SAT product variant and limits each request to 31 days. The release aggregation is an arithmetic mean of independently verified grid-cell observations at each timestamp; it does not impute missing values. Coverage and missingness remain unreported. NASA POWER is point-based and is not eligible for this area-aggregated public release flow.

Still required before a climate public-data demo:
- A successful live provider run in the target staging deployment.
- Independent quality review by an eligible second user.
- A published release verified through the anonymous public API and browser.
- Operational review of synchronous ingestion limits, timeouts, provider freshness and retry behaviour.

## Presentation and demo policy

Maintain these repository artefacts together:
- This status/roadmap.
- [Founder demonstration runbook](FOUNDER_DEMONSTRATION.md).
- [Founder presentation](FOUNDER_PRESENTATION.md).
- [Short demo pitch](pitch/DEMO_PITCH.md).
- [LLM development instructions](LLM_DEVELOPMENT_GUIDE.md).
- [Curriculum blueprint](learning/NEXTGEN_CURRICULUM_BLUEPRINT.md).

A demo may combine live platform records, imported website records and synthetic fixtures only when each category is labelled. Never present an unavailable provider as live, a simulated ODK endpoint as ODK Central, a website claim as independently audited impact, or an unfinished workflow as production-ready.
