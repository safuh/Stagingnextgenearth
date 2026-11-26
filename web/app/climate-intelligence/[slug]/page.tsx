"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
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
  provider_version: string | null;
  data_class: string;
  geography_label: string;
  geography_resolution: string;
  period_start: string;
  period_end: string;
  baseline: string | null;
  aggregation_method: string;
  coverage_pct: number | null;
  missingness_pct: number | null;
  uncertainty_summary: string | null;
  limitations: string;
  license_name: string;
  attribution: string;
  terms_url: string | null;
  citation_url: string | null;
  published_at: string | null;
};
type Series = {
  release: Release;
  series: Array<{ observed_at: string; value: number }>;
  regions: Array<{ region: string; value: number; coverage_pct: number | null }>;
};

export default function ClimateReleasePage() {
  const params = useParams<{ slug: string }>();
  const [data, setData] = useState<Series | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    apiGet<Series>(
      `/public/organizations/${ORGANIZATION_SLUG}/climate/releases/${encodeURIComponent(params.slug)}/series`,
    ).then((result) => {
      if (active) setData(result);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "This climate release is unavailable.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [params.slug]);

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <nav aria-label="Climate intelligence navigation">
          <Link className="secondary-action" href="/climate-intelligence">Climate intelligence</Link>
          <Link className="secondary-action" href="/research">Research</Link>
        </nav>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">PUBLISHED CLIMATE EVIDENCE</p>
        {loading ? <p className="workspace-muted" role="status">Loading release…</p> : error ? (
          <section className="staff-card"><h1>Release unavailable</h1><p className="workspace-error" role="alert">{error}</p></section>
        ) : data ? (
          <>
            <h1 className="workspace-title">{data.release.title}</h1>
            <p className="workspace-muted">{data.release.summary}</p>
            <section className="staff-card">
              <h2>Source and method</h2>
              <dl>
                <dt>Provider and product</dt><dd>{data.release.provider_id} · {data.release.provider_product}</dd>
                <dt>Data class</dt><dd>{data.release.data_class}</dd>
                <dt>Indicator</dt><dd>{data.release.indicator} ({data.release.unit})</dd>
                <dt>Geography and resolution</dt><dd>{data.release.geography_label} · {data.release.geography_resolution}</dd>
                <dt>Period</dt><dd>{new Date(data.release.period_start).toLocaleDateString()} – {new Date(data.release.period_end).toLocaleDateString()}</dd>
                <dt>Baseline</dt><dd>{data.release.baseline || "Not specified"}</dd>
                <dt>Aggregation method</dt><dd>{data.release.aggregation_method}</dd>
                <dt>Coverage</dt><dd>{data.release.coverage_pct === null ? "Not reported" : `${data.release.coverage_pct}%`}</dd>
                <dt>Missingness</dt><dd>{data.release.missingness_pct === null ? "Not reported" : `${data.release.missingness_pct}%`}</dd>
                <dt>Uncertainty</dt><dd>{data.release.uncertainty_summary || "Not reported"}</dd>
                <dt>Limitations</dt><dd>{data.release.limitations}</dd>
                <dt>Licence</dt><dd>{data.release.license_name}</dd>
                <dt>Attribution</dt><dd>{data.release.attribution}</dd>
              </dl>
              {data.release.terms_url && <p><a href={data.release.terms_url} target="_blank" rel="noreferrer">Provider terms</a></p>}
              {data.release.citation_url && <p><a href={data.release.citation_url} target="_blank" rel="noreferrer">Source citation</a></p>}
            </section>
            <section className="staff-card">
              <h2>Time series</h2>
              <p className="workspace-muted">Values are presented as released by the organisation. Missing periods are not filled with zero.</p>
              <div className="table-scroll">
                <table>
                  <caption>{data.release.indicator} ({data.release.unit})</caption>
                  <thead><tr><th scope="col">Date</th><th scope="col">Value</th></tr></thead>
                  <tbody>
                    {data.series.map((point) => (
                      <tr key={point.observed_at}><td>{new Date(point.observed_at).toLocaleDateString()}</td><td>{point.value}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            {data.regions.length > 0 && (
              <section className="staff-card">
                <h2>Regional summary</h2>
                <div className="table-scroll">
                  <table>
                    <thead><tr><th scope="col">Region</th><th scope="col">Value</th><th scope="col">Coverage</th></tr></thead>
                    <tbody>{data.regions.map((region) => (
                      <tr key={region.region}><td>{region.region}</td><td>{region.value}</td><td>{region.coverage_pct === null ? "Not reported" : `${region.coverage_pct}%`}</td></tr>
                    ))}</tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        ) : null}
        <p><Link href="/climate-intelligence">← Back to climate intelligence</Link></p>
      </section>
    </main>
  );
}
