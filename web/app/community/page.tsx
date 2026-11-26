"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { ORGANIZATION_SLUG } from "@/lib/organization";

type PublicPerson = {
  id: string;
  full_name: string;
  positions: string[];
  biography: string | null;
  profile_image_url?: string | null;
};
type PublicPartner = {
  id: string;
  name: string;
  partner_type: string;
  description: string | null;
  website_url: string | null;
  country_code: string;
  region: string | null;
};

const partnerLogos: Record<string, string> = {
  "University of Nairobi": "/media/nextgen-source/partner-university-of-nairobi.png",
  "Medical College of Wisconsin": "/media/nextgen-source/partner-medical-college-wisconsin.png",
  "Men In Health": "/media/nextgen-source/men-in-health-7b0b71fb0d.png",
  "Eternal Flame Worldwide": "/media/nextgen-source/eternal-flame-worldwide-bf4a67139d.png",
  "Kilifi County Health Department": "/media/nextgen-source/kilifi-county-health-department-acec4dce86.png",
  "Masinde Muliro University (MMUST)": "/media/nextgen-source/partner-mmust.png",
  "CHANCE Network": "/media/nextgen-source/partner-chance-network.png",
};

export default function CommunityPage() {
  const [people, setPeople] = useState<PublicPerson[]>([]);
  const [partners, setPartners] = useState<PublicPartner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      apiGet<PublicPerson[]>(`/public/organizations/${ORGANIZATION_SLUG}/people`),
      apiGet<PublicPartner[]>(`/public/organizations/${ORGANIZATION_SLUG}/partners`),
    ]).then(([peopleRows, partnerRows]) => {
      if (active) {
        setPeople(peopleRows);
        setPartners(partnerRows);
      }
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "The community directory could not be loaded.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <nav aria-label="Community navigation">
          <Link className="secondary-action" href="/#people">Home</Link>
          <Link className="secondary-action" href="/#access">Get involved</Link>
        </nav>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">OUR PEOPLE & COLLABORATORS</p>
        <h1 className="workspace-title">A community working <em>for Earth.</em></h1>
        <p className="workspace-muted">
          Meet the people and organisations publicly listed in the NextGen For Earth directory.
          Profiles shown here are drawn from records approved for public visibility.
        </p>
        {loading ? (
          <p className="workspace-muted" role="status">Loading the community directory…</p>
        ) : error ? (
          <section className="staff-card">
            <h2>Directory unavailable</h2>
            <p className="workspace-error" role="alert">{error}</p>
          </section>
        ) : (
          <>
            <section className="staff-card">
              <h2>People</h2>
              {people.length === 0 ? (
                <p className="workspace-muted">Public people profiles will appear here when approved.</p>
              ) : (
                <div className="portal-grid">
                  {people.map((person) => (
                    <article className="portal-card people-card" key={person.id}>
                      {person.profile_image_url ? (
                        <img className="people-avatar" src={person.profile_image_url} alt={person.full_name} width={112} height={112} loading="lazy" />
                      ) : (
                        <div className="people-avatar people-avatar-fallback" aria-hidden="true">{person.full_name.slice(0, 1)}</div>
                      )}
                      <p className="portal-tag">Community profile</p>
                      <h3>{person.full_name}</h3>
                      {person.positions.length > 0 && <p className="portal-description">{person.positions.join(" · ")}</p>}
                      {person.biography && <p className="portal-description">{person.biography}</p>}
                    </article>
                  ))}
                </div>
              )}
            </section>
            <section className="staff-card">
              <h2>Institutional partners & collaborators</h2>
              {partners.length === 0 ? (
                <p className="workspace-muted">Institutional profiles will appear here after they have been reviewed and approved for public visibility.</p>
              ) : (
                <div className="portal-grid">
                  {partners.map((partner) => (
                    <article className="portal-card partner-card" key={partner.id}>
                      {partnerLogos[partner.name] ? (
                        <div className="partner-logo-frame">
                          <img className="partner-logo" src={partnerLogos[partner.name]} alt={partner.name + " logo"} loading="lazy" />
                        </div>
                      ) : (
                        <div className="partner-logo-frame partner-logo-fallback" aria-hidden="true">
                          {partner.name.slice(0, 2).toUpperCase()}
                        </div>
                      )}
                      <p className="portal-tag">Institutional collaborator</p>
                      <h3>{partner.name}</h3>
                      <p className="portal-description">
                        {partner.partner_type.replaceAll("_", " ")}
                        {partner.region ? ` · ${partner.region}` : ""}
                        {partner.country_code ? ` · ${partner.country_code}` : ""}
                      </p>
                      {partner.description && <p className="portal-description">{partner.description}</p>}
                      {partner.website_url && (
                        <a href={partner.website_url} target="_blank" rel="noreferrer">
                          Visit organisation website <span aria-hidden="true">↗</span>
                        </a>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
        <p><Link href="/volunteer/apply">Explore ways to participate</Link></p>
      </section>
    </main>
  );
}
