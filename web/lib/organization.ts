/** Canonical public organisation identity; override per deployment when needed. */
export const ORGANIZATION_SLUG =
  process.env.NEXT_PUBLIC_ORGANIZATION_SLUG?.trim() || "next-gen-for-earth";
