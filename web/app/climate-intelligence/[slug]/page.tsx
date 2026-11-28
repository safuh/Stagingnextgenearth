"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { apiGetRevalidated } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

type Release = {
  id: string; slug: string; version: number; title: string; summary: string;
  indicator: string; unit: string; provider_id: string; provider_product: string;
  provider_version: string | null; data_class: string; geography_label: string;
  geography_resolution: string; period_start: string; period_end: string;
  baseline: string | null; aggregation_method: string; coverage_pct: number | null;
  missingness_pct: number | null; uncertainty_summary: string | null; limitations: string;
  license_name: string; attribution: string; terms_url: string | null;
  citation_url: string | null; published_at: string | null;
};
type Series = { release: Release; series: Array<{ observed_at: string; value: number }>; regions: Array<{ region: string; value: number; coverage_pct: number | null }> };

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(value));
}

function ClimateSeriesChart({ points, unit }: { points: Series["series"]; unit: string }) {
  const geometry = useMemo(() => {
    if (points.length < 2) return null;
    const values = points.map((point) => point.value);
    const min = Math.min(...values); const max = Math.max(...values);
    const span = max - min || Math.max(Math.abs(max) * .1, 1);
    const low = min - span * .12; const high = max + span * .12;
    const coordinates = points.map((point, index) => ({
      x: 36 + (index / (points.length - 1)) * 728,
      y: 198 - ((point.value - low) / (high - low)) * 166,
    }));
    return {
      path: coordinates.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" "),
      dots: coordinates,
      min: Math.min(...values), max: Math.max(...values),
    };
  }, [points]);

  if (!geometry) return <p className="climate-chart-note">At least two timestamps are required to draw a time-series line. The released values remain available in the table below.</p>;
  return (
    <div>
      <svg className="climate-series-chart" viewBox="0 0 800 230" role="img" aria-label={`Time series of ${unit}, from ${geometry.min} to ${geometry.max} ${unit}`}>
        {[32, 87, 142, 198].map((y) => <line className="grid-line" key={y} x1="25" x2="775" y1={y} y2={y} />)}
        <path className="series-line" d={geometry.path} />
        {geometry.dots.map((point, index) => <circle className="series-dot" key={points[index].observed_at} cx={point.x} cy={point.y} r="4" />)}
      </svg>
      <div className="climate-chart-axis"><span>{formatDate(points[0].observed_at)}</span><span>{points.length} timestamps · {unit}</span><span>{formatDate(points[points.length - 1].observed_at)}</span></div>
    </div>
  );
}

export default function ClimateReleasePage() {
  const params = useParams<{ slug: string }>();
  const [data, setData] = useState<Series | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    apiGetRevalidated<Series>(`/public/organizations/${ORGANIZATION_SLUG}/climate/releases/${encodeURIComponent(params.slug)}/series`)
      .then((result) => { if (active) setData(result); })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "This climate release is unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [params.slug]);

  return (
    <main className="climate-public climate-public-detail">
      <header className="climate-public-nav">
        <Link className="climate-public-brand" href="/"><span>N</span> NEXTGEN <i>FOR EARTH</i></Link>
        <nav aria-label="Public climate navigation">
          <Link href="/climate-intelligence">Climate intelligence</Link>
          <Link href="/research">Research</Link>
          <Link href="/climate-intelligence/methodology">Methodology</Link>
        </nav>
      </header>
      {loading ? <div className="climate-public-state" role="status">Loading published release…</div> : error ? (
        <section className="climate-detail-hero"><p className="climate-public-kicker">PUBLIC EVIDENCE / UNAVAILABLE</p><h1>Release not available.</h1><p>{error}</p><Link href="/climate-intelligence">← Return to climate intelligence</Link></section>
      ) : data ? (
        <>
          <section className="climate-detail-hero">
            <p className="climate-public-kicker">{data.release.provider_id === "demo-synthetic" ? "PUBLISHED STAGING DEMO / SYNTHETIC DATA" : `PUBLISHED CLIMATE EVIDENCE / VERSION ${data.release.version}`}</p>
            <h1>{data.release.title}</h1>
            <p>{data.release.summary}</p>
            <p className="climate-public-proof"><span className="climate-public-proof-dot" /> PUBLISHED {data.release.published_at ? formatDate(data.release.published_at) : "DATE NOT REPORTED"} · {data.release.data_class.replace(/_/g, " ").toUpperCase()}</p>
          </section>
          {data.release.provider_id === "demo-synthetic" && (
            <aside className="climate-public-demo-banner" role="note">
              <div><strong>SYNTHETIC DEMONSTRATION — NOT CLIMATE OBSERVATIONS</strong><p>This series is generated fixture data for staging UX demonstration. It has no provider provenance, observational uncertainty, or scientific validity. The linked research context does not validate or analyse these values.</p></div>
            </aside>
          )}
          <section className="climate-detail-content">
            <div className="climate-detail-main">
              <section className="climate-detail-panel">
                <p className="climate-public-kicker">{data.release.provider_id === "demo-synthetic" ? "ILLUSTRATIVE SIGNAL / 01" : "OBSERVED SIGNAL / 01"}</p>
                <h2>{data.release.indicator} <small>{data.release.unit}</small></h2>
                <ClimateSeriesChart points={data.series} unit={data.release.unit} />
                <div className="climate-detail-table-wrap">
                  <table className="climate-detail-table">
                    <caption>{data.release.provider_id === "demo-synthetic" ? "Synthetic demonstration values · not observations" : "Released observations · no missing-value imputation"}</caption>
                    <thead><tr><th scope="col">Timestamp</th><th scope="col">Value ({data.release.unit})</th></tr></thead>
                    <tbody>{data.series.map((point) => <tr key={point.observed_at}><td>{formatDate(point.observed_at)}</td><td>{point.value.toLocaleString("en-GB", { maximumFractionDigits: 3 })}</td></tr>)}</tbody>
                  </table>
                </div>
              </section>
              {data.regions.length > 0 && <section className="climate-detail-panel"><h2>Regional summary</h2><table className="climate-detail-table"><thead><tr><th>Region</th><th>Value</th><th>Coverage</th></tr></thead><tbody>{data.regions.map((region) => <tr key={region.region}><td>{region.region}</td><td>{region.value}</td><td>{region.coverage_pct === null ? "Not reported" : `${region.coverage_pct}%`}</td></tr>)}</tbody></table></section>}
            </div>
            <aside className="climate-detail-aside">
              <section className="climate-detail-panel">
                <p className="climate-public-kicker">PROVENANCE / 02</p><h2>Evidence record</h2>
                <dl className="climate-detail-facts">
                  <div><dt>Provider</dt><dd>{data.release.provider_id}</dd></div>
                  <div><dt>Product</dt><dd>{data.release.provider_product}{data.release.provider_version ? ` · ${data.release.provider_version}` : ""}</dd></div>
                  <div><dt>Data class</dt><dd>{data.release.data_class.replace(/_/g, " ")}</dd></div>
                  <div><dt>Geography</dt><dd>{data.release.geography_label}</dd></div>
                  <div><dt>Resolution</dt><dd>{data.release.geography_resolution}</dd></div>
                  <div><dt>Period</dt><dd>{formatDate(data.release.period_start)} — {formatDate(data.release.period_end)}</dd></div>
                  <div><dt>Baseline</dt><dd>{data.release.baseline || "Not specified"}</dd></div>
                  <div><dt>Aggregation</dt><dd>{data.release.aggregation_method}</dd></div>
                  <div><dt>Coverage</dt><dd>{data.release.coverage_pct === null ? "Not reported" : `${data.release.coverage_pct}%`}</dd></div>
                  <div><dt>Missingness</dt><dd>{data.release.missingness_pct === null ? "Not reported" : `${data.release.missingness_pct}%`}</dd></div>
                  <div><dt>Licence</dt><dd>{data.release.license_name}</dd></div>
                  <div><dt>Attribution</dt><dd>{data.release.attribution}</dd></div>
                </dl>
                {data.release.citation_url && <p><a href={data.release.citation_url} target="_blank" rel="noreferrer">Open source citation ↗</a></p>}
                {data.release.terms_url && <p><a href={data.release.terms_url} target="_blank" rel="noreferrer">Provider terms ↗</a></p>}
              </section>
              <section className="climate-detail-panel">
                <p className="climate-public-kicker">INTERPRETATION / 03</p><h2>Limits matter.</h2>
                <dl className="climate-detail-facts">
                  <div><dt>Uncertainty</dt><dd>{data.release.uncertainty_summary || "Not reported"}</dd></div>
                  <div><dt>Limitations</dt><dd>{data.release.limitations}</dd></div>
                </dl>
              </section>
            </aside>
          </section>
        </>
      ) : null}
      <footer className="climate-public-footer"><Link className="climate-public-brand" href="/"><span>N</span> NEXTGEN <i>FOR EARTH</i></Link><Link href="/climate-intelligence">← Back to climate intelligence</Link></footer>
    </main>
  );
}
