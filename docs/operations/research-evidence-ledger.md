# Research evidence ledger

The study evidence ledger is a read-only, tenant-scoped traceability snapshot:

`GET /api/organizations/{organization_id}/research-studies/{study_id}/evidence-ledger?limit=100`

It joins approved study datasets and their currently available, malware-clean file manifests with recorded analysis runs, study publications and OpenAlex metadata provenance counts, study protocol/ethics governance states, and climate observation quality totals. Governance output is summary metadata only: protocol version count and latest status/review decision, ethics decision count and latest outcome/reference, and the study lifecycle/ethics reference. Protocol contents, reviewer identities and private review notes are not included.

Each analysis run reports whether its recorded input manifest digest matches the current approved dataset manifest. A mismatch is a traceability warning, not proof of tampering; a match establishes digest equality only, not scientific validity.

The response is bounded to 500 datasets, runs and publications. Each dataset manifest is bounded to 1,000 file versions. It contains identifiers, hashes, counts and metadata only; it never returns storage keys, download URLs or file contents. Climate observations are summarized by review state and date range; measurement values are not copied into this ledger.

Access requires active membership and access to the requested study through the existing study collaborator / organisation role policy. This report is an inventory, not independent validation, a reproducibility guarantee, or an impact claim.

## CSV export

Download the same bounded report as a spreadsheet-safe CSV:

`GET /api/organizations/{organization_id}/research-studies/{study_id}/evidence-ledger/export?limit=100`

The export uses the same active-membership and study-access checks as the JSON endpoint, retains deterministic record ordering, includes the study snapshot, protocol and ethics governance summary, dataset fingerprints, analysis-run lineage, publication provenance counts and climate review summary, and applies formula-injection neutralization to text cells. It is UTF-8 with a byte-order mark for spreadsheet compatibility. The CSV deliberately excludes file names and storage locations, download links, file bytes and individual climate measurements.
