"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import Image from "next/image";
import { apiGet, restoreSession } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

type PublicContent = { id: string; content_type: string; title: string; summary: string | null; body: string | null; slug: string; source_url?: string | null; metadata_json?: { display_value?: string; image_url?: string; gallery?: { alt: string; image_url: string }[] } };
type PublicPerson = { id: string; full_name: string; positions: string[]; biography: string | null; profile_image_url?: string | null };
type PublicPartner = { id: string; name: string; partner_type: string; description: string | null; website_url: string | null; country_code: string; region: string | null };
type PublicProgramme = { id: string; title: string; slug: string; summary: string | null; status: string; start_date: string | null; end_date: string | null };
type PublicCourse = { id: string; title: string; slug: string; description: string; category: string | null; delivery_mode: string; status: string; programme_id: string | null };

const partnerLogos: Record<string, string> = {
  "University of Nairobi": "/media/nextgen-source/partner-university-of-nairobi.png",
  "Medical College of Wisconsin": "/media/nextgen-source/partner-medical-college-wisconsin.png",
  "Men In Health": "/media/nextgen-source/men-in-health-7b0b71fb0d.png",
  "Eternal Flame Worldwide": "/media/nextgen-source/eternal-flame-worldwide-bf4a67139d.png",
  "Kilifi County Health Department": "/media/nextgen-source/kilifi-county-health-department-acec4dce86.png",
  "Masinde Muliro University (MMUST)": "/media/nextgen-source/partner-mmust.png",
  "CHANCE Network": "/media/nextgen-source/partner-chance-network.png",
};


function AnimatedMetric({ value }: { value: string }) {
  const nodeRef = useRef<HTMLSpanElement>(null);
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    const node = nodeRef.current;
    if (!node) return;
    const match = value.match(/^(\\D*?)([\\d,]+)(\\D*)$/);
    if (!match) { setDisplay(value); return; }
    const target = Number(match[2].replaceAll(",", ""));
    if (!Number.isFinite(target) || target <= 0 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplay(value); return;
    }
    const prefix = match[1], suffix = match[3];
    let frame = 0;
    let start = 0;
    const animate = (now: number) => {
      if (!start) start = now;
      const progress = Math.min((now - start) / 1450, 1);
      const eased = 1 - Math.pow(1 - progress, 4);
      const current = Math.round(target * eased);
      setDisplay(prefix + current.toLocaleString("en-US") + suffix);
      if (progress < 1) frame = window.requestAnimationFrame(animate);
    };
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        observer.disconnect();
        frame = window.requestAnimationFrame(animate);
      }
    }, { threshold: 0.35 });
    observer.observe(node);
    return () => { observer.disconnect(); window.cancelAnimationFrame(frame); };
  }, [value]);
  return <span ref={nodeRef} className="animated-metric" aria-label={value}>{display}</span>;
}

function LetterHeading({ text, className = "" }: { text: string; className?: string }) {
  const headingRef = useRef<HTMLSpanElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const node = headingRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setVisible(true); observer.disconnect(); }
    }, { threshold: 0.25 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return <span ref={headingRef} className={"letter-heading " + (visible ? "is-visible " : "") + className} aria-label={text}>{Array.from(text).map((letter, index) => <span aria-hidden="true" className="letter-heading-char" key={letter + "-" + index} style={{ animationDelay: Math.min(index * 24, 900) + "ms" }}>{letter === " " ? "\u00a0" : letter}</span>)}</span>;
}

function ContentCarousel({ children, label, singleRow = false }: { children: ReactNode; label: string; singleRow?: boolean }) {
  const track = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const move = (direction: -1 | 1) => {
    const node = track.current;
    if (!node) return;
    const distance = Math.max(280, node.clientWidth * 0.88);
    if (direction < 0 && node.scrollLeft <= 4) node.scrollTo({ left: node.scrollWidth, behavior: "smooth" });
    else if (direction > 0 && node.scrollLeft + node.clientWidth >= node.scrollWidth - 8) node.scrollTo({ left: 0, behavior: "smooth" });
    else node.scrollBy({ left: direction * distance, behavior: "smooth" });
  };
  useEffect(() => {
    if (paused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => move(1), 5200);
    return () => window.clearInterval(timer);
  }, [paused]);
  return <div className="carousel-shell" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocusCapture={() => setPaused(true)} onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setPaused(false); }}><div className="carousel-controls"><span>{label}</span><div><button type="button" aria-label={"Previous " + label} onClick={() => move(-1)}>←</button><button type="button" aria-label={"Next " + label} onClick={() => move(1)}>→</button></div></div><div className={"content-carousel" + (singleRow ? " content-carousel-single" : "")} ref={track} tabIndex={0} aria-label={label} aria-live="off">{children}</div></div>;
}

const portals = [
  {
    title: "Research & climate",
    description: "Research studies, governed datasets and climate intelligence.",
    tag: "Researcher portal",
    symbol: "⌁",
  },
  {
    title: "Youth & volunteers",
    description: "Learning programmes, mentorship and community participation.",
    tag: "Youth portal",
    symbol: "↗",
  },
  {
    title: "Programme operations",
    description: "Activities, delivery milestones, indicators and quality review.",
    tag: "Administrator portal",
    symbol: "▦",
  },
  {
    title: "Institutional partnerships",
    description: "Collaborative programmes, evidence and organisational reporting.",
    tag: "Partner portal",
    symbol: "◎",
  },
];

export default function HomePage() {
  const [catalogue, setCatalogue] = useState<PublicContent[]>([]);
  const [publicPeople, setPublicPeople] = useState<PublicPerson[]>([]);
  const [publicPartners, setPublicPartners] = useState<PublicPartner[]>([]);
  const [publicProgrammes, setPublicProgrammes] = useState<PublicProgramme[]>([]);
  const [publicCourses, setPublicCourses] = useState<PublicCourse[]>([]);
  const [signedIn, setSignedIn] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    restoreSession()
      .then((session) => { if (active) setSignedIn(Boolean(session)); })
      .catch(() => { if (active) setSignedIn(false); });
    // Do not disguise API failures as a genuinely empty catalogue. Render a
    // visible diagnostic so deployment/configuration faults can be distinguished
    // from content that has not yet been published.
    Promise.all([
      apiGet<PublicContent[]>(`/public/organizations/${ORGANIZATION_SLUG}/content`),
      apiGet<PublicPerson[]>(`/public/organizations/${ORGANIZATION_SLUG}/people`),
      apiGet<PublicPartner[]>(`/public/organizations/${ORGANIZATION_SLUG}/partners`),
      apiGet<PublicProgramme[]>(`/public/organizations/${ORGANIZATION_SLUG}/programmes`),
      apiGet<PublicCourse[]>(`/public/organizations/${ORGANIZATION_SLUG}/courses`),
    ]).then(([items, people, partners, programmes, courses]) => {
      if (!active) return;
      setCatalogue(items);
      setPublicPeople(people);
      setPublicPartners(partners);
      setPublicProgrammes(programmes);
      setPublicCourses(courses);
      setFeedError(null);
    }).catch((error: unknown) => {
      if (!active) return;
      setFeedError(error instanceof Error ? error.message : "Unable to load public organisation data.");
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const sections = Array.from(
      document.querySelectorAll<HTMLElement>(".section-wrap, .impact-ribbon, .access-section"),
    );
    sections.forEach((section) => section.classList.add("reveal-on-scroll"));
    if (!("IntersectionObserver" in window)) {
      sections.forEach((section) => section.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      }),
      { threshold: 0.12, rootMargin: "0px 0px -48px 0px" },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  return (
    <main>
      {feedError && <p className="muted" role="alert">Organisation data could not be loaded: {feedError}. Please retry shortly.</p>}
      <header className="topbar">
        <Link className="brand" href="/" aria-label="NextGen for Earth home">
          <span className="brand-mark">N</span>
          <span>nextgen<span className="brand-light">for</span>earth</span>
        </Link>
        <nav aria-label="Main navigation">
          <a href="#platform">Platform</a>
          <a href="#programmes">Programmes</a>
          <a href="#research">Research</a>
          <Link href="/climate-intelligence">Climate intelligence</Link>
          <a href="#activities">Activities</a>
          <a href="/volunteer/apply">Volunteer</a>
          <a href="/employment/apply">Careers</a>
          <a href="/staff/login">Staff sign in</a>
        </nav>
        <a className="nav-cta" href="#access">Access platform <span aria-hidden="true">↗</span></a>
      </header>

      <section className="hero" id="platform">
        <div className="hero-copy">
          <p className="eyebrow"><span /> RESEARCH · LEARNING · ENVIRONMENTAL ACTION</p>
          <h1><LetterHeading text="Evidence for a" /><br /><em><LetterHeading text="better" /></em> <LetterHeading text="planet." /></h1>
          <p className="hero-intro">
            One connected workspace for the people researching, restoring and
            building a more sustainable future.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href="#access">Enter the platform <span>→</span></a>
            <a className="text-link" href="#portals">Explore the portals <span>↓</span></a>
          </div>
          <div className="hero-note"><span className="pulse" /> A shared platform for measurable impact</div>
        </div>
        <div className="hero-art" aria-label="NextGen for Earth youth climate leaders in the field" role="img">
          <Image className="hero-photo" src="/media/nextgen-source/hero-landscape.jpg" alt="NextGen for Earth youth climate leaders" fill priority quality={95} sizes="(max-width: 900px) 100vw, 50vw" />
          <div className="sun" />
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="hill hill-back" />
          <div className="hill hill-front" />
          <div className="art-caption"><span>FIELD NOTES / 01</span><span>Climate science to action · Kenya</span></div>
        </div>
      </section>

      <section className="impact-ribbon" aria-label="Organisation-reported impact figures">
        <div className="impact-ribbon-intro"><span>THE WORK SO FAR</span><strong>Progress, grounded in people.</strong></div>
        {catalogue.filter((item) => item.content_type === "impact_metric").map((item) => (
          <div className="impact-ribbon-stat" key={item.id}><strong><AnimatedMetric value={item.metadata_json?.display_value || "—"} /></strong><span>{item.title}</span></div>
        ))}
      </section>

      <section className="proof-ticker" aria-label="Training, reach and geographic impact">
        <div className="proof-ticker-track">
          <div className="proof-ticker-group">
            <span>Research Methods Training</span><i>✳</i><span>Systematic Reviews</span><i>✳</i><span>Grant Writing</span><i>✳</i><span>Climate Stewardship</span><i>✳</i><strong>4,000+ Children Reached</strong><i>✳</i><strong>40,000+ Trees Planted</strong><i>✳</i><span>Kenya · Ethiopia · Zimbabwe</span>
          </div>
          <div className="proof-ticker-group" aria-hidden="true">
            <span>Research Methods Training</span><i>✳</i><span>Systematic Reviews</span><i>✳</i><span>Grant Writing</span><i>✳</i><span>Climate Stewardship</span><i>✳</i><strong>4,000+ Children Reached</strong><i>✳</i><strong>40,000+ Trees Planted</strong><i>✳</i><span>Kenya · Ethiopia · Zimbabwe</span>
          </div>
        </div>
      </section>

      <section className="portals section-wrap" id="portals">
        <div className="section-heading">
          <div><p className="eyebrow">CONNECTED BY PURPOSE</p><h2><LetterHeading text="One mission." /><br /><em><LetterHeading text="Four ways in." /></em></h2></div>
          <p>Purpose-built spaces bring each community together while keeping
            organisational data and permissions protected.</p>
        </div>
        <div className="portal-grid">
          {portals.map((portal, index) => (
            <article className="portal-card" key={portal.title}>
              <div className="portal-card-top"><span className="portal-number">0{index + 1}</span><span className="portal-symbol">{portal.symbol}</span></div>
              <p className="portal-tag">{portal.tag}</p>
              <h3>{portal.title}</h3>
              <p className="portal-description">{portal.description}</p>
              <a href={index === 1 ? "/learners" : "/staff/login"} aria-label={index === 1 ? "Open learner and volunteer portal" : `Open ${portal.title} sign in`}>Open portal <span>↗</span></a>
            </article>
          ))}
        </div>
      </section>

      <section className="portals section-wrap editorial-about" id="about">
        <div className="section-heading"><div><p className="eyebrow">THE NEXTGEN STORY</p><h2><LetterHeading text="Science, community" /> <em><LetterHeading text="& action." /></em></h2></div><p>Mission, vision and approach captured from the organisation’s public website and connected to the platform CMS.</p></div>
        <ContentCarousel label="Organisation story" singleRow><div className="carousel-track">
          {catalogue.filter((item) => ["website-we-are-on-a-mission", "website-our-mission", "website-we-have-a-vision", "website-our-approach", "website-our-logic"].includes(item.slug)).map((item) => <article className="story-card" key={item.id}><p className="portal-tag">{item.title}</p><p>{item.summary || item.body}</p></article>)}
        </div></ContentCarousel>
      </section>
      <section className="portals section-wrap" id="programmes">
        <div className="section-heading"><div><p className="eyebrow">OUR WORK</p><h2><LetterHeading text="Programmes &" /> <em><LetterHeading text="initiatives." /></em></h2></div><p>Current organisational programmes and training opportunities.</p></div>
        <ContentCarousel label="Programmes and courses"><div className="carousel-track">
          {publicProgrammes.map((programme) => (
            <article className="portal-card programme-card" key={programme.id}>
              <div className="catalogue-image-wrap"><Image className="catalogue-image" src={programme.slug === "research-capacity-building" ? "/media/nextgen-source/programme-research-capacity.svg" : programme.slug === "healthcare-worker-training" ? "/media/nextgen-source/programme-healthcare-workers.svg" : programme.slug === "youth-climate-stewardship" ? "/media/nextgen-source/programme-youth-stewardship.svg" : "/media/nextgen-source/programme-indigenous-knowledge.svg"} alt="" width={720} height={440} quality={92} /></div>
              <p className="portal-tag">Programme · {programme.status}</p><h3><Link href={`/programmes/${programme.slug}`}>{programme.title}</Link></h3><p className="portal-description">{programme.summary}</p>{(programme.start_date || programme.end_date) && <p className="portal-description">{programme.start_date ?? "Date to be announced"} – {programme.end_date ?? "Ongoing"}</p>}
            </article>
          ))}
          {publicCourses.map((course) => {
            const programme = publicProgrammes.find((item) => item.id === course.programme_id);
            return (
              <article className="portal-card" key={`course-${course.id}`}>
                <p className="portal-tag">Training course · {course.delivery_mode.replaceAll("_", " ")}</p>
                <h3>{course.title}</h3>
                <p className="portal-description">{course.description}</p>
                {programme && <p className="portal-description">Programme: {programme.title}</p>}
                {course.category && <p className="portal-description">Category: {course.category}</p>}
                <Link href="/learners">Apply or access learning <span>↗</span></Link>
              </article>
            );
          })}

        </div></ContentCarousel>
        {publicProgrammes.length === 0 && publicCourses.length === 0 && catalogue.length === 0 && <p className="muted">The public catalogue is being prepared. Approved entries will appear here.</p>}
      </section>
      <section className="portals section-wrap" id="activities">
        <div className="section-heading"><div><p className="eyebrow">ONGOING DELIVERY</p><h2><LetterHeading text="Work in" /> <em><LetterHeading text="motion." /></em></h2></div><p>Current activities connected to programme delivery, learning and community engagement.</p></div>
        <ContentCarousel label="Activities and training"><div className="carousel-track">
          {catalogue.filter((item) => item.content_type === "initiative").map((item) => (
            <article className="portal-card activity-card" key={item.id}>{item.metadata_json?.image_url && <div className="catalogue-image-wrap"><Image className="catalogue-image" src={item.metadata_json.image_url} alt={item.title} width={720} height={440} quality={90} /></div>}<p className="portal-tag">Ongoing activity</p><h3>{item.title}</h3><p className="portal-description">{item.summary || item.body}</p></article>
          ))}
          {catalogue.filter((item) => item.content_type === "training_track").map((item) => (
            <article className="portal-card activity-card" key={item.id}>{item.metadata_json?.image_url && <div className="catalogue-image-wrap"><Image className="catalogue-image" src={item.metadata_json.image_url} alt={item.title} width={720} height={440} quality={90} /></div>}<p className="portal-tag">Training track</p><h3>{item.title}</h3><p className="portal-description">{item.summary || item.body}</p></article>
          ))}
        </div></ContentCarousel>
        {catalogue.filter((item) => item.content_type === "initiative" || item.content_type === "training_track").length === 0 && <p className="muted">Activity and training information will appear here as it is published.</p>}
      </section>
      <section className="portals section-wrap" id="research">
        <div className="section-heading"><div><p className="eyebrow">EVIDENCE & KNOWLEDGE</p><h2><LetterHeading text="Research &" /> <em><LetterHeading text="publications." /></em></h2></div><p>Research outputs and knowledge products attributed to the organisation&apos;s published catalogue.</p></div>
        <ContentCarousel label="Research and publications"><div className="carousel-track">
          {catalogue.filter((item) => item.content_type === "publication" || item.content_type === "research_area").map((item) => (
            <article className="portal-card" key={item.id}><p className="portal-tag">{item.content_type === "publication" ? "Publication" : "Research area"}</p><h3>{item.title}</h3><p className="portal-description">{item.summary || item.body}</p>{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">View publication <span>↗</span></a>}</article>
          ))}
        </div></ContentCarousel>
        {catalogue.filter((item) => item.content_type === "publication" || item.content_type === "research_area").length === 0 && <p className="muted">Published research records will appear here.</p>}
        <p className="section-more"><Link href="/research">Explore the research catalogue <span aria-hidden="true">→</span></Link></p>
      </section>
      <section className="portals section-wrap" id="impact">
        <div className="section-heading"><div><p className="eyebrow">ORGANISATIONAL IMPACT</p><h2><LetterHeading text="Evidence of" /> <em><LetterHeading text="progress." /></em></h2></div><p>Impact figures shown here are sourced from the organisation&apos;s published website and should be updated through reviewed reporting.</p></div>
        <ContentCarousel label="Impact indicators"><div className="carousel-track">
          {catalogue.filter((item) => item.content_type === "impact_metric").map((item) => (
            <article className="portal-card" key={item.id}><p className="portal-tag">Published impact figure</p><h3>{item.metadata_json?.display_value || "—"}</h3><p className="portal-description">{item.title}</p></article>
          ))}
        </div></ContentCarousel>
        {catalogue.filter((item) => item.content_type === "impact_metric").length === 0 && <p className="muted">Reviewed impact figures will appear here.</p>}
      </section>
      <section className="portals section-wrap" id="people">
        <div className="section-heading"><div><p className="eyebrow">OUR COMMUNITY</p><h2><LetterHeading text="People &" /> <em><LetterHeading text="partners." /></em></h2></div><p>Publicly approved leadership, staff, volunteers, mentors and institutional partners.</p></div>
        <ContentCarousel label="People and institutions"><div className="carousel-track">
          {publicPeople.map((person) => <article className="portal-card people-card" key={person.id}>{person.profile_image_url ? <img className="people-avatar" src={person.profile_image_url} alt={person.full_name} width={112} height={112} loading="lazy" /> : <div className="people-avatar people-avatar-fallback" aria-hidden="true">{person.full_name.slice(0, 1)}</div>}<p className="portal-tag">People</p><h3>{person.full_name}</h3><p className="portal-description">{person.positions.join(" · ")}</p>{person.biography && <p className="portal-description">{person.biography}</p>}</article>)}
          {publicPartners.map((partner) => <article className="portal-card partner-card" key={partner.id}>{partnerLogos[partner.name] ? <div className="partner-logo-frame"><img className="partner-logo" src={partnerLogos[partner.name]} alt={`${partner.name} logo`} loading="lazy" /></div> : <div className="partner-logo-frame partner-logo-fallback" aria-hidden="true">{partner.name.slice(0, 2).toUpperCase()}</div>}<p className="portal-tag">Listed organisation · source website</p><h3>{partner.name}</h3><p className="portal-description">{partner.partner_type.replaceAll("_", " ")}{partner.region ? ` · ${partner.region}` : ""}{partner.country_code ? ` · ${partner.country_code}` : ""}</p>{partner.description && <p className="portal-description">{partner.description}</p>}{partner.website_url && <a href={partner.website_url} target="_blank" rel="noreferrer">Partner website ↗</a>}</article>)}
        </div></ContentCarousel>
        {publicPeople.length === 0 && publicPartners.length === 0 && <p className="muted">Public people and website-listed organisations will appear here.</p>}
        <p className="section-more"><Link href="/community">Meet our people and institutional collaborators <span aria-hidden="true">→</span></Link></p>
      </section>

      <section className="portals section-wrap field-gallery" id="gallery">
        <div className="section-heading"><div><p className="eyebrow">IN THE FIELD</p><h2><LetterHeading text="People, places" /> <em><LetterHeading text="& progress." /></em></h2></div><p>Photographs and profiles are published with organisational authorisation. Images and records remain editable through the administration workspace.</p></div>
        <ContentCarousel label="Field photographs"><div className="carousel-track">
          {(catalogue.find((item) => item.slug === "website-gallery")?.metadata_json?.gallery ?? []).map((item) => <figure className="gallery-item" key={item.image_url}><img src={item.image_url} alt={item.alt} width={720} height={480} loading="lazy" /><figcaption>{item.alt}</figcaption></figure>)}
        </div></ContentCarousel>
      </section>
      <section className="theory-section section-wrap" id="our-logic">
        <div className="section-heading">
          <div><p className="eyebrow">OUR LOGIC</p><h2><LetterHeading text="Theory of" /> <em><LetterHeading text="Change." /></em></h2></div>
          <p>How we move from training and science to lasting climate impact across Africa.</p>
        </div>
        <div className="theory-flow">
          <article className="theory-step"><span className="theory-number">1</span><p className="portal-tag">The foundation</p><h3>Input</h3><ul><li>Expert mentors</li><li>Published science</li><li>Community partnerships</li><li>Funded programmes</li></ul></article>
          <span className="theory-arrow" aria-hidden="true">→</span>
          <article className="theory-step"><span className="theory-number">2</span><p className="portal-tag">What we do</p><h3>Activities</h3><ul><li>Weekly workshops</li><li>Peer mentorship</li><li>Field research</li><li>Tree planting drives</li></ul></article>
          <span className="theory-arrow" aria-hidden="true">→</span>
          <article className="theory-step"><span className="theory-number">3</span><p className="portal-tag">What we deliver</p><h3>Outputs</h3><ul><li><AnimatedMetric value="100+" /> youth trained</li><li><AnimatedMetric value="35" /> researchers mentored</li><li><AnimatedMetric value="4,000+" /> children reached</li><li><AnimatedMetric value="12" /> publications</li></ul></article>
          <span className="theory-arrow" aria-hidden="true">→</span>
          <article className="theory-step"><span className="theory-number">4</span><p className="portal-tag">What changes</p><h3>Outcomes</h3><ul><li>Youth lead research</li><li>Schools adopt stewardship</li><li>Communities more resilient</li><li>Policies informed</li></ul></article>
          <span className="theory-arrow" aria-hidden="true">→</span>
          <article className="theory-step theory-impact"><span className="theory-number">5</span><p className="portal-tag">The long-term change</p><h3>Impact</h3><ul><li>Climate-literate generation</li><li>Evidence-based policy</li><li>Healthier communities</li><li>Sustainable Africa</li></ul></article>
        </div>
      </section>
      <section className="access-section" id="access">
        <div className="access-copy">
          <p className="eyebrow">SECURE WORKSPACE</p>
          <h2>{signedIn ? "Welcome to the platform." : "Your work starts here."}</h2>
          <p>Staff and institutional partners sign in after receiving an organisation invitation. Learners create accounts through the separate learning portal.</p>
          <div className="access-points"><span>✓ Organisation-scoped access</span><span>✓ Role-based permissions</span><span>✓ Research data governance</span></div>
        </div>
        <div className="login-panel">
          <div className="login-heading"><span className="login-icon">↗</span><div><p className="eyebrow">CHOOSE YOUR ACCESS</p><h3>Continue to your portal</h3></div></div>
          <p className="session-note">Organisation members and learners have separate entry journeys. Registering an identity does not automatically grant staff or partner permissions.</p>
          <Link className="button button-primary full" href="/staff/login">Staff & institutional partner sign in <span>→</span></Link>
          <Link className="button button-primary full" href="/workspace/accept-invitation">Accept an organisation invitation <span>→</span></Link>
          <Link className="text-link" href="/staff/register">New employee or partner? Register an identity</Link>
          <Link className="text-link" href="/learners">Learner portal: register, apply or continue learning</Link>
        </div>
      </section>

      <footer><Link className="brand" href="/"><span className="brand-mark">N</span><span>nextgen<span className="brand-light">for</span>earth</span></Link><span>Research with purpose. Action with evidence.</span><span>© {new Date().getFullYear()} NextGen for Earth</span></footer>
    </main>
  );
}
