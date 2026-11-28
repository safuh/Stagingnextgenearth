export interface ResearchPublicationRecord {
  title: string;
  summary: string | null;
  slug: string;
  metadata_json?: {
    authors?: string | string[];
    publication_date?: string;
    year?: number | string;
    publisher?: string;
    doi?: string;
    topic?: string;
  } | null;
}

export interface ResearchPublicationFilters {
  search?: string;
  year?: string;
  topic?: string;
}

export function researchPublicationYear(item: ResearchPublicationRecord): string {
  const value = item.metadata_json?.year ?? item.metadata_json?.publication_date;
  return typeof value === "number"
    ? String(value)
    : typeof value === "string"
      ? value.slice(0, 4)
      : "";
}

export function researchPublicationFilterOptions(items: ResearchPublicationRecord[]): {
  years: string[];
  topics: string[];
} {
  return {
    years: Array.from(new Set(items.map(researchPublicationYear).filter(Boolean))).sort().reverse(),
    topics: Array.from(new Set(
      items
        .map((item) => item.metadata_json?.topic)
        .filter((value): value is string => typeof value === "string" && value.length > 0),
    )).sort(),
  };
}

export function filterResearchPublications<T extends ResearchPublicationRecord>(
  items: T[],
  filters: ResearchPublicationFilters,
): T[] {
  const query = filters.search?.trim().toLowerCase() ?? "";
  return items.filter((item) => {
    const authors = item.metadata_json?.authors;
    const authorText = typeof authors === "string"
      ? authors
      : Array.isArray(authors)
        ? authors.join(" ")
        : "";
    const searchText = [
      item.title,
      item.summary,
      item.slug,
      item.metadata_json?.topic,
      item.metadata_json?.publisher,
      item.metadata_json?.doi,
      authorText,
      researchPublicationYear(item),
    ]
      .filter((value): value is string => typeof value === "string")
      .join(" ")
      .toLowerCase();
    return searchText.includes(query)
      && (!filters.year || researchPublicationYear(item) === filters.year)
      && (!filters.topic || item.metadata_json?.topic === filters.topic);
  });
}
