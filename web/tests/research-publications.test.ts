import assert from "node:assert/strict";
import test from "node:test";

import {
  filterImportedPublications,
  publicPublicationCataloguePath,
  type ImportedPublication,
} from "../lib/research-publications";

const references: ImportedPublication[] = [
  {
    id: "pub-1",
    content_type: "publication",
    slug: "heat-and-maternal-health",
    title: "Heat exposure and maternal health in coastal Kenya",
    summary: "A community-based study in Kilifi.",
    source_url: "https://example.org/publication/heat",
    metadata_json: {
      authors: ["A. Researcher", "B. Scientist"],
      publication_date: "2024-06-01",
      year: 2024,
      publisher: "Journal of Climate and Health",
      doi: "10.1000/example.1",
      topic: "maternal health",
    },
  },
  {
    id: "pub-2",
    content_type: "publication",
    slug: "youth-climate-research",
    title: "Youth-inclusive climate research",
    summary: "Methods for youth participation.",
    source_url: "https://example.org/publication/youth",
    metadata_json: { authors: "C. Author", year: "2023", topic: "youth" },
  },
];

test("publication search matches title, authors, year, publisher, DOI, topic and summary", () => {
  for (const query of [
    "maternal health",
    "A. Researcher",
    "2024",
    "Journal of Climate",
    "10.1000/example.1",
    "coastal Kenya",
    "youth-inclusive",
  ]) {
    assert.equal(filterImportedPublications(references, query).length, 1, query);
  }
});

test("publication search is case-insensitive and trims whitespace", () => {
  assert.deepEqual(
    filterImportedPublications(references, "  KILIFI  ").map((item) => item.id),
    ["pub-1"],
  );
});

test("empty search returns the complete source list without mutation", () => {
  assert.deepEqual(filterImportedPublications(references, "  "), references);
  assert.equal(references.length, 2);
});

test("public catalogue path is built from the selected tenant slug", () => {
  assert.equal(
    publicPublicationCataloguePath("next-gen-for-earth-demo"),
    "/public/organizations/next-gen-for-earth-demo/content",
  );
  assert.equal(publicPublicationCataloguePath("other org"), "/public/organizations/other%20org/content");
  assert.equal(publicPublicationCataloguePath(""), null);
  assert.equal(publicPublicationCataloguePath("org/other"), null);
});
