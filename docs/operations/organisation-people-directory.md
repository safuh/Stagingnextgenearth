# Organisation people directory

The directory stores a public-facing or internal profile independently from a portal
login account. Creating a directory record never creates a user, sends an invitation,
or grants application access.

## Access model

- All management endpoints require an active organisation membership with the
  `admin` role.
- Records are tenant-scoped by `organization_id`.
- New records default to `review_state=pending`, `visibility=private`,
  and `status=active`.
- The public feed includes only records where all three conditions hold:
  `review_state=verified`, `visibility=public`, and `status=active`.
- Public responses intentionally omit source attribution and internal actor IDs.
- Use `status=inactive` to archive a record without deleting historical data.

## Management endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/organizations/{organization_id}/people` | List all tenant profiles |
| POST | `/api/organizations/{organization_id}/people` | Create a private profile |
| PATCH | `/api/organizations/{organization_id}/people/{person_id}` | Edit, verify, publish or archive |
| GET | `/api/public/organizations/{organization_slug}/people` | Read published profiles |

Supported person classifications include employee, board member, executive,
volunteer, ambassador, researcher, mentor, advisor, intern, trainee, consultant
and alumnus. A person may have multiple classifications and multiple position
titles.

## Safe initial workflow

1. Create a profile using a source URL and source label where available.
2. Confirm the person's identity, current affiliation, title and permission to
   publish the biography or profile image.
3. Set `review_state=verified` only after that review.
4. Set `visibility=public` only when the person and organisation have approved
   public display.
5. Set `status=inactive` when the profile should no longer appear publicly.

Do not treat a name on an old website page as proof of current employment or
consent to publish. Do not import personal email addresses or create accounts
from public directory entries. Send a separate invitation only after confirming
the intended account identifier and the person's role.

## Example API calls

Create a private record:

```bash
curl -X POST \
  "$API_URL/api/organizations/$ORG_ID/people" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Example Researcher",
    "positions": ["Researcher", "Regional Ambassador"],
    "person_types": ["researcher", "ambassador"],
    "country_code": "KE",
    "region": "Nairobi",
    "source_url": "https://nextgenforearth.org/",
    "source_label": "Organisation website"
  }'
```

Verify and publish after review:

```bash
curl -X PATCH \
  "$API_URL/api/organizations/$ORG_ID/people/$PERSON_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"review_state":"verified","visibility":"public"}'
```

Read the public feed:

```bash
curl "$API_URL/api/public/organizations/$ORG_SLUG/people"
```

The management screen is available at `/workspace/administration/people` to
organisation administrators. The API remains the authorization boundary.

## Deployment

Apply the migration during the release migration step:

```bash
uv run alembic upgrade head
```

Run the targeted regression suite and then the complete quality suite:

```bash
uv run pytest -q tests/test_organization_people.py
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
```

The public feed is not a substitute for a reviewed CMS publishing workflow.
Website catalogue import, append-only per-profile audit history, invitations
for new accounts, and broader permission-based HR workflows remain follow-on work.
