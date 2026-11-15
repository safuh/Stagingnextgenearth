"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type Programme = {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
};
type ProgrammeProject = {
  id: string;
  title: string;
  summary: string | null;
  status: string;
  country_code: string;
  county: string | null;
};
type Course = {
  id: string;
  title: string;
  slug: string;
  description: string;
  category: string | null;
  delivery_mode: string;
};

export default function ProgrammeDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const [programme, setProgramme] = useState<Programme | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [projects, setProjects] = useState<ProgrammeProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const programmes = await apiGet<Programme[]>(
          "/public/organizations/nextgen-for-earth/programmes",
        );
        const selected = programmes.find((item) => item.slug === slug) ?? null;
        if (!selected) {
          if (active) setProgramme(null);
          return;
        }
        const [linkedCourses, linkedProjects] = await Promise.all([
          apiGet<Course[]>(
            `/public/organizations/nextgen-for-earth/programmes/${encodeURIComponent(slug)}/courses`,
          ),
          apiGet<ProgrammeProject[]>(
            `/public/organizations/nextgen-for-earth/programmes/${encodeURIComponent(slug)}/projects`,
          ),
        ]);
        if (active) {
          setProgramme(selected);
          setCourses(linkedCourses);
          setProjects(linkedProjects);
        }
      } catch (cause) {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Unable to load this programme.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [slug]);

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="brand" href="/">NextGen For Earth</Link>
        <Link className="secondary-action" href="/#programmes">All programmes</Link>
      </header>
      <section className="workspace-content">
        <p className="eyebrow">PROGRAMME DIRECTORY</p>
        {loading ? (
          <p className="workspace-muted">Loading programme…</p>
        ) : error ? (
          <p className="workspace-error" role="alert">{error}</p>
        ) : !programme ? (
          <section className="staff-card">
            <h1>Programme not found</h1>
            <p>This programme is not currently published in the public catalogue.</p>
            <Link href="/#programmes">Return to the programme directory</Link>
          </section>
        ) : (
          <>
            <h1 className="workspace-title">{programme.title}</h1>
            <p className="workspace-muted">{programme.summary || "Programme information will be updated by the programme team."}</p>
            <p className="workspace-muted">
              Status: {programme.status}
              {programme.start_date ? ` · Starts ${programme.start_date}` : ""}
              {programme.end_date ? ` · Ends ${programme.end_date}` : ""}
            </p>
            <section className="staff-card">
              <h2>Projects and implementation</h2>
              {projects.length === 0 ? (
                <p className="workspace-muted">Project information will be published here as implementation records are added.</p>
              ) : (
                <div className="portal-grid">
                  {projects.map((project) => (
                    <article className="portal-card" key={project.id}>
                      <p className="portal-tag">
                        {project.status.replaceAll("_", " ")}
                        {project.county ? ` · ${project.county}` : ""}
                        {project.country_code ? ` · ${project.country_code}` : ""}
                      </p>
                      <h3>{project.title}</h3>
                      <p className="portal-description">{project.summary || "Project details will be updated by the programme team."}</p>
                    </article>
                  ))}
                </div>
              )}
            </section>
            <section className="staff-card">
              <h2>Learning opportunities</h2>
              {courses.length === 0 ? (
                <p className="workspace-muted">No public courses are currently linked to this programme.</p>
              ) : (
                <div className="portal-grid">
                  {courses.map((course) => (
                    <article className="portal-card" key={course.id}>
                      <p className="portal-tag">Course · {course.delivery_mode.replaceAll("_", " ")}</p>
                      <h3>{course.title}</h3>
                      <p className="portal-description">{course.description}</p>
                      {course.category && <p className="portal-description">{course.category}</p>}
                    </article>
                  ))}
                </div>
              )}
            </section>
            <p><Link href="/volunteer/apply">Explore volunteer opportunities</Link></p>
          </>
        )}
      </section>
    </main>
  );
}
