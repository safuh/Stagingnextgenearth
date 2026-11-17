# Research evidence ledger

The study evidence ledger is a read-only, tenant-scoped traceability snapshot:

`GET /api/organizations/{organization_id}/research-studies/{study_id}/evidence-ledger?limit=100`

It joins approved study datasets and their currently available, malware-clean file manifests with recorded analysis runs, study publications and OpenAlex metadata provenance counts, and climate observation quality totals.

Each analysis run reports whether its recorded input manifest digest matches the current approved dataset manifest. A mismatch is a traceability warning, not proof of tampering; a match establishes digest equality only, not scientific validity.

The response is bounded to 500 datasets, runs and publications. Each dataset manifest is bounded to 1,000 file versions. It contains identifiers, hashes, counts and metadata only; it never returns storage keys, download URLs or file contents. Climate observations are summarized by review state and date range; measurement values are not copied into this ledger.

Access requires active membership and access to the requested study through the existing study collaborator / organisation role policy. This report is an inventory, not independent validation, a reproducibility guarantee, or an impact claim.
