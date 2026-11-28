import assert from "node:assert/strict";
import test from "node:test";
import {
  filterResearchPublications,
  researchPublicationFilterOptions,
  type ResearchPublicationRecord,
} from "../lib/research-publications.ts";

const records: ResearchPublicationRecord[] = [
  {
    title: "Heat and health in Kilifi",
    summary: "A community study",
    slug: "heat-health-kilifi",
    metadata_json: {
      authors: "Lusambili A et al.",
      publisher: "Frontiers in Public Health",
      year: 2025,
      topic: "Maternal Health",
      doi: "10.1000/heat.2025",
    },
  },
  {
    title: "Youth climate strategies",
    summary: "A regional review",
    slug: "youth-climate-strategies",
    metadata_json: {
      authors: ["Njoroge J", "Otieno P"],
      publisher: "Climate and Health",
      publication_date: "2024-06-01",
      topic: "Youth & Climate",
      doi: "10.1000/youth.2024",
    },
  },
  {
    title: "Metadata incomplete",
    summary: null,
    slug: "metadata-incomplete",
    metadata_json: null,
  },
];

test("publication filters search authors, journal, DOI and title", () => {
  assert.equal(filterResearchPublications(records, { search: "Lusambili" }).length, 1);
  assert.equal(filterResearchPublications(records, { search: "Frontiers" }).length, 1);
  assert.equal(filterResearchPublications(records, { search: "10.1000/youth" }).length, 1);
  assert.equal(filterResearchPublications(records, { search: "metadata incomplete" }).length, 1);
});

test("publication year and topic filters compose with text search", () => {
  const result = filterResearchPublications(records, {
    search: "climate",
    year: "2024",
    topic: "Youth & Climate",
  });
  assert.equal(result.length, 1);
  assert.equal(result[0].slug, "youth-climate-strategies");
});

test("filter options use available source metadata and omit unknown values", () => {
  assert.deepEqual(researchPublicationFilterOptions(records), {
    years: ["2025", "2024"],
    topics: ["Maternal Health", "Youth & Climate"],
  });
});
