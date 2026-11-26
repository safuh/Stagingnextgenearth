import assert from "node:assert/strict";
import test from "node:test";
import { resolvePortalDestination } from "../lib/portal-routing";

test("routes an active staff member to the organisation workspace", () => {
  assert.equal(resolvePortalDestination([{ status: "active", roles: ["employee"] }]), "/workspace");
});

test("routes an invited staff identity to invitation acceptance", () => {
  assert.equal(resolvePortalDestination([{ status: "invited", roles: ["researcher"] }]), "/workspace/accept-invitation");
});

test("routes a learner-only identity to the learner portal", () => {
  assert.equal(resolvePortalDestination([{ status: "active", roles: ["learner"] }]), "/learners");
});

test("prioritises active staff access when a person has multiple roles", () => {
  assert.equal(resolvePortalDestination([
    { status: "active", roles: ["learner"] },
    { status: "active", roles: ["researcher", "employee"] },
  ]), "/workspace");
});

test("does not infer access for an authenticated identity without memberships", () => {
  assert.equal(resolvePortalDestination([]), null);
});
