import Link from "next/link";

export default function ClimateMethodologyPage() {
  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <nav aria-label="Methodology navigation">
          <Link className="secondary-action" href="/climate-intelligence">Climate intelligence</Link>
        </nav>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">TRANSPARENCY & REPRODUCIBILITY</p>
        <h1 className="workspace-title">Methodology and sources</h1>
        <section className="staff-card">
          <h2>Publication standard</h2>
          <p className="workspace-muted">
            A climate release is a curated, versioned evidence product. It must identify
            its provider, product, data class, period, geography, aggregation method,
            coverage, missingness, uncertainty, limitations, licence and attribution.
          </p>
          <p className="workspace-muted">
            A quality-verified observation is not automatically approved for public
            release. Public values are shown only after independent review and explicit
            publication by an authorised organisation member.
          </p>
        </section>
        <section className="staff-card">
          <h2>Data classes</h2>
          <ul>
            <li><strong>Station observations:</strong> measurements collected at ground stations.</li>
            <li><strong>Satellite estimates:</strong> remotely sensed or satellite-derived estimates.</li>
            <li><strong>Reanalysis:</strong> retrospective model-data assimilation products.</li>
            <li><strong>Forecasts:</strong> time-limited predictions for future conditions.</li>
            <li><strong>Climate projections:</strong> scenario-based future climate simulations.</li>
          </ul>
        </section>
        <section className="staff-card">
          <h2>Interpretation limits</h2>
          <ul>
            <li>Do not interpret a delayed historical dataset as live conditions.</li>
            <li>Do not treat missing data as zero or silently combine different data classes.</li>
            <li>Coverage and missingness are data availability measures, not uncertainty estimates.</li>
            <li>Climate-health associations are contextual evidence and do not establish causation or individual health risk.</li>
            <li>Community and Indigenous knowledge requires appropriate permission, governance, attribution and protection of restricted knowledge.</li>
          </ul>
        </section>
      </section>
    </main>
  );
}
