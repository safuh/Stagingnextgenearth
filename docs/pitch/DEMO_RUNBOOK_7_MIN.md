# Seven-minute Founder Demo Runbook

**Environment:** dedicated staging/demo environment  
**Rule:** show only workflows verified in the current build; label imported, external and synthetic records.

| Time | Screen | Demonstration |
|---|---|---|
| 00:00–00:40 | Public website | Establish mission, programme pillars, research and published impact claims. Identify website-reported figures as source claims. Open the Climate Intelligence hub if a published release is available; show source, data class, period and limitations. |
| 00:40–01:30 | Founder/admin | Show organisation overview, roles, people directory, partner verification and governance/audit controls. |
| 01:30–02:40 | Research library | Open a website-imported publication, show source provenance, preview external scholarly metadata and create a new study saved as concept. |
| 02:40–03:30 | Research governance | Show proposal/protocol/ethics gates, dataset registration, submission/review and analysis provenance. Do not imply a concept is approved. |
| 03:30–04:40 | Climate intelligence | Open the populated staging public climate hub and methodology. Inspect the synthetic rainfall and temperature series, source register, regional comparisons and linked research field note. Read the visible synthetic-data disclaimer aloud; these are deterministic demo fixtures, not observations, forecasts or scientific findings. Point out publication time, source retrieval time and represented data-period end as separate timestamps. Then open the authenticated Climate Studio to show the distinct provider-ingestion, quality-review and release-governance workflow. |
| 04:40–05:20 | Field data | If live Central is unavailable, demonstrate the synthetic ODK simulator. Label every fixture Synthetic demo; show mapping, pagination, duplicate suppression and pending review. |
| 05:20–06:20 | Learning | Show the four published pilot tracks, 28 modules, 86 substantive lessons and four formative quizzes. Four private authoring drafts are available to staff; public discovery shows published tracks only. Explain that the curriculum is subject to subject-matter, clinical, safeguarding, accessibility and community review; it is not accredited training. |
| 06:20–07:00 | Leadership / close | Show available organisational indicators, distinguish operational counts from verified outcomes, and close on one connected operating platform. |

## Pre-demo checks

- [ ] Confirm the public web page and API health endpoint respond.
- [ ] Record the deployed commit SHA and deployment timestamp.
- [ ] Confirm founder/admin access with a dedicated demo account.
- [ ] Use synthetic learner/staff accounts; never expose real credentials or private invitations.
- [ ] Verify the research publication being shown and its source URL.
- [ ] Confirm OpenAlex preview/import availability before promising a live lookup.
- [ ] For the staging showcase, verify the public synthetic-data disclaimer is visible on the hub and release detail pages. Only show provider-backed climate values as evidence after successful ingestion, independent review and approved publication.
- [ ] Confirm Climate Studio is accessible to the demo account at `/workspace/research/climate`; verify role permissions for ingestion, quality review and release publication.
- [ ] Verify the requested bounding box, dates, source licence, observation counts and sample values before approving a provider run.
- [ ] Verify the public release time series and full provenance page; confirm it contains no internal run IDs, raw coordinates or review notes. Check publication, source retrieval and represented period-end timestamps separately.
- [ ] Verify that public climate endpoints return published releases only and that pending/restricted/synthetic records are excluded.
- [ ] If ERA5 is not configured, show it as planned/configuration-required.
- [ ] If ODK Central is not connected, use only the local simulator and label all records synthetic.
- [ ] Confirm the four-track pilot content is presented as substantive but pending organisational review—not as accredited or finally approved training.
- [ ] Never call website-reported metrics audited impact.
- [ ] Keep API docs and the operations runbook available in a separate tab.

## Fallback language

- **Synthetic staging climate showcase:** “These published rainfall and temperature series are deterministic synthetic fixtures for demonstrating the public product. They are not measured conditions, forecasts, provider data or scientific findings. Production publication remains gated on real provider ingestion, independent quality review and authorised approval.”
- **Provider unavailable:** “The adapter is part of the platform design; this environment is not currently returning a live provider result. We are showing the recorded provider status rather than simulated climate values.”
- **No ODK Central endpoint:** “This is a deterministic synthetic protocol demonstration of the sync workflow, not a live ODK Central connection.”
- **Curriculum review pending:** “The four-track, 28-module/86-lesson pilot is substantively authored and seeded in staging, but it remains subject to subject-matter, clinical, safeguarding, accessibility and community review. It is not accredited training.”
- **Impact not verified:** “These figures are currently reported on the organisation's website. The platform is being designed to attach reporting periods, methods and evidence before leadership treats them as verified outcomes.”

## Extended demonstration

For a 15–20 minute session, use [the full founder demonstration and handover guide](../FOUNDER_DEMONSTRATION.md), followed by the research and curriculum blueprints.


## Research-linked climate insight check

- [ ] In the CMS authoring form, select **Climate insight** and link it to a currently published climate release and a separately published research publication.
- [ ] Submit the insight, obtain approval from a different authorised reviewer, then publish it.
- [ ] Verify the insight appears on the public Climate Intelligence page with both evidence links.
- [ ] Verify an insight linked to an unpublished, missing, superseded or retracted release is not returned by the anonymous API.
- [ ] If no valid release/publication pair exists, show the intentional no-insights state; do not create a synthetic public insight.


## Learning curriculum pilot check

- [ ] Confirm the API container startup seeded the default demo organisation `next-gen-for-earth-demo`; if staging uses another organisation slug, run the documented seed command for that slug.
- [ ] Verify the four published tracks, 28 modules, 86 substantive lessons and four formative quizzes are present; confirm four staff-only authoring drafts are available.
- [ ] Open one learner classroom and inspect course scope, module progress, lesson reading and source links.
- [ ] Confirm the quizzes expose questions/options but never expose correct answers before submission.
- [ ] Present the materials as pilot content pending subject-matter, safeguarding, clinical and community review—not as accredited training.


## Latest release and live staging checks

The expanded curriculum catalogue is live on staging commit `c379b20` (28 November 2026). All six CI jobs passed. Both Render web and API services report live; API health checks return HTTP 200.

- [Open staging website](https://nextgen-web-upag.onrender.com)
- [Open API health check](https://nextgen-api-au53.onrender.com/api/health)

Before presenting, complete the human browser checks below. A successful deployment and API health check do not replace visual, accessibility, responsive and authenticated user-flow acceptance.

- [ ] Open the public homepage and check navigation, typography, responsive layout and no-data states.
- [ ] Open Research & Publications and verify the 12 public-site publication entries.
- [ ] Open Climate Intelligence and verify source/methodology labels and the honest no-release/no-insight states where applicable.
- [ ] Sign in with an authorised staging account and open the research workspace and Climate Studio.
- [ ] Open one learner course and verify module progress, lesson content, official source links and quiz behaviour.
- [ ] Check keyboard navigation, focus states, contrast, narrow mobile width and error/loading states.
- [ ] Do not present pilot learning content as accredited training.


## Research portfolio source-library check (M122)

- [ ] Open `/workspace/research` with an authorised research account.
- [ ] Confirm the **Published research library** loads records from the selected organisation's public CMS catalogue.
- [ ] Confirm the number and titles match the public `/research` page; only published publication entries appear.
- [ ] Search for a known title and an author/journal phrase from the listing.
- [ ] Open a DOI/source link and verify it points to the listed source.
- [ ] Confirm the UI labels each item as a website listing and does not claim organisational authorship or link it to a study.
- [ ] Use **Create a new research study** to create a concept study; verify it appears in the study registry and remains subject to proposal/protocol/ethics governance.
- [ ] Verify loading, empty and API-error states do not show fabricated publication records.


## Publication catalogue metadata and filter acceptance (M137)

- [ ] Confirm the selected organisation's public CMS catalogue contains the 12 published website publication records (or reconcile against the current public website count).
- [ ] Confirm each card shows the website-sourced author string, journal/venue and DOI.
- [ ] Confirm the seeded catalogue year is visibly labelled as provisional pending DOI verification.
- [ ] Confirm editorial topic tags are explicitly labelled as editorial classifications, with provenance stating they are not source-reported keywords.
- [ ] Search by title, author surname, journal name and DOI; each search must return the expected source listing.
- [ ] Filter by publication year and editorial topic, including combinations with text search.
- [ ] Confirm DOI/source links open the exact external source represented by each card.
- [ ] Confirm the CMS source label remains visible and the records are not described as organisation-authored or linked to an organisation-owned study.
- [ ] Re-run the demo seed and confirm it updates metadata idempotently without creating duplicate publication entries.
- [ ] Create a separate concept study and verify the imported publication remains a source-catalogue record rather than being silently attached to that study.


## Learner operations walkthrough extension

- [ ] Confirm four published pathways and four private editable authoring drafts.
- [ ] Confirm four draft programme intake records appear in learning administration.
- [ ] Select a draft course and edit a module/lesson without changing its published learner counterpart.
- [ ] Demonstrate cohort configuration while leaving all demo cohorts in draft until safeguarding, consent and facilitator readiness are verified.
- [ ] Do not present synthetic learner records or demo intake dates as real admissions or programme commitments.
