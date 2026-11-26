# Seven-minute Founder Demo Runbook

**Environment:** dedicated staging/demo environment  
**Rule:** show only workflows verified in the current build; label imported, external and synthetic records.

| Time | Screen | Demonstration |
|---|---|---|
| 00:00–00:40 | Public website | Establish mission, programme pillars, research and published impact claims. Identify website-reported figures as source claims. Open the Climate Intelligence hub if a published release is available; show source, data class, period and limitations. |
| 00:40–01:30 | Founder/admin | Show organisation overview, roles, people directory, partner verification and governance/audit controls. |
| 01:30–02:40 | Research library | Open a website-imported publication, show source provenance, preview external scholarly metadata and create a new study saved as concept. |
| 02:40–03:30 | Research governance | Show proposal/protocol/ethics gates, dataset registration, submission/review and analysis provenance. Do not imply a concept is approved. |
| 03:30–04:40 | Climate intelligence | Show provider catalogue and a successful NASA POWER/CHIRPS ingestion if available. Display source, units, period, coverage and quality state. Otherwise show provider status and last successful run. |
| 04:40–05:20 | Field data | If live Central is unavailable, demonstrate the synthetic ODK simulator. Label every fixture Synthetic demo; show mapping, pagination, duplicate suppression and pending review. |
| 05:20–06:20 | Learning | Show the four proposed curriculum tracks and course authoring/enrolment/assessment path. Explicitly distinguish draft blueprint and placeholder lessons from approved content. |
| 06:20–07:00 | Leadership / close | Show available organisational indicators, distinguish operational counts from verified outcomes, and close on one connected operating platform. |

## Pre-demo checks

- [ ] Confirm the public web page and API health endpoint respond.
- [ ] Record the deployed commit SHA and deployment timestamp.
- [ ] Confirm founder/admin access with a dedicated demo account.
- [ ] Use synthetic learner/staff accounts; never expose real credentials or private invitations.
- [ ] Verify the research publication being shown and its source URL.
- [ ] Confirm OpenAlex preview/import availability before promising a live lookup.
- [ ] Confirm a recent successful climate-provider ingestion and an independently approved, published public release before showing public climate values.
- [ ] Verify that public climate endpoints return published releases only and that pending/restricted/synthetic records are excluded.
- [ ] If ERA5 is not configured, show it as planned/configuration-required.
- [ ] If ODK Central is not connected, use only the local simulator and label all records synthetic.
- [ ] Confirm courses/lessons shown are reviewed; if not, label them draft/placeholder.
- [ ] Never call website-reported metrics audited impact.
- [ ] Keep API docs and the operations runbook available in a separate tab.

## Fallback language

- **No public climate release:** “The public climate intelligence experience is being built on the provider and research infrastructure. We only publish values after provenance, quality and disclosure review; this environment does not yet have an approved public release.”
- **Provider unavailable:** “The adapter is part of the platform design; this environment is not currently returning a live provider result. We are showing the recorded provider status rather than simulated climate values.”
- **No ODK Central endpoint:** “This is a deterministic synthetic protocol demonstration of the sync workflow, not a live ODK Central connection.”
- **Curriculum not approved:** “These are proposed curriculum structures for subject-matter review. The existing seeded lesson text is not final instructional content.”
- **Impact not verified:** “These figures are currently reported on the organisation's website. The platform is being designed to attach reporting periods, methods and evidence before leadership treats them as verified outcomes.”

## Extended demonstration

For a 15–20 minute session, use [the full founder demonstration and handover guide](../FOUNDER_DEMONSTRATION.md), followed by the research and curriculum blueprints.
