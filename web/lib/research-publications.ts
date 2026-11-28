export interface ImportedPublication {
  id: string;
  content_type: "publication";
  slug: string;
  title: string;
  summary: string | null;
  source_url?: string | null;
  metadata_json?: {
    authors?: string | string[];
    publication_date?: string;
    year?: number | string;
    publisher?: string;
    doi?: string;
    topic?: string;
  } | null;
}

export function publicPublicationCataloguePath(organizationSlug: string): string | null {
  const slug = organizationSlug.trim();
  if (!slug || slug.includes("/") || slug.includes("\\\\")) return null;
  return `/public/organizations/${encodeURIComponent(slug)}/content`;
}

export function filterImportedPublications(
  publications: ImportedPublication[],
  query: string,
): ImportedPublication[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return publications;
  return publications.filter((item) => {
    const authors = Array.isArray(item.metadata_json?.authors)
      ? item.metadata_json.authors.join(" ")
      : item.metadata_json?.authors ?? "";
    return [
      item.title,
      item.summary ?? "",
      authors,
      item.metadata_json?.publication_date ?? "",
      item.metadata_json?.year ?? "",
      item.metadata_json?.publisher ?? "",
      item.metadata_json?.doi ?? "",
      item.metadata_json?.topic ?? "",
    ].join(" ").toLowerCase().includes(normalized);
  });
}
