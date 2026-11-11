import assert from "node:assert/strict";
import test from "node:test";

import { isSameOriginMutation, safeApiPath } from "../lib/session-policy.ts";

test("safe methods do not require an Origin header", () => {
  assert.equal(isSameOriginMutation("GET", null, "https://app.example.org"), true);
});

test("mutations require an exact same-origin header", () => {
  const origin = "https://app.example.org";
  assert.equal(isSameOriginMutation("POST", origin, origin), true);
  assert.equal(isSameOriginMutation("POST", "https://attacker.example", origin), false);
  assert.equal(isSameOriginMutation("POST", null, origin), false);
});

test("API path segments are encoded without changing path boundaries", () => {
  assert.equal(safeApiPath(["organizations", "org id", "programmes"]), "organizations/org%20id/programmes");
  assert.equal(safeApiPath(["research", "a/b"]), "research/a%2Fb");
});

test("empty and traversal path segments are rejected", () => {
  assert.equal(safeApiPath([]), null);
  assert.equal(safeApiPath(["organizations", "..", "secrets"]), null);
  assert.equal(safeApiPath(["organizations", ""]), null);
});
