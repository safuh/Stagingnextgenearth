import assert from "node:assert/strict";
import test from "node:test";
import { isPublicClimateRead } from "../lib/public-cache.ts";

test("only anonymous public climate GET and HEAD routes carry validators", () => {
  assert.equal(isPublicClimateRead("GET", "public/organizations/demo/climate/overview"), true);
  assert.equal(isPublicClimateRead("GET", "public/organizations/demo/climate/releases"), true);
  assert.equal(isPublicClimateRead("GET", "public/organizations/demo/climate/releases/rainfall"), true);
  assert.equal(isPublicClimateRead("GET", "public/organizations/demo/climate/releases/rainfall/series"), true);
  assert.equal(isPublicClimateRead("GET", "public/organizations/demo/climate/sources"), true);
  assert.equal(isPublicClimateRead("GET", "public/organizations/demo/climate/insights"), true);
  assert.equal(isPublicClimateRead("POST", "public/organizations/demo/climate/releases"), false);
  assert.equal(isPublicClimateRead("GET", "organizations/demo/climate-ingestion"), false);
  assert.equal(isPublicClimateRead("GET", "public/organizations/demo/members"), false);
});
