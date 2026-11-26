# NextGen For Earth — Founder and Partner Presentation

**From a public website to a connected organisational operating platform**  
**Status snapshot:** 26 November 2026  
**Audience:** Founder, board, programme leadership, institutional partners and funders

## 1. The opportunity

NextGen For Earth works across research capacity building, healthcare worker training, youth climate stewardship and Indigenous knowledge transfer. Its public presence communicates that mission, programmes, research activity, partnerships and impact claims. The opportunity is to connect that public story to the operational systems that coordinate delivery and preserve evidence.

## 2. The proposition

One connected platform with two complementary surfaces:

- **Public experience:** approved organisational story, programmes, research, people, partners, learning opportunities and evidence.
- **Organisation workspace:** governed records and workflows for people, roles, programmes, activities, learning, research, climate data, partnerships, content and reporting.

The objective is to establish one organisational source of truth, not to replace the organisation's mission or public identity.

## 3. What is already implemented in the repository

The current feature branch contains substantial platform foundations:

- FastAPI, PostgreSQL/PostGIS, Next.js, Docker and Render deployment architecture.
- Organisation membership, roles, invitations, founder/admin governance and audit history.
- People directory, partner registry, programme/project/activity and CMS foundations.
- Research study and dataset records, proposal/protocol versioning, ethics review, collaborators, publication metadata, file quarantine/scanning, dataset review and reproducible analysis provenance.
- OpenAlex publication discovery and metadata workflows.
- NASA POWER and CHIRPS v3 climate ingestion adapters; Copernicus ERA5 adapter code with optional runtime requirements and CDS configuration.
- Climate quality review, bounded spatial/time queries, descriptive statistics, coverage and anomaly workflows.
- ODK Central connector and sync workflows; live acceptance requires a separately configured test Central project.
- Learning course/module/lesson, enrolment, assessment, progress, mentorship, attendance and certificate foundations.

This is a repository-level status statement. Live staging acceptance is a separate release gate.

## 4. Research and climate intelligence — first product priority

The research workspace is being developed as an end-to-end evidence workflow:

**Discover → create study → plan → protocol and ethics review → collect/register data → quality review → analyse → publish → report.**

The demo will begin with research and publication records imported from the public website. External scholarly metadata can enrich those records through OpenAlex, with explicit field selection and provenance. Researchers will also be able to create new studies and retain them as concepts until the required governance gates are met.

Climate intelligence is not limited to manually entered observations. The current architecture includes NASA POWER and CHIRPS v3 adapters, with ERA5 requiring deployment configuration. The proposed next provider layer includes World Bank climate projections, ICPAC regional products and NASA GPM precipitation. Every chart and map must identify source, unit, period, geography, coverage, quality state and limitations.

Where a live ODK Central test endpoint is unavailable, the demonstration will use the repository's synthetic simulator and label the records as synthetic. It will not be represented as a live Central integration test.

## 5. Public climate intelligence — visible mission capability

Climate intelligence will be available on the public website as a dedicated hub, alongside the deeper authenticated research workspace. The public experience will present Kenya and East Africa rainfall, temperature/heat, drought/vegetation and climate-health context where suitable source data and approved releases exist.

The public site will not query private observation records directly. Researchers prepare a versioned public release from eligible provider or reviewed organisation data; an independent reviewer approves it; an authorised publisher makes it public. Every chart and map identifies provider/product, data class, unit, geography, period, baseline, method, coverage, missingness, uncertainty, licence and limitations.

The first public climate runtime increment now includes a governed release API, versioning and audit events, a public evidence catalogue, release detail pages and methodology notes. The authenticated Climate Studio at `/workspace/research/climate` connects bounded CHIRPS v3 ingestion, provider-run history, sample inspection, batch quality review, release drafting and independent approval/publication. The public interface uses a high-contrast editorial data design; the research studio uses a dark, technical operations interface.

This is a deployable workflow increment, not evidence of live climate coverage. A real provider run must complete, receive independent quality review and be explicitly published before the public hub can show climate values. The hub must remain in its honest no-release state until then. NASA POWER remains point-based in the current adapter; the public area-release path uses bounded-area providers such as CHIRPS.

## 6. Learning and curriculum — second product priority

The existing demo seed creates three published course shells with ordered modules and lessons. Their current lesson text is placeholder content, not approved instructional material. The next curriculum increment defines four proposed tracks for organisational review:

1. Research Methods and Evidence Practice.
2. Climate and Health Resilience.
3. Youth Climate Stewardship and Community Action.
4. Indigenous and Community Knowledge for Climate Resilience.

Each curriculum is designed around measurable outcomes, lesson plans, practical activities, assessment rubrics, safeguarding requirements and transparent certificate criteria. The Indigenous knowledge track requires community-led governance, permissions and benefit-sharing.

## 7. What remains to complete

- Finish the connected research authoring, governance, discovery and climate analysis experience.
- Replace placeholder lesson bodies with reviewed, substantive curriculum content and assessments.
- Complete founder/admin operational queues and governance visibility.
- Improve programme delivery, participant progression and cohort operations.
- Complete learner assessment, progress and certificate acceptance.
- Build leadership impact reporting that distinguishes inputs, activities, outputs, outcomes and long-term impact.
- Complete partner/funder reporting, evidence exports and grant reporting.
- Complete browser end-to-end tests, security/privacy/safeguarding review, observability, alerting, backup automation and restore drills.

## 8. Evidence and integrity

Website-reported impact metrics are source claims until independently validated. Website-listed people are not automatically active portal users. Website-listed partners are not automatically verified agreements. Imported publications are not automatically organisation-authored research. Provider ingestion does not equal scientific validation. Synthetic demo records must remain visibly labelled.

The platform will preserve source, period, method, owner, reviewer and evidence references for reported indicators.

## 9. Rollout

**A — Product completion:** research workflow, climate provider presentation, curriculum authoring and founder/admin acceptance.  
**B — Organisational validation:** reconcile people, programmes, publications, partner relationships, permissions and impact evidence.  
**C — Pilot:** onboard a small group of administrators, researchers, programme leads and learners; execute acceptance journeys.  
**D — Production:** security and safeguarding review, backup/restore validation, monitoring, operational handover and controlled launch.

## 10. Decisions requested

- Confirm the organisation's research and curriculum subject-matter leads.
- Confirm research governance and ethics approval responsibilities.
- Review the four proposed curriculum tracks and nominate independent reviewers.
- Validate partner relationships, public people profiles and image reuse permissions.
- Confirm the evidence, period and methodology behind public impact claims.
- Approve a pilot cohort and production acceptance criteria.

## Closing

Tell the story. Run the programmes. Organise the people. Connect the partners. Demonstrate the evidence.

The objective is a stronger organisation capable of turning research, youth leadership and climate action into measurable, accountable impact.


## Public climate intelligence — research context

The public climate hub now connects two separately governed evidence streams: provider-backed climate releases and published research outputs. An editorial climate insight can be published only when both linked records are public. The public card exposes its geography, indicator, evidence note, source research and underlying climate release. Retracting the climate release removes the insight from public discovery.

This creates a traceable path from provider evidence to research context without treating an association as causation. The public page shows an explicit empty state until a valid pair of published records exists; no synthetic insight is seeded.


## Learning and capacity-building — pilot content update

The learning workspace now has four substantive pilot tracks covering research methods, climate and health, youth climate stewardship, and Indigenous/community knowledge. The demo seed catalogue contains 24 lessons with learning outcomes, applied exercises, self-checks and official further reading, plus four formative quizzes. The learner classroom shows course scope, guided learning time and module completion.

Position this as a pilot curriculum prepared for review—not as an accredited qualification. Before cohort delivery, obtain research, clinical, safeguarding and community-lead review as appropriate. The updated seed catalogue must be applied in the target environment with the documented seed command.
