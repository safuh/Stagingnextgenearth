import assert from "node:assert/strict";
import test from "node:test";
import {
  resolveInitialOrganisationId,
  slugifyOrganisationName,
} from "../lib/organisation-onboarding.ts";

test("organisation slug is URL-safe and normalises accents and punctuation", () => {
  assert.equal(slugifyOrganisationName("  Éast Africa Climate & Health Network!  "), "east-africa-climate-health-network");
});

test("organisation slug trims repeated separators and caps the API limit", () => {
  assert.equal(slugifyOrganisationName("---Climate___Research---"), "climate-research");
  assert.equal(slugifyOrganisationName("a".repeat(140)).length, 120);
});

test("organisation slug can be empty until a valid name is supplied", () => {
  assert.equal(slugifyOrganisationName("***"), "");
});

test("requested organisation is selected when it belongs to the caller", () => {
  assert.equal(resolveInitialOrganisationId([{ id: "a" }, { id: "b" }], "b"), "b");
});

test("unknown requested organisation falls back to the first active membership", () => {
  assert.equal(resolveInitialOrganisationId([{ id: "a" }, { id: "b" }], "missing"), "a");
  assert.equal(resolveInitialOrganisationId([], null), "");
});
