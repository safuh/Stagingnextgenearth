export interface PortalMembership {
  roles: string[];
  status: "active" | "invited";
}

export type PortalDestination = "/workspace" | "/workspace/accept-invitation" | "/learners" | null;

export function resolvePortalDestination(
  memberships: PortalMembership[],
): PortalDestination {
  const active = memberships.filter((item) => item.status === "active");
  if (active.some((item) => item.roles.some((role) => role !== "learner"))) {
    return "/workspace";
  }
  if (memberships.some((item) => item.status === "invited")) {
    return "/workspace/accept-invitation";
  }
  if (active.some((item) => item.roles.includes("learner"))) {
    return "/learners";
  }
  return null;
}
