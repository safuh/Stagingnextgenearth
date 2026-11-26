"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

type Release = {
  id: string;
  slug: string;
  version: number;
  title: string;
  summary: string;
  indicator: string;
  unit: string;
  provider_id: string;
  provider_product: string;
  data_class: string;
  geography_label: string;
  geography_resolution: string;
  period_start: string;
  period_end: string;
  baseline: string | null;
  coverage_pct: number | null;
  missingness_pct: number | null;
  license_name: string;
  attribution: string;
  citation_url: string | null;
  published_at: string | null;
};
type Overview = {
  organization: string;
  release_count: number;
  indicators: string[];
  latest_published_at: string | null;
};

const dataClassLabels: Record<string, string> = {
  station_observation: "Station observation",
  satellite_estimate: "Satellite estimate",
  reanalysis: "Reanalysis",
  forecast: "Forecast",
  projection: "Climate projection",
};

export default function ClimateIntelligencePage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [releases, setReleases] = useState<Release[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      apiGet<Overview>(`/public/organizations/${ORGANIZATION_SLUG}/climate/overview`),
      apiGet<Release[]>(`/public/organizations/${ORGANIZATION_SLUG}/climate/releases?limit=100`),
    ]).then(([summary, items]) => {
      if (!active) return;
      setOverview(summary);
      setReleases(items);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Climate intelligence is temporarily unavailable.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <nav aria-label="Climate intelligence navigation">
          <Link className="secondary-action" href="/">Home</Link>
          <Link className="secondary-action" href="/research">Research</Link>
        </nav>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">CLIMATE SCIENCE TO ACTION</p>
        <h1 className="workspace-title">Climate intelligence</h1>
        <p className="workspace-muted">
          Explore published climate evidence with its source, data class, geography,
          period, method and limitations. Public values appear only after an
          organisation review and publication process.
        </p>
        <div className="staff-card">
          <h2>Evidence catalogue</h2>
          {loading ? (
            <p className="workspace-muted" role="status">Loading published climate releases…</p>
          ) : error ? (
            <>
              <p className="workspace-error" role="alert">{error}</p>
              <p className="workspace-muted">The climate catalogue could not be retrieved. Please try again later.</p>
            </>
          ) : releases.length === 0 ? (
            <>
              <p className="workspace-muted">
                No climate releases have been approved and published yet.
                Provider ingestion and internal research observations are not
                automatically public.
              </p>
              <p className="workspace-muted">
                This catalogue will show rainfall, temperature and seasonal
                indicators when a provider-backed release has passed source,
                licence, quality and publication review.
              </p>
            </>
          ) : (
            <div className="portal-grid">
              {releases.map((release) => (
                <article className="portal-card" key={release.id}>
                  <p className="portal-tag">
                    {dataClassLabels[release.data_class] ?? release.data_class} · v{release.version}
                  </p>
                  <h3>{release.title}</h3>
                  <p className="portal-description">{release.summary}</p>
                  <p className="portal-tag">{release.indicator} · {release.unit}</p>
                  <p className="portal-description">{release.geography_label} · {release.geography_resolution}</p>
                  <p className="portal-description">
                    {new Date(release.period_start).toLocaleDateString()} – {new Date(release.period_end).toLocaleDateString()}
                  </p>
                  <p className="portal-tag">Source: {release.provider_product}</p>
                  <Link href={`/climate-intelligence/${release.slug}`}>Explore evidence →</Link>
                </article>
              ))}
            </div>
          )}
          {overview && !loading && !error && (
            <p className="workspace-muted">
              {overview.release_count} published release{overview.release_count === 1 ? "" : "s"}
              {overview.latest_published_at
                ? ` · Updated ${new Date(overview.latest_published_at).toLocaleDateString()}`
                : ""}
            </p>
          )}
        </div>
        <div className="staff-card">
          <h2>How to read this evidence</h2>
          <ul>
            <li>Station observations, satellite estimates and reanalysis are different data classes.</li>
            <li>Coverage and missingness describe data availability, not certainty.</li>
            <li>Historical data are not live conditions or forecasts.</li>
            <li>Climate-health context is descriptive and does not establish causation or individual health risk.</li>
          </ul>
          <p><Link href="/climate-intelligence/methodology">Methodology and source notes</Link></p>
        </div>
      </section>
    </main>
  );
}
