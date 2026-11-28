# Public Climate Intelligence — Product, API and Release Specification

**Priority:** research/climate intelligence — public presentation workstream  
**Status:** public hub, governed release workflow, research-linked insight pathway and staging synthetic showcase implemented; real provider-backed publication acceptance and dedicated regional aggregation remain outstanding  
**Applies to:** public website, research workspace, climate ingestion and reporting

## 1. Product decision

Climate intelligence is a first-class public-facing capability of NextGen For Earth. It must be discoverable from the public homepage and have a dedicated route at:

- `/climate-intelligence` — public climate intelligence hub.
- `/climate-intelligence/insights/[slug]` — editorial insight pages backed by approved evidence.
- `/climate-intelligence/methodology` — sources, methods, definitions, uncertainty and limitations.

The authenticated research workspace remains the place for provider configuration, unrestricted research queries, pending observations, field data, quality review, study-linked analysis and sensitive material.

Both experiences must consume the same provider and evidence infrastructure. The public experience is a deliberately curated publication layer, not a second climate database.

## 2. Public information architecture

### Climate intelligence hub

The page should answer: what is changing, where, over what period, how confident are we, what is the source, and what should the reader do next?

Recommended sections:

1. **Regional overview:** Kenya first, then East Africa where geographic coverage and provider semantics support it. Show last updated time and the selected reference period.
2. **Rainfall:** observed/estimated rainfall totals, departures from a clearly defined baseline, spatial coverage and data gaps.
3. **Temperature and heat:** daily/monthly temperature summaries and heat indicators only where the selected provider supports the definition.
4. **Drought and vegetation:** rainfall deficit and vegetation-condition indicators with their own baseline, sensor, resolution and caveats.
5. **Climate and health:** carefully framed exposure/context indicators and links to approved research. Do not expose participant-level health data or infer individual risk.
6. **Regional maps:** published, bounded geographies with legend, unit, time window, source, resolution and missing-data treatment.
7. **Research and field evidence:** approved public research summaries and community projects with publication permissions.
8. **Data and methodology:** provider catalogue, definitions, source citations, licence/attribution and known limitations.

Public users should be able to select geography, indicator and period from a bounded set of supported options. The UI must show a meaningful empty state when no eligible public release exists. Synthetic or pending observations must never be substituted for real evidence. A dedicated staging-only synthetic showcase is permitted only when `DEPLOYMENT_STAGE=staging` and the explicit `CLIMATE_DEMO_SEED_ENABLED=true` flag are both set, every release is prominently labelled as illustrative, and the production deployment stage excludes it.

### Homepage integration

Add a primary navigation item and a visible homepage feature card linking to Climate Intelligence. The card should use the latest approved public climate release only. It must not display a manually maintained "live" number or imply real-time status when the underlying source is daily, monthly, delayed or a historical reanalysis.

## 2A. Initial NextGen For Earth use cases

The public organisation website describes climate science-to-action, climate-health research, youth stewardship and community resilience. Its research section includes work on heat exposure and maternal/infant health in Kilifi, climate seasonality and ageing in Busia and Kilifi, healthcare-worker preparedness, and youth-inclusive climate/health research. These public descriptions provide a defensible initial editorial focus, but they do not themselves supply gridded climate measurements or permission to republish private research data.

Prioritise the public hub around:

1. **Heat and health context in coastal Kenya:** temperature/heat indicators for Kilifi and nearby supported areas, with a clear distinction between gridded ambient conditions and individual exposure. Link to approved NextGen publications on maternal health and heat.
2. **Seasonality and health in Busia and Kilifi:** rainfall/temperature seasonal context for the geography and periods covered by the SENIORS study. Do not infer individual health effects from climate series.
3. **Rainfall variability and drought context:** CHIRPS rainfall summaries and, when methodologically appropriate, drought/vegetation indicators. Show baseline and spatial coverage.
4. **Healthcare worker preparedness:** pair approved climate-health research summaries with external climate context; do not publish patient or health-worker personal data.
5. **Youth/community climate stewardship:** present approved programme activity and aggregate restoration indicators separately from satellite-derived vegetation change. Do not claim planted-tree survival or ecological recovery from an unvalidated imagery comparison.
6. **Indigenous/community knowledge:** publish only community-authorised knowledge and co-approved narratives. Restricted knowledge must remain outside the public site even if a climate map overlaps the relevant region.

The first release should focus on a small number of defensible indicators and geographies rather than a broad but weakly evidenced "Africa climate dashboard".

## 2B. Implemented public editorial insight pathway

The CMS supports a dedicated `climate_insight` content type. Each insight records a linked public climate release slug and a linked public research publication slug, plus optional region, indicator and evidence note. Anonymous climate insight reads return an item only while both linked records are independently published in the same organisation. The release must be in the current `published` state; a retraction or supersession that removes the current public release also removes the linked insight from public discovery.

The public hub displays these editorial cards separately from quantitative climate release cards. If there are no eligible insight records, it shows a deliberate no-insights state. An insight is not a substitute for a data release and cannot publish independently of its evidence links.

## 3. Data classes and publication boundary

Keep these data classes distinct in the UI and API:

| Class | Meaning | Public default |
|---|---|---|
| Station/in-situ observation | Instrument or field measurement | No; publish only through explicit approved release |
| Satellite estimate | Retrieval/algorithm-derived estimate | Yes only when source terms permit and release is approved |
| Reanalysis | Model/data-assimilation reconstruction of past conditions | Yes with product and period identified |
| Forecast | Model output for a future valid period | Yes only with provider issue time, valid time and forecast status |
| Climate projection | Scenario/model ensemble for future climate | Yes only with scenario, model/ensemble and reference period explicit |
| Organisation field observation | Collected through programme/ODK workflow | No until independently reviewed, safeguarding checked and explicitly approved for public release |
| Synthetic demo | Deterministic generated fixture | Permitted only in non-production staging as an explicitly labelled UX demonstration; never represented as observed climate or scientific evidence |

**Important:** a verified climate observation is not automatically public. Existing `ClimateObservation.quality_status='verified'` is a quality-review state, not a publication permission. Public exposure requires a separate explicit release decision.

## 4. Public release model

Introduce a publication aggregate (proposed model: `ClimatePublicRelease`) rather than querying all tenant observations from public routes.

Minimum fields:

- ID, organisation ID, stable slug, title, summary and publication state.
- Indicator/variable, canonical unit and display precision.
- Provider ID, provider product/dataset, provider version and provider citation.
- Data class: observation, satellite_estimate, reanalysis, forecast or projection.
- Geography identifier/name, geometry version and bounded geometry reference.
- Period start/end, baseline start/end where applicable, issue time and valid time where applicable.
- Aggregation method, spatial/temporal resolution, missing-data policy and transformations.
- Source ingestion run IDs and immutable source dataset/observation version references.
- Quality review state, reviewer, review time and quality notes suitable for publication.
- Uncertainty/confidence description and known limitations.
- Licence/attribution text and provider terms URL.
- Public chart/map payload or reference to a precomputed, bounded result.
- Created by, approved by, approved at, published at, updated at and audit events.

A release may be created only from eligible source records and must retain lineage. It must not contain restricted geometries, precise locations of vulnerable communities, personal data, raw ODK submissions or private dataset object keys.

### Publication workflow

1. Researcher creates a candidate release from an approved provider ingestion or independently reviewed organisation dataset.
2. System validates provider terms, quality state, coverage, time period, units, transformations and geography.
3. Candidate is previewed with source citations, map/chart, missingness and caveats.
4. A different authorised reviewer approves it; author cannot approve their own release.
5. Publisher makes the release public; publication creates an audit event and immutable release version.
6. Updates create a new version or explicitly supersede the old one. Public API responses expose the current published version and its timestamp.
7. Unpublish/retract action is available to authorised administrators, with reason and audit trail.

No direct public query should read arbitrary `ClimateObservation` rows merely because their quality state is verified.

## 5. Public API contract (proposed)

All endpoints are anonymous, read-only, bounded, cacheable and organisation-slug scoped. The public BFF must allow-list these exact GET routes and must never forward cookies or arbitrary caller-supplied upstream URLs.

### Overview

`GET /api/public/organizations/{slug}/climate/overview`

Returns:
- organisation name and public climate coverage;
- latest approved release per supported indicator;
- publication timestamp and source observation period;
- featured public insights;
- explicit coverage/availability summary.

### Published releases

`GET /api/public/organizations/{slug}/climate/releases?indicator=precipitation&region=kenya&period=...`

Returns only `published` release versions. Filter values must be allow-listed, bounded and validated. Pagination is cursor-based. No arbitrary SQL, geometry or unbounded time ranges are exposed.

### Time series

`GET /api/public/organizations/{slug}/climate/releases/{release_slug}/series`

Returns the release's precomputed points with date, value, unit, sample/coverage count and optional uncertainty fields. The response includes provider, data class, baseline, method, missing-data policy, source URL, licence, citation, retrieval time and limitations.

### Regional layers

`GET /api/public/organizations/{slug}/climate/releases/{release_slug}/regions`

Returns only simplified, approved regional features or bounded aggregate rows. Never expose precise participant/station coordinates unless a separate disclosure review explicitly permits it. Prefer administrative-area summaries and simplified geometry.

### Public insights

`GET /api/public/organizations/{slug}/climate/insights`

Returns published editorial summaries linked to release IDs and research publications. Narrative claims must be traceable to their evidence.

### Provider catalogue

`GET /api/public/organizations/{slug}/climate/sources`

Returns public-safe provider/product descriptions, variables, source links, attribution and data class. Never return credentials, internal errors, private endpoints or operational secrets.

The exact path prefix should follow the existing `/public/organizations/{slug}/...` conventions in `public_content.py`; the `/api` prefix is supplied by the application deployment.

## 6. Provider roadmap for public products

| Stage | Source | Public role | Status in current repository baseline |
|---|---|---|---|
| 1 | NASA POWER | Daily point meteorology and solar variables; clear point-data coverage | Adapter implemented for selected variables; public release pipeline still required |
| 1 | CHIRPS v3 | Rainfall totals/deficits and bounded regional summaries | Adapter implemented; public release pipeline still required |
| 2 | Copernicus ERA5/ERA5-Land | Reanalysis context, temperature and land variables | Adapter code exists; optional dependencies, CDS credentials and terms acceptance required |
| 2 | NASA GPM IMERG | Higher-frequency satellite precipitation and event context | Candidate; not integrated |
| 2 | ICPAC | East Africa regional climate outlooks and early warning | Candidate; confirm product access, licence, update cadence and terms before integration |
| 3 | World Bank CCKP / CMIP6 | Long-term climate baselines and scenario projections | Candidate; not integrated |
| 3 | MODIS/VIIRS and Sentinel | Vegetation, land-cover, fire and earth-observation context | Candidate; product-specific pipelines and licences/attribution required |

Public data availability is not equivalent to local relevance or scientific validity. Prioritise provider products against a named indicator and use case; do not add providers simply to increase a dashboard's source count.

## 7. Visualisation and interpretation rules

Every public visual must show:
- Indicator name, definition and unit.
- Geography and spatial resolution.
- Observation/reference period and timezone/calendar convention.
- Provider, dataset/product and version.
- Data class (observed, satellite estimate, reanalysis, forecast or projection).
- Baseline definition for anomalies.
- Missing-data and spatial coverage.
- Quality/review state.
- Uncertainty or limitations where available.
- Last updated/retrieved time and source citation.

Do not:
- label daily or delayed products "live" without a defensible latency definition;
- mix observed data, reanalysis, forecasts and projections on one undifferentiated line;
- compare unlike grid resolutions without disclosure;
- fill missing periods with zero;
- describe correlation or a map overlay as causal climate-health attribution;
- infer local household exposure from coarse grid-cell data;
- imply that a scenario projection is a prediction;
- publish small-area results that could identify individuals or sensitive community locations.

For anomaly charts, publish the reference baseline and calculation. For projections, show scenario and ensemble spread rather than a single deterministic line where the source supports ensembles.

## 8. Technical implementation sequence

### Increment A — public-safe release contract
- Add release schema/model and migration, with explicit draft/review/approved/published/retracted states.
- Add role-protected create/update/submit/approve/publish/unpublish endpoints.
- Enforce separation of duty and immutable source lineage.
- Add public read-only overview, release, series, regional and source endpoints.
- Add tests for anonymous access, published-only filtering, tenant isolation, retraction, approval separation, restricted data exclusion and response bounds.

### Increment B — public website experience
- Add `web/app/climate-intelligence/page.tsx` and insight detail routes.
- Add climate intelligence navigation and homepage feature.
- Consume only the public BFF allow-listed endpoints.
- Build indicator cards, regional selector, chart, map/region summaries, data-source panel and methodology notes.
- Include accessible tables as alternatives to charts; responsive and reduced-motion support.
- Add Playwright tests for no-data, published data, provider outage, source attribution and mobile layout.

### Increment C — research workspace publishing
- Add "Prepare public release" from a verified provider ingestion or approved dataset.
- Preview charts/maps and disclosure checks before submission.
- Add reviewer queue and publish/retract actions to founder/admin and research workspaces.
- Preserve versions and notify public cache invalidation after publication.

### Increment D — provider breadth and durable ingestion
- Move larger climate ingestion to durable background jobs with idempotency, quotas, retries, cancellation and observability.
- Configure ERA5 only after runtime and provider terms prerequisites.
- Evaluate GPM and ICPAC against priority use cases.
- Add climate projection and vegetation/land-cover layers after data governance and performance testing.

## 9. Public endpoint security and operational requirements

- Anonymous GET only; no public write endpoints.
- Organisation slug resolves to the canonical organisation; all queries still filter organisation ID.
- Publish allow-listed response schemas, never ORM objects or raw metadata JSON.
- Strictly bound query parameters, response size, time ranges, geometry complexity and pagination.
- Apply rate limits, CDN caching and cache invalidation on publish/retract.
- Use ETags or version identifiers for immutable release payloads.
- Public error messages must not reveal internal provider URLs, stack traces, credentials or private record identifiers.
- Avoid precise coordinates for field/community records; apply disclosure thresholds and geometry generalisation.
- Keep source licence/attribution attached to every chart, map and downloadable export.
- Monitor freshness and show stale/unavailable state rather than generating substitute values.
- Add automated checks that production public endpoints cannot return pending, rejected, restricted or synthetic demo data; staging fixture responses must carry the dedicated synthetic provider/data-class labels and limitations.

## 10. Definition of done

- Public homepage links to a dedicated climate intelligence hub.
- At least one real provider-backed, licence-reviewed, approved public release is available in staging before it is described as populated.
- Public charts/maps include source, unit, geography, period, data class, method, missingness and limitations.
- Anonymous API tests prove only published releases are returned.
- Researchers can create candidate releases; a separate reviewer can approve and publish them.
- Retracted releases disappear from public API responses while audit/version history remains.
- No private participant, ODK, restricted dataset or precise sensitive location data is exposed.
- Public page remains useful with no releases or an unavailable provider.
- Public endpoint health, cache freshness and provider ingestion status are observable.

## 11. Presentation language

Use: "NextGen For Earth is building a public climate intelligence resource that brings together trusted climate datasets, regional research and community evidence, with sources and limitations visible."

Do not say "real-time climate monitoring" unless a specific operational feed has demonstrated and documented that latency.


## 15. Implementation boundary — first runtime increment (PR #116)

The first runtime increment implements the publication lifecycle and public catalogue, but does not complete every proposed surface above.

Implemented in the current feature branch:
- `ClimatePublicRelease` and append-only lifecycle events, with a migration.
- Authenticated draft creation, submission, independent approval, publication and retraction.
- Draft creation requires a completed same-organisation provider ingestion run with a recorded licence.
- Every observation inserted by that run must be independently quality-verified before release creation.
- The API derives the public series server-side from those verified observations. The client cannot submit chart values.
- The implemented temporal aggregation is the arithmetic mean of verified observations sharing a timestamp. It performs no imputation.
- Coverage and missingness are returned as unreported until a defensible denominator/coverage calculation is implemented; do not invent percentages.
- Publishing a replacement version supersedes the prior published version. Retraction removes the current version from public reads.
- Anonymous endpoints currently cover overview, release list, release detail, series and source catalogue. Public reads are bounded and cacheable.
- The website has the catalogue, release detail and methodology routes, homepage navigation, source register and research-linked insight cards. With `DEPLOYMENT_STAGE=staging` and `CLIMATE_DEMO_SEED_ENABLED=true`, the staging demo seed publishes synthetic rainfall and temperature series with 72 monthly points each and a clearly disclosed linked field note; production responses exclude the synthetic provider.

The authenticated browser workflow is now implemented at `/workspace/research/climate`:
- Bounded CHIRPS v3 SAT ingestion with a 7-day UI limit, explicit WGS84 bounding box, researcher-supplied area label and pinned Rasterio runtime in the API image.
- The ingestion record retains the area label and CHIRPS product variant. Release creation verifies that the declared geography and data class match that original provider request; product version, resolution, citation, licence and attribution are derived from the trusted provider run.
- Organisation-scoped provider-run history with per-run pending/verified/rejected counts.
- Sample observation inspection and an audited batch quality decision.
- Versioned release drafting, submission, independent approval, publication, supersession and retraction.
- Public climate catalogue, source register, release detail and methodology pages; release detail includes a chart derived from published series values and an accessible table.

Still outstanding:
- A successful live provider-backed run, independent review and publication in the target staging environment.
- Explicit public regional aggregation and a dedicated regions endpoint.
- Curated climate insight/editorial records and the insights endpoint.
- Spatial maps and geographic comparison visualisations.
- Stale-data indicators, ETags/cache invalidation and operational monitoring for public release freshness.
- Durable asynchronous jobs for larger provider backfills; the current endpoint is synchronous and should remain bounded.
Do not claim the public climate hub is populated or live until a real provider-backed run has been quality-reviewed, published and verified through the staging public API.
