#!/usr/bin/env python3
"""Validate the checked-in ODK climate demo XLSForm and synthetic OData fixture."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

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


_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if letters is None:
        raise SystemExit(f"Invalid XLSX cell reference: {reference}")
    index = 0
    for character in letters.group(0):
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def _read_xlsform(path: Path) -> dict[str, list[list[object]]]:
    """Read the small XLSForm workbook using only Python's standard library."""
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships.findall(f"{_PKG_REL_NS}Relationship")
        }
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(text.text or "" for text in item.iter(f"{_MAIN_NS}t"))
                for item in shared_root.findall(f"{_MAIN_NS}si")
            ]
        sheets: dict[str, list[list[object]]] = {}
        for sheet in workbook.findall(f"{_MAIN_NS}sheets/{_MAIN_NS}sheet"):
            name = sheet.attrib["name"]
            target = targets[sheet.attrib[f"{_DOC_REL_NS}id"]]
            member = (
                str(PurePosixPath("xl") / target.lstrip("/"))
                if not target.startswith("/")
                else target.lstrip("/")
            )
            root = ET.fromstring(archive.read(member))
            rows: list[list[object]] = []
            for row in root.findall(f"{_MAIN_NS}sheetData/{_MAIN_NS}row"):
                values: list[object] = []
                for cell in row.findall(f"{_MAIN_NS}c"):
                    reference = cell.attrib.get("r", "")
                    index = _column_index(reference)
                    while len(values) <= index:
                        values.append(None)
                    cell_type = cell.attrib.get("t")
                    if cell_type == "inlineStr":
                        value: object = "".join(
                            part.text or "" for part in cell.iter(f"{_MAIN_NS}t")
                        )
                    else:
                        raw = cell.findtext(f"{_MAIN_NS}v")
                        if cell_type == "s" and raw is not None:
                            value = shared_strings[int(raw)]
                        else:
                            value = raw
                    values[index] = value
                rows.append(values)
            sheets[name] = rows
        return sheets


def main() -> int:
    workbook = _read_xlsform(FORM)
    if not {"survey", "choices", "settings"}.issubset(workbook):
        raise SystemExit("XLSForm must contain survey, choices, and settings sheets")
    survey = workbook["survey"]
    if not survey:
        raise SystemExit("XLSForm survey sheet is empty")
    headers = survey[0]
    if "name" not in headers:
        raise SystemExit("XLSForm survey sheet must contain a name column")
    name_index = headers.index("name")
    names = {row[name_index] for row in survey[1:] if len(row) > name_index and row[name_index]}
    missing = REQUIRED_FIELDS - names
    if missing:
        raise SystemExit(f"XLSForm missing required fields: {sorted(missing)}")
    settings = workbook["settings"]
    if len(settings) < 2:
        raise SystemExit("XLSForm settings sheet must contain a settings row")
    setting_headers = settings[0]
    setting = dict(zip(setting_headers, settings[1], strict=False))
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
