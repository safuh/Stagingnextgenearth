# Research dataset integrity manifests

The tenant-scoped endpoint

`GET /api/organizations/{organization_id}/research-datasets/{dataset_id}/manifest`

returns a deterministic SHA-256 digest for an **approved** dataset. Only file
versions that are both `available` and malware-scan `clean`, and have a
recorded SHA-256, participate in the manifest. Pending, rejected, quarantined,
deleted, and un-hashed files are excluded.

The digest is calculated from canonical JSON containing the dataset ID,
dataset version, and ordered file identity, version, filename, media type,
size, and content SHA-256. The response never includes object-storage keys,
signed URLs, or file contents. It is therefore suitable for recording as an
input-manifest reference in a later analysis execution, but does not itself
execute or certify an analysis.

Access requires active organisation membership and a research-capable
organisation role or active study collaboration. Restricted datasets remain
limited to their owner, privileged organisation roles, or study collaborators.
