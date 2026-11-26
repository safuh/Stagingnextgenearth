from stagingnextgenearth.api.public_content import _public_metadata


def test_public_metadata_only_exposes_approved_presentation_fields() -> None:
    metadata = {
        "display_value": "12",
        "authors": ["A. Researcher"],
        "year": 2025,
        "publisher": "Example Journal",
        "doi": "https://doi.org/10.0000/example",
        "topic": "Climate and health",
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
