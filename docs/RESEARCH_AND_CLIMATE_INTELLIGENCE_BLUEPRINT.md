# Research and Climate Intelligence — Product and Workflow Blueprint

**Priority:** 1 — research intelligence  
**Companion priority:** 2 — curriculum development  
**Status:** Product specification for implementation and acceptance

## Product objective

Make research a complete, auditable workflow rather than a list of imported publications. Connect the organisation's existing public research and publications to governed study records, external scholarly discovery, curated climate datasets, field observations, reproducible analysis and approved outputs.

The dashboard must make source and evidence provenance visible at every step. It must not present an imported paper as an organisation-led study, an unreviewed dataset as verified, or a descriptive association as causal evidence.

## 1. Research portfolio and imported-publication demo

### Imported website research

The demo should begin with the publications and research items already transcribed from the public NextGen For Earth website. Preserve:
- Original website URL and capture date.
- Original title, author string, year and DOI/URL where available.
- Import timestamp and importing actor.
- External provider identifier, if reconciled.
- Metadata fields changed by an editor versus provider-supplied fields.
- Verification state and reviewer.

The public website's 12 publication listings are a starting inventory, not a guarantee that all metadata is complete or that the organisation owns every work. Resolve DOI and author identity carefully. Do not infer organisational authorship from a mention on the site.

### Research portfolio cards

Show title, record type, lifecycle state, theme, geography, lead, updated date and next action. Include filters for status, type, theme, geography, lead and date. Provide a visible legend for:
- Website-imported.
- External metadata enriched.
- Organisation-created.
- Awaiting governance.
- Active/approved.
- Completed.
- Published.
- Archived.

## 2. Research lifecycle

Use the lifecycle already enforced by the API:
`concept → protocol → active → completed → published → archived`.

The UI should orchestrate, not bypass, the following gates:

1. Concept: study created; lead researcher assigned.
2. Proposal: versioned rationale, question, objectives, methods, feasibility and budget assumptions.
3. Protocol: versioned protocol submitted and independently approved.
4. Ethics and safeguarding: decision tied to the protocol version; activation blocked until approval where required.
5. Active: milestones, tasks, collaborators, field collection and deviations.
6. Dataset: metadata, dictionary, source, licence, classification, versions, scan state and independent review.
7. Analysis: approved input versions, analysis configuration, software, outputs and checksums.
8. Completed: final outputs, close-out, limitations and data disposition.
9. Published: approved publication/output linked to DOI or repository record.
10. Archived: retention and access policy applied; audit history retained.

A lifecycle state change must display the prerequisites and the exact API validation response. Do not create a client-only “approved” state.

## 3. Create new research workflow

A guided authoring flow should collect:

### Step A — Identity
- Working title.
- Short public-facing summary and internal abstract.
- Research type: observational, qualitative, mixed methods, review, evaluation, implementation, environmental monitoring or other.
- Programme/project linkage.
- Theme and geography.

### Step B — Scientific framing
- Problem statement and rationale.
- Primary research question.
- Objectives and hypotheses where appropriate.
- Target population or unit of analysis.
- Expected outputs and intended users.

### Step C — Team and governance
- Lead researcher.
- Collaborators and role.
- Partner institutions, only where verified.
- Ethics/safeguarding applicability and rationale.
- Data sensitivity and consent considerations.

### Step D — Methods and delivery
- Design and sampling.
- Instruments and collection channels.
- Analysis approach.
- Milestones, owner and due date.
- Dependencies and risk register.

### Step E — Review and save
- Validate required fields.
- Save as concept/draft.
- Show next steps: proposal, protocol, review and approvals.
- Do not activate the study on creation.

The form should support draft save, progressive completion and edit history. Avoid forcing users to enter information that is not yet known; make unknown fields explicit and report missing prerequisites.

## 4. Literature discovery and enrichment

### OpenAlex

The existing OpenAlex integration is the first discovery adapter. Support query by DOI, title, author, ORCID, institution and topic. Preview candidate records and let the user choose fields to import. Persist OpenAlex ID, retrieval time, query context, source URL and raw metadata snapshot/hash.

OpenAlex exposes works, authors, sources, institutions and related entities over a REST API; it supports search, filtering, grouping, pagination and field selection. Basic access is available without a key, while a free key raises usage budget and is required for cursor paging beyond the first page. External text is untrusted input and must be safely rendered. See [OpenAlex API reference](https://help.openalex.org/api/) and [authentication/rate limits](https://help.openalex.org/api/authentication/).

### Complementary scholarly sources — proposed

- Crossref: DOI registration metadata and bibliographic reconciliation.
- ORCID: researcher identity and author-controlled profile data; use explicit consent/authorization where accessing private or authenticated data.
- PubMed/Europe PMC: biomedical literature discovery and abstracts where relevant.
- OpenAIRE or institutional repositories: open research outputs and repository links.
- Unpaywall: open-access location discovery, subject to its current API terms and key requirements.

These are proposed adapters, not currently accepted integrations. Do not bulk-download or republish copyrighted full text. Prefer metadata, abstracts where permitted, repository links and user-authorised uploads.

## 5. Climate intelligence — provider-backed, not user-entry-only

### Provider registry

Every provider should have a registry record:
- Provider name and product/dataset.
- Variables and units.
- Spatial/temporal resolution and coverage.
- Update cadence and latency.
- Access method, credentials required and quota.
- Licence, attribution and citation.
- Data version and known limitations.
- Operational status, last successful run and last error.
- Enabled geographies and request limits.

### Initial provider portfolio

| Provider | Data role | Existing implementation status | Workflow requirement |
|---|---|---|---|
| NASA POWER | Daily point meteorology and solar parameters | Implemented for selected precipitation and 2m temperature variables | Point query, provenance, missing-value filtering and source/unit display |
| CHIRPS v3 | Satellite/gauge precipitation, point and bounded-area extraction | Implemented | Variant, grid cell, date semantics, citation/licence and quality context |
| Copernicus ERA5 | Reanalysis fields and climate context | Adapter code exists; runtime dependencies and CDS credentials/terms acceptance needed | Operator-managed credentials, async job, dataset request record and failure handling |
| World Bank CCKP | Historical climate context and CMIP6 scenario projections | Proposed, not integrated | Country/subnational selection; baseline, scenario, model ensemble and period visible |
| ICPAC | East Africa regional climate outlooks and early warning | Proposed, not integrated | Confirm access, licence, update schedule and regional product semantics |
| NASA GPM IMERG | Satellite precipitation at finer event timescales | Proposed, not integrated | Evaluate complementarity and validation against CHIRPS and station data |
| ODK Central | Structured field observations | Connector implemented; no live test endpoint accepted | Synthetic simulator for demo; live acceptance requires separate Central test project |

NASA POWER daily endpoints provide analysis-ready time series; temporal APIs support point requests and regional options with documented spatial constraints. See [NASA POWER daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) and [temporal API overview](https://power.larc.nasa.gov/docs/services/api/temporal/).

CHIRPS v3 provides gridded rainfall estimates combining satellite and station information; its data citation and CC BY 4.0 terms should be retained with derived products. See [Climate Hazards Center CHIRPS v3](https://www.chc.ucsb.edu/data/chirps3).

Copernicus CDS API access requires an account/token and acceptance of each dataset's terms before retrieval. Credentials must be server-side secrets and never browser-visible. See [CDS API setup](https://cds.climate.copernicus.eu/en/how-to-api).

World Bank CCKP provides API access to observed and projected products, including CMIP6 variables and scenarios; preserve collection, product, period, percentile, scenario, model and statistic identifiers. See [CCKP data API structure](https://climateknowledgeportal.worldbank.org/download-data).

### Climate intelligence screens

1. **Climate overview:** map of available observations/coverage, selected variable, source, date range and data-quality status.
2. **Provider catalogue:** available providers, variables, resolution, temporal coverage, licence and last ingestion.
3. **New ingestion:** choose provider, variable/product, point or bounded region, period and cadence. Validate request cost and limits before starting.
4. **Ingestion runs:** queued/running/succeeded/failed, requested extent, counts, timestamps, error summary and retry action.
5. **Observation explorer:** map/table/time series with provider, units, quality state and provenance.
6. **Quality review:** pending, flagged, accepted and rejected observations; independent reviewer and reason.
7. **Climate analysis:** descriptive summaries, anomalies, coverage, comparisons and carefully scoped derived indicators.
8. **Research linkage:** attach a climate query or dataset version to a study/protocol/analysis run.
9. **Export/report:** reproducible manifest with provider citation, licence, time range, geometry, transformations and limitations.

### Climate analysis guardrails

- Distinguish observed station data, satellite estimates, reanalysis and model projections.
- Show baseline and scenario for anomalies/projections.
- Preserve native units and record any conversion.
- Do not combine different spatial/temporal resolutions without explicit resampling methodology.
- Missing values remain missing; do not replace with zero or silently interpolate.
- Pending field observations remain provisional.
- Flagged observations are triage signals, not scientific rejection.
- Show coverage and sample counts beside every summary.
- Do not imply causality, attribution or forecast skill without a suitable validated method.
- Large backfills and provider calls must use durable background jobs, not long synchronous HTTP requests.

## 6. ODK workflow without a live Central endpoint

The UI must still demonstrate a complete data lifecycle when no test ODK Central endpoint is available:

1. Show the configured ODK connection state as “not connected” or “demo simulator”.
2. Use the repository's local synthetic ODK Central simulator and two fixture submissions.
3. Demonstrate form discovery, explicit field mapping, paginated OData sync and duplicate suppression.
4. Label each record as synthetic/demo at source and on every downstream screen.
5. Show imported observations entering pending review.
6. Demonstrate independent approval/rejection with reason and audit trail.
7. Link approved observations to a research study and show their provenance.

Never describe the simulator as a live ODK Central integration test. Production/staging acceptance requires a separate non-production Central project, dedicated read-only account, real form mapping and enabled worker.

## 7. Dashboard visual hierarchy

Recommended top-level sections:
- Research portfolio.
- Literature discovery.
- Create study.
- Protocols and ethics.
- Datasets and evidence.
- Climate intelligence.
- Field data / ODK.
- Analysis runs.
- Publications and outputs.
- Review queues.

Use meaningful empty states with a next action. Every chart needs a title, unit, period, geography, source and quality filter. Use tables for exact values and maps only when coordinates/geometry are actually available. Never invent chart values for visual polish.

## 8. Demo story

Use one website-imported publication as the discovery example, one existing study as the research record example, and a new synthetic study as the authoring example. Show:
- imported record and source provenance;
- OpenAlex metadata preview and selected-field import;
- new study saved as concept;
- protocol/ethics prerequisites;
- dataset registration and review;
- NASA POWER/CHIRPS provider data where live retrieval is available;
- synthetic ODK flow where live Central is unavailable;
- climate quality review and descriptive analysis;
- analysis provenance and publication linkage.

Mark each screen with a visible data badge: Website import, External provider, Organisation record, Synthetic demo, Pending review or Verified. “Verified” must come from the backend review state, not the frontend.

## 9. Definition of done

- [ ] Research portfolio shows imported public records and their provenance.
- [ ] OpenAlex discovery/import can be completed end-to-end with duplicate handling.
- [ ] New research can be created and saved as concept.
- [ ] Proposal/protocol/ethics workflow is navigable and API-gated.
- [ ] Dataset register/submit/review and file lifecycle are usable from the UI.
- [ ] Climate provider registry shows operational status and metadata.
- [ ] At least NASA POWER and CHIRPS are accepted against staging; ERA5 status is explicit.
- [ ] Climate ingestion is asynchronous for large jobs with retry and run history.
- [ ] Map/table/time-series views display only actual returned observations.
- [ ] ODK simulator workflow is reproducible and visibly synthetic.
- [ ] Every imported/provider observation retains source, timestamp, units and quality state.
- [ ] Research-to-climate-to-analysis-to-publication lineage is visible.
- [ ] Tenant isolation, role enforcement and audit events are covered by tests.
- [ ] Founder demo runbook and pitch are aligned with the actual staging build.
