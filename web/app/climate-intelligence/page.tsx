"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

type Release = {
  id: string; slug: string; version: number; title: string; summary: string;
  indicator: string; unit: string; provider_id: string; provider_product: string;
  data_class: string; geography_label: string; geography_resolution: string;
  period_start: string; period_end: string; baseline: string | null;
  coverage_pct: number | null; missingness_pct: number | null;
  license_name: string; attribution: string; citation_url: string | null;
  published_at: string | null;
};
type Overview = {
  organization: string; release_count: number; indicators: string[];
  latest_published_at: string | null; latest_data_period_end: string | null;
  latest_source_retrieved_at: string | null;
};
type Source = {
  provider_id: string; provider_product: string; data_class: string; license_name: string;
  attribution: string; terms_url: string | null; citation_url: string | null; release_count: number;
};
type ClimateInsight = {
  id: string; slug: string; title: string; summary: string | null; body: string | null;
  region: string | null; indicator: string | null; evidence_note: string | null;
  release_slug: string; publication_title: string; publication_url: string | null;
  published_at: string | null;
};

const dataClassLabels: Record<string, string> = {
  station_observation: "Station observation",
  satellite_estimate: "Satellite estimate",
  reanalysis: "Reanalysis",
  forecast: "Forecast",
  projection: "Climate projection",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(value));
}

function formatDateTime(value: string | null): string {
  if (!value) return "Not yet available";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", timeZone: "UTC", timeZoneName: "short",
  }).format(new Date(value));
}

export default function ClimateIntelligencePage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [releases, setReleases] = useState<Release[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [insights, setInsights] = useState<ClimateInsight[]>([]);
  const [insightError, setInsightError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      apiGet<Overview>(`/public/organizations/${ORGANIZATION_SLUG}/climate/overview`),
      apiGet<Release[]>(`/public/organizations/${ORGANIZATION_SLUG}/climate/releases?limit=100`),
      apiGet<Source[]>(`/public/organizations/${ORGANIZATION_SLUG}/climate/sources`),
    ]).then(([summary, items, sourceItems]) => {
      if (!active) return;
      setOverview(summary); setReleases(items); setSources(sourceItems);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Climate intelligence is temporarily unavailable.");
    }).finally(() => { if (active) setLoading(false); });
    apiGet<ClimateInsight[]>(`/public/organizations/${ORGANIZATION_SLUG}/climate/insights`)
      .then((items) => { if (active) setInsights(items); })
      .catch((cause: unknown) => {
        if (active) setInsightError(cause instanceof Error ? cause.message : "Research-linked insights are temporarily unavailable.");
      });
    return () => { active = false; };
  }, []);

  return (
    <main className="climate-public">
      <header className="climate-public-nav">
        <Link className="climate-public-brand" href="/"><span>N</span> NEXTGEN <i>FOR EARTH</i></Link>
        <nav aria-label="Public climate navigation">
          <Link href="/research">Research</Link>
          <Link href="/climate-intelligence/methodology">Methodology</Link>
          <Link className="climate-public-nav-cta" href="/workspace/research/climate">Research studio <span>↗</span></Link>
        </nav>
      </header>

      <section className="climate-public-hero">
        <div className="climate-public-hero-copy">
          <p className="climate-public-kicker"><span /> CLIMATE SYSTEMS / EAST AFRICA</p>
          <h1>Make the signal<br /> <em>make sense.</em></h1>
          <p className="climate-public-intro">
            Explore climate evidence with its source, method, geography and limits in view.
            We turn trusted provider data into transparent, reviewable knowledge for research and action.
          </p>
          <div className="climate-public-actions">
            <a className="climate-public-primary" href="#evidence">Explore evidence <span>↓</span></a>
            <Link className="climate-public-secondary" href="/climate-intelligence/methodology">How we work ↗</Link>
          </div>
          <div className="climate-public-proof"><span className="climate-public-proof-dot" /> GOVERNED DATA / PUBLIC BY REVIEW</div>
        </div>
        <div className="climate-signal-art" aria-label="Abstract climate data signal visualisation" role="img">
          <div className="climate-signal-grid" />
          <div className="climate-signal-orbit orbit-a" />
          <div className="climate-signal-orbit orbit-b" />
          <div className="climate-signal-core"><span>CLIMATE</span><strong>↗</strong><small>DATA / CONTEXT / ACTION</small></div>
          <div className="climate-signal-tag signal-tag-a">01 / OBSERVE</div>
          <div className="climate-signal-tag signal-tag-b">02 / VERIFY</div>
          <div className="climate-signal-tag signal-tag-c">03 / INTERPRET</div>
          <div className="climate-signal-caption">NEXTGEN FOR EARTH · CLIMATE INTELLIGENCE</div>
        </div>
      </section>

      <section className="climate-public-metrics" aria-label="Climate catalogue summary">
        <div><span>PUBLIC RELEASES</span><strong>{loading ? "—" : overview?.release_count ?? 0}</strong></div>
        <div><span>INDICATORS</span><strong>{loading ? "—" : overview?.indicators.length ?? 0}</strong></div>
        <div><span>DATA SOURCES</span><strong>{loading ? "—" : sources.length}</strong></div>
        <div><span>PUBLICATION STANDARD</span><strong>REVIEWED</strong></div>
      </section>
      <section className="climate-public-freshness" aria-label="Evidence freshness and time coverage">
        <div><span>LAST PUBLISHED</span><strong>{loading ? "—" : formatDateTime(overview?.latest_published_at ?? null)}</strong></div>
        <div><span>SOURCE RETRIEVED</span><strong>{loading ? "—" : formatDateTime(overview?.latest_source_retrieved_at ?? null)}</strong></div>
        <div><span>DATA PERIOD ENDS</span><strong>{loading ? "—" : formatDate(overview?.latest_data_period_end ?? "") || "Not yet available"}</strong></div>
        <p>Publication time, provider retrieval time and the period represented by the data are different timestamps. Historical releases are not live conditions.</p>
      </section>

      <section className="climate-public-content" id="evidence">
        <div className="climate-public-section-head">
          <div><p className="climate-public-kicker">THE EVIDENCE CATALOGUE / 01</p><h2>Signals worth<br /><em>looking closer at.</em></h2></div>
          <p>Every published release carries its own provenance, classification, temporal coverage, method and limitations. No public value is generated from demo fixtures.</p>
        </div>

        {error && <div className="climate-public-state climate-public-error" role="alert">{error}<p>The public catalogue could not be retrieved. Try again later.</p></div>}
        {loading && <div className="climate-public-state" role="status">Loading published climate evidence…</div>}
        {!loading && !error && releases.length === 0 && (
          <div className="climate-public-empty">
            <div className="climate-empty-mark">∅</div>
            <div><p className="climate-public-kicker">NO RELEASES PUBLISHED YET</p><h3>The evidence layer is being prepared.</h3><p>Provider ingestion, quality review and publication approval are separate steps. This catalogue will populate only after a real provider-backed dataset has passed the release process.</p></div>
            <Link href="/climate-intelligence/methodology">Read the publication standard ↗</Link>
          </div>
        )}
        {!loading && releases.length > 0 && (
          <div className="climate-public-release-grid">
            {releases.map((release, index) => (
              <article className="climate-public-release-card" key={release.id}>
                <div className="climate-public-card-top"><span>{String(index + 1).padStart(2, "0")} / EVIDENCE RELEASE</span><span>V{release.version}</span></div>
                <p className="climate-public-data-class">{dataClassLabels[release.data_class] ?? release.data_class}</p>
                <h3>{release.title}</h3>
                <p className="climate-public-card-summary">{release.summary}</p>
                <div className="climate-public-card-data"><strong>{release.indicator}</strong><span>{release.unit}</span></div>
                <div className="climate-public-card-meta"><span>{release.geography_label}</span><span>{formatDate(release.period_start)} — {formatDate(release.period_end)}</span></div>
                <div className="climate-public-card-foot"><span>{release.provider_product}</span><Link href={`/climate-intelligence/${release.slug}`}>Inspect release ↗</Link></div>
              </article>
            ))}
          </div>
        )}

        <section className="climate-public-insights">
          <div className="climate-public-section-head">
            <div><p className="climate-public-kicker">RESEARCH MEETS CLIMATE EVIDENCE / 02</p><h2>Context is a<br /><em>research question.</em></h2></div>
            <p>Editorial interpretation is published only when it is connected to a public climate release and a separately published research output. The links make the evidence trail inspectable.</p>
          </div>
          {insightError ? (
            <div className="climate-public-state climate-public-error" role="status">Research-linked insights are temporarily unavailable. The climate evidence catalogue remains available.</div>
          ) : insights.length === 0 ? (
            <div className="climate-public-insight-empty">
              <span>↗</span>
              <div><strong>No research-linked climate insights published yet.</strong><p>When a climate release and its related research publication are public, an independently reviewed editorial insight can connect them here. Research context is not a claim of causation.</p></div>
            </div>
          ) : (
            <div className="climate-public-insight-grid">
              {insights.map((insight, index) => (
                <article className="climate-public-insight-card" key={insight.id}>
                  <p className="climate-public-kicker">FIELD NOTE / {String(index + 1).padStart(2, "0")}</p>
                  <h3>{insight.title}</h3>
                  {insight.region && <span className="climate-public-insight-region">{insight.region}</span>}
                  <p>{insight.summary || insight.body || "Read the linked evidence and research context."}</p>
                  {insight.evidence_note && <small>{insight.evidence_note}</small>}
                  <div className="climate-public-insight-links">
                    <Link href={`/climate-intelligence/${insight.release_slug}`}>Inspect climate release ↗</Link>
                    {insight.publication_url && <a href={insight.publication_url} target="_blank" rel="noreferrer">Read research: {insight.publication_title} ↗</a>}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <div className="climate-public-source-strip">
          <div><p className="climate-public-kicker">SOURCE REGISTER / 02</p><h3>Know where the numbers come from.</h3></div>
          {sources.length === 0 ? <p>No provider sources have been publicly released yet. Sources will be listed here with their licence and attribution.</p> : (
            <div className="climate-public-source-list">{sources.map((source) => (
              <article key={source.provider_id + source.provider_product}>
                <strong>{source.provider_product}</strong><span>{dataClassLabels[source.data_class] ?? source.data_class} · {source.license_name}</span>
                <small>{source.attribution}</small>
                <div>{source.citation_url && <a href={source.citation_url} target="_blank" rel="noreferrer">Citation ↗</a>}{source.terms_url && <a href={source.terms_url} target="_blank" rel="noreferrer">Terms ↗</a>}</div>
              </article>
            ))}</div>
          )}
        </div>
      </section>

      <section className="climate-public-principles">
        <div><p className="climate-public-kicker">READ THE DATA, NOT JUST THE CHART / 03</p><h2>Context is part<br />of the <em>evidence.</em></h2></div>
        <div className="climate-principle-grid">
          <article><span>01</span><strong>Different data. Different meaning.</strong><p>Station observations, satellite estimates, reanalysis, forecasts and projections are not interchangeable.</p></article>
          <article><span>02</span><strong>Missing is not zero.</strong><p>Coverage and missingness are reported separately from uncertainty. We do not silently fill gaps.</p></article>
          <article><span>03</span><strong>Association is not causation.</strong><p>Climate-health context is descriptive and does not establish causation or individual health risk.</p></article>
        </div>
        <Link href="/climate-intelligence/methodology">Explore methodology and governance ↗</Link>
      </section>

      <footer className="climate-public-footer"><Link className="climate-public-brand" href="/"><span>N</span> NEXTGEN <i>FOR EARTH</i></Link><p>Climate science to action. Evidence with provenance.</p><Link href="/">Return to NextGen For Earth ↗</Link></footer>
    </main>
  );
}
