import Link from "next/link";

export default function ClimateMethodologyPage() {
  return (
    <main className="climate-public climate-public-method">
      <header className="climate-public-nav">
        <Link className="climate-public-brand" href="/"><span>N</span> NEXTGEN <i>FOR EARTH</i></Link>
        <nav aria-label="Methodology navigation"><Link href="/climate-intelligence">Climate intelligence</Link><Link href="/research">Research</Link></nav>
      </header>
      <section className="climate-method-hero">
        <p className="climate-public-kicker">TRANSPARENCY / REPRODUCIBILITY / GOVERNANCE</p>
        <h1>Trust the method.<br /><em>Interrogate the evidence.</em></h1>
        <p>Climate data can inform decisions only when its origin, classification, spatial and temporal coverage, transformations and limitations are visible. This is the publication standard for NextGen For Earth climate intelligence.</p>
      </section>
      <section className="climate-method-grid">
        <article><p className="climate-public-kicker">01 / RELEASE STANDARD</p><h2>Curated, versioned evidence.</h2><p>A public climate release is a versioned evidence product. It identifies its provider, product, data class, time period, geography, aggregation method, coverage, missingness, uncertainty, limitations, licence and attribution.</p><p>Quality verification does not automatically authorise public release. The licence reviewer must differ from the release author, ingestion operator and observation quality reviewer. The release approver must differ from those actors, and publication must be performed by another authorised person. Each decision is recorded.</p></article>
        <article><p className="climate-public-kicker">02 / DATA CLASSES</p><h2>Know what you are reading.</h2><ul><li><strong>Station observations:</strong> measurements collected at ground stations.</li><li><strong>Satellite estimates:</strong> remotely sensed or satellite-derived estimates.</li><li><strong>Reanalysis:</strong> retrospective model-data assimilation products.</li><li><strong>Forecasts:</strong> time-limited predictions for future conditions.</li><li><strong>Climate projections:</strong> scenario-based future climate simulations.</li><li><strong>Synthetic demonstration datasets:</strong> deterministic fixtures used to demonstrate the staging product; they are not observations, forecasts, reanalysis or scientific findings.</li></ul></article>
        <article><p className="climate-public-kicker">03 / MISSING DATA</p><h2>Missing is not zero.</h2><p>Missing observations are not silently converted to zero. Coverage and missingness describe data availability; they are not uncertainty estimates. If a defensible denominator is unavailable, these metrics remain unreported.</p></article>
        <article><p className="climate-public-kicker">04 / INTERPRETATION</p><h2>Context before conclusion.</h2><ul><li>Delayed historical data are not live conditions.</li><li>Different data classes are not interchangeable.</li><li>Climate-health associations are contextual and do not establish causation or individual health risk.</li><li>Projections are scenario-dependent, not predictions of certainty.</li></ul></article>
        <article><p className="climate-public-kicker">05 / COMMUNITY KNOWLEDGE</p><h2>Governed with communities.</h2><p>Community and Indigenous knowledge requires appropriate permission, governance, attribution and benefit-sharing. Restricted knowledge and sensitive locations must remain protected.</p></article>
        <article><p className="climate-public-kicker">06 / PUBLICATION CONTROL</p><h2>Public by explicit review.</h2><p>Only published release versions appear on the public website. Drafts, review notes, raw participant information, internal provider runs and precise sensitive coordinates remain private. Superseded and retracted versions are excluded from public catalogue results.</p></article>
        <article><p className="climate-public-kicker">07 / STAGING DEMONSTRATIONS</p><h2>Illustration is not evidence.</h2><p>The staging catalogue includes deterministic synthetic rainfall and temperature series to demonstrate the public catalogue, release metadata and visualisations. These fixtures are not provider observations, forecasts, climate projections or scientific findings. They must not be cited or used for decisions.</p><p>Provider-derived releases are identified by their source, product, data class, period, geography, licence and citation.</p></article>
      </section>
      <footer className="climate-public-footer"><Link className="climate-public-brand" href="/"><span>N</span> NEXTGEN <i>FOR EARTH</i></Link><Link href="/climate-intelligence">← Back to climate intelligence</Link></footer>
    </main>
  );
}
