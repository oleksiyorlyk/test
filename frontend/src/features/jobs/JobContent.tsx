import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  CircleCheck,
  Clock3,
  FileCode2,
  Terminal,
} from "lucide-react";
import { api } from "../../shared/api/client";
import type { Health, Job } from "../../shared/api/types";
import { Results } from "../results/Results";
import { date } from "../../shared/format";
import { active } from "./status";
import {
  Badge,
  Empty,
  External,
  DownloadLink,
} from "../../shared/ui/components";
import { Elapsed } from "./Elapsed";

export function JobContent({ job }: { job: Job }) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
  });
  const azure =
    health.data?.organization && health.data?.project
      ? `https://dev.azure.com/${encodeURIComponent(health.data.organization)}/${encodeURIComponent(health.data.project)}/_workitems/edit/`
      : null;
  return (
    <>
      <section
        className={`panel job-summary ${active(job) ? "job-active" : ""}`}
      >
        <div className="job-symbol">
          {active(job) ? (
            <Activity size={30} />
          ) : job.status === "SUCCEEDED" ? (
            <CircleCheck size={30} />
          ) : (
            <Clock3 size={30} />
          )}
        </div>
        <div>
          <p className="eyebrow">
            {job.kind === "GENERATE"
              ? "GENEROVANIE SCENÁROV"
              : "SCHVÁLENIE / TESTOVANIE / PUBLIKOVANIE"}
          </p>
          <h2>
            {active(job)
              ? "Operácia prebieha"
              : job.status === "SUCCEEDED"
                ? "Operácia dokončená"
                : "Operácia nebola dokončená"}
          </h2>
          <p className="muted">
            {active(job)
              ? "Môžete prejsť na inú stránku. Stav sa aktualizuje každé 2 sekundy."
              : `Začiatok: ${date(job.created_at)}`}{" "}
            · <Elapsed job={job} />
          </p>
        </div>
        <Badge status={job.status} />
      </section>
      {job.error && (
        <div className="alert alert-error" role="alert">
          <div>
            <strong>{job.error.message}</strong>
            {job.error.details && (
              <p className="error-detail">{job.error.details}</p>
            )}
            {job.result?.publication === "PARTIAL" && (
              <p>
                Niektoré položky už mohli byť publikované v Azure. Skontrolujte
                uložený manifest pred novým spustením.
              </p>
            )}
          </div>
        </div>
      )}
      {job.kind === "GENERATE" && job.status === "SUCCEEDED" && (
        <Link
          className="button button-primary"
          to={`/stories/${job.story_id}?tab=scenarios`}
        >
          Otvoriť aktuálne scenáre <ArrowRight size={17} />
        </Link>
      )}
      {job.result?.execution && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Výsledky testov</h2>
            {job.status === "SUCCEEDED" && <Badge status="PUBLISHED" />}
          </div>
          <p className="panel-description">
            Stav operácie vyjadruje dokončenie workflow. Výsledok každého testu
            sa hodnotí samostatne.
          </p>
          <Results execution={job.result.execution} />
        </section>
      )}
      {!!job.result?.devops?.blocked?.length && (
        <div className="alert">
          <div>
            <strong>Zablokované scenáre</strong>
            <p>
              {job.result.devops.blocked.join(", ")} — tieto scenáre sa
              nespúšťali.
            </p>
          </div>
        </div>
      )}
      {!!Object.keys(job.result?.devops?.test_cases ?? {}).length && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Test Cases v Azure</h2>
          </div>
          <div className="case-links">
            {Object.entries(job.result!.devops!.test_cases).map(([test, id]) =>
              azure ? (
                <External key={test} href={`${azure}${id}`}>
                  {test} → #{id}
                </External>
              ) : (
                <span key={test}>
                  {test} → #{id}
                </span>
              ),
            )}
          </div>
        </section>
      )}
      <section className="panel">
        <div className="panel-heading">
          <h2>Artefakty operácie</h2>
          <span className="count-label">{job.artifacts.length} SÚBOROV</span>
        </div>
        {job.artifacts.length ? (
          <ul className="artifact-list">
            {job.artifacts.map((file) => (
              <li key={file.id}>
                <FileCode2 size={21} />
                <div>
                  <strong>{file.name}</strong>
                  <small>{Math.max(1, Math.ceil(file.size / 1024))} KB</small>
                </div>
                <DownloadLink job={job.id} id={file.id} name={file.name} />
              </li>
            ))}
          </ul>
        ) : (
          <Empty
            title={
              active(job)
                ? "Artefakty budú dostupné po dokončení"
                : "Žiadne nové artefakty"
            }
          />
        )}
      </section>
      <details className="panel log-panel" open={active(job)}>
        <summary>
          <Terminal size={17} /> Denník operácie
        </summary>
        <pre>{job.log || "Denník zatiaľ neobsahuje žiadne záznamy."}</pre>
      </details>
    </>
  );
}
