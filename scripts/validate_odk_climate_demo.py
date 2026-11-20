#!/usr/bin/env python3
"""Validate the checked-in ODK climate demo XLSForm and synthetic OData fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples/odk/climate-observation"
FORM = DEMO / "nextgen_climate_observation.xlsx"
FIXTURE = DEMO / "sample_odata_submissions.json"
REQUIRED_FIELDS = {
    "site_code",
    "observed_at",
    "measurement",
    "value",
    "unit",
    "latitude",
    "longitude",
}


def main() -> int:
    workbook = load_workbook(FORM, read_only=True, data_only=True)
    if not {"survey", "choices", "settings"}.issubset(workbook.sheetnames):
        raise SystemExit("XLSForm must contain survey, choices, and settings sheets")
    survey = workbook["survey"]
    headers = [cell.value for cell in next(survey.iter_rows(min_row=1, max_row=1))]
    name_index = headers.index("name")
    names = {
        row[name_index] for row in survey.iter_rows(min_row=2, values_only=True) if row[name_index]
    }
    missing = REQUIRED_FIELDS - names
    if missing:
        raise SystemExit(f"XLSForm missing required fields: {sorted(missing)}")
    settings = workbook["settings"]
    setting_headers = [cell.value for cell in next(settings.iter_rows(min_row=1, max_row=1))]
    setting = dict(
        zip(
            setting_headers,
            next(settings.iter_rows(min_row=2, values_only=True)),
            strict=True,
        )
    )
    if setting.get("form_id") != "nextgen_climate_observation":
        raise SystemExit("Unexpected XLSForm form_id")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    submissions = fixture.get("value")
    if not isinstance(submissions, list) or len(submissions) < 2:
        raise SystemExit("Expected at least two synthetic OData submissions")
    for row in submissions:
        if not isinstance(row, dict) or not row.get("__id"):
            raise SystemExit("Every synthetic submission needs an ODK __id")
        absent = REQUIRED_FIELDS - row.keys()
        if absent:
            raise SystemExit(f"Submission {row.get('__id')} missing {sorted(absent)}")
        if not isinstance(row.get("value"), (int, float)):
            raise SystemExit(f"Submission {row['__id']} has a non-numeric value")
        if not -90 <= float(row["latitude"]) <= 90 or not -180 <= float(row["longitude"]) <= 180:
            raise SystemExit(f"Submission {row['__id']} has invalid coordinates")
    print(f"ODK demo valid: {FORM.relative_to(ROOT)}; {len(submissions)} synthetic submissions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
