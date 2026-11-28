export function slugifyOrganisationName(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120)
    .replace(/-+$/g, "");
}

export function resolveInitialOrganisationId<T extends { id: string }>(
  organisations: T[],
  requestedId: string | null,
): string {
  return organisations.find((organisation) => organisation.id === requestedId)?.id
    ?? organisations[0]?.id
    ?? "";
}
