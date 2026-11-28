from stagingnextgenearth.api.public_content import _public_metadata


def test_public_metadata_only_exposes_approved_presentation_fields() -> None:
    metadata = {
        "display_value": "12",
        "authors": ["A. Researcher"],
        "year": 2025,
        "year_provenance": (
            "Seed catalogue year; verify against the DOI landing page before treating as canonical."
        ),
        "publisher": "Example Journal",
        "doi": "https://doi.org/10.0000/example",
        "topic": "Legacy topic should not be public",
        "editorial_topic": "Climate and health",
        "editorial_topic_provenance": (
            "Editorial discovery tag assigned by the demo seed; not a source-reported keyword."
        ),
        "release_slug": "kilifi-monthly-rainfall",
        "publication_slug": "heat-maternal-health-kilifi",
        "region": "Kilifi County, Kenya",
        "indicator": "Rainfall",
        "evidence_note": "Context only.",
        "gallery": [
            {"alt": "Field work", "image_url": "/media/field.jpg"},
            {"alt": "Remote image", "image_url": "https://images.example/field.jpg"},
            {"alt": "Unsafe scheme", "image_url": "javascript:alert(1)"},
            {"alt": 42, "image_url": "/media/invalid.jpg"},
        ],
        "source_status": "internal review note",
        "source_capture": "https://internal.example/capture",
        "image_manifest": "scripts/data/private-manifest.json",
        "rights_note": "Internal note",
    }

    result = _public_metadata(metadata)

    assert result["display_value"] == "12"
    assert result["authors"] == ["A. Researcher"]
    assert result["year"] == 2025
    assert result["year_provenance"].startswith("Seed catalogue year;")
    assert result["editorial_topic"] == "Climate and health"
    assert result["editorial_topic_provenance"].startswith("Editorial discovery tag")
    assert "topic" not in result
    assert result["release_slug"] == "kilifi-monthly-rainfall"
    assert result["publication_slug"] == "heat-maternal-health-kilifi"
    assert result["region"] == "Kilifi County, Kenya"
    assert result["indicator"] == "Rainfall"
    assert result["evidence_note"] == "Context only."
    assert result["gallery"] == [
        {"alt": "Field work", "image_url": "/media/field.jpg"},
        {"alt": "Remote image", "image_url": "https://images.example/field.jpg"},
    ]
    assert "source_status" not in result
    assert "source_capture" not in result
    assert "image_manifest" not in result
    assert "rights_note" not in result


def test_public_metadata_handles_missing_or_non_object_values() -> None:
    assert _public_metadata(None) == {}
    assert _public_metadata("not metadata") == {}
