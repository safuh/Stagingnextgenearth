"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

type ResearchRecord = {
  id: string;
  content_type: string;
  title: string;
  summary: string | null;
  body: string | null;
  slug: string;
  source_url?: string | null;
  metadata_json?: {
    authors?: string | string[];
    publication_date?: string;
    year?: number | string;
    publisher?: string;
    doi?: string;
    topic?: string;
  } | null;
};

export default function ResearchPage() {
  const [records, setRecords] = useState<ResearchRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    apiGet<ResearchRecord[]>(`/public/organizations/${ORGANIZATION_SLUG}/content`)
      .then((items) => {
        if (active) setRecords(items.filter((item) =>
          item.content_type === "publication" || item.content_type === "research_area"
        ));
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Research catalogue could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const publications = useMemo(
    () => records.filter((item) => item.content_type === "publication"),
    [records],
  );
  const areas = useMemo(
    () => records.filter((item) => item.content_type === "research_area"),
    [records],
  );

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <nav aria-label="Research navigation">
          <Link className="secondary-action" href="/#research">Home</Link>
          <Link className="secondary-action" href="/#programmes">Programmes</Link>
        </nav>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">EVIDENCE, KNOWLEDGE & CLIMATE INTELLIGENCE</p>
        <h1 className="workspace-title">Research & publications</h1>
        <p className="workspace-muted">
          Explore research themes and knowledge products published in the NextGen For Earth catalogue.
          Records are maintained through the organisation workspace.
        </p>

        {loading ? (
          <p className="workspace-muted" role="status">Loading the research catalogue…</p>
        ) : error ? (
          <section className="staff-card">
            <h2>Research catalogue unavailable</h2>
            <p className="workspace-error" role="alert">{error}</p>
            <p className="workspace-muted">The catalogue could not be retrieved from the public API. Please try again later.</p>
          </section>
        ) : (
          <>
            <section className="staff-card">
              <h2>Research themes</h2>
              {areas.length === 0 ? (
                <p className="workspace-muted">Research themes will appear here when published by the organisation.</p>
              ) : (
                <div className="portal-grid">
                  {areas.map((item) => (
                    <article className="portal-card" key={item.id}>
                      <p className="portal-tag">Research area</p>
                      <h3>{item.title}</h3>
                      {(item.summary || item.body) && <p className="portal-description">{item.summary || item.body}</p>}
                    </article>
                  ))}
                </div>
              )}
            </section>
            <section className="staff-card">
              <h2>Publications & knowledge products</h2>
              {publications.length === 0 ? (
                <p className="workspace-muted">Published research outputs will appear here as records are approved.</p>
              ) : (
                <div className="portal-grid">
                  {publications.map((item) => {
                    const authors = item.metadata_json?.authors;
                    const authorText = Array.isArray(authors) ? authors.join(", ") : authors;
                    const year = item.metadata_json?.year || item.metadata_json?.publication_date;
                    return (
                      <article className="portal-card" key={item.id}>
                        <p className="portal-tag">Publication{year ? ` · ${year}` : ""}</p>
                        <h3>{item.title}</h3>
                        {authorText && <p className="portal-description">{authorText}</p>}
                        {(item.summary || item.body) && <p className="portal-description">{item.summary || item.body}</p>}
                        {item.metadata_json?.publisher && <p className="portal-tag">{item.metadata_json.publisher}</p>}
                        {item.metadata_json?.doi && <p className="portal-description">DOI: {item.metadata_json.doi}</p>}
                        {item.source_url && (
                          <a href={item.source_url} target="_blank" rel="noreferrer">
                            Read source <span aria-hidden="true">↗</span>
                          </a>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </>
        )}
        <p><Link href="/#access">Access the organisation workspace</Link></p>
      </section>
    </main>
  );
}
