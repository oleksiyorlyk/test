import { useEffect } from "react";
import {
  useNavigate,
  useParams,
  useSearchParams,
  Link,
} from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  ChevronLeft,
  FileCode2,
} from "lucide-react";
import { api, post } from "../../shared/api/client";
import type { Review, Story } from "../../shared/api/types";
import { useJobs } from "../jobs/useJobs";
import { Results } from "../results/Results";
import { ScenarioEditor } from "../scenarios/ScenarioEditor";
import { active } from "../jobs/status";
import {
  PageTitle,
  Empty,
  Loading,
  ErrorBox,
  External,
  DownloadLink,
} from "../../shared/ui/components";
import { JobTable } from "../jobs/JobTable";

export function StoryDetail() {
  const { id } = useParams();
  const storyId = Number(id);
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "requirements";
  const client = useQueryClient();
  const navigate = useNavigate();
  const jobs = useJobs(storyId);
  const running = jobs.data?.items.find(active);
  const allJobs = useJobs();
  const busy = !!allJobs.data?.items.some(active);
  const story = useQuery({
    queryKey: ["story", storyId],
    queryFn: () => api<Story>(`/stories/${storyId}`),
  });
  const review = useQuery({
    queryKey: ["review", storyId],
    queryFn: () => api<Review>(`/stories/${storyId}/review`),
    enabled: !busy,
  });
  const latestGenerated = jobs.data?.items.find(
    (j) => j.kind === "GENERATE" && j.status === "SUCCEEDED",
  )?.id;
  useEffect(() => {
    if (!busy) {
      client.invalidateQueries({ queryKey: ["review", storyId] });
    }
  }, [busy, latestGenerated, storyId, client]);
  const generate = useMutation({
    mutationFn: () => post<{ job_id: string }>(`/stories/${storyId}/generate`),
    onSuccess: (data) => {
      client.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/jobs/${data.job_id}`);
    },
  });
  const execute = useMutation({
    mutationFn: () =>
      post<{ job_id: string }>(`/stories/${storyId}/approve-and-run`, {
        revision: review.data!.revision,
        review_hash: review.data!.review_hash,
      }),
    onSuccess: (data) => {
      client.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/jobs/${data.job_id}`);
    },
  });
  const current = review.data?.story || story.data;
  const executionJob = jobs.data?.items.find(
    (j) => j.kind === "EXECUTE" && j.result?.execution,
  );
  const artifactJobs = jobs.data?.items.filter((j) => j.artifacts.length) ?? [];
  const approve = () => {
    if (
      window.confirm(
        "Schváliť tento koncept? Generátor vytvorí a spustí testy a publikuje Test Cases a reporty do Azure DevOps.",
      )
    )
      execute.mutate();
  };
  return (
    <>
      <Link className="breadcrumb" to="/stories">
        <ChevronLeft size={14} /> User Stories
      </Link>
      <PageTitle
        eyebrow={`USER STORY #${id}${current ? ` / REVÍZIA ${current.revision}` : ""}`}
        title={current?.title || `User Story #${id}`}
      >
        {current?.source?.url && (
          <External href={current.source.url}>Otvoriť v Azure</External>
        )}
      </PageTitle>
      <ErrorBox error={generate.error || execute.error} />
      {running && (
        <div className="alert">
          <div>
            <strong>Pre túto Story práve beží operácia.</strong>
            <p>
              Úpravy sú do jej dokončenia nedostupné.{" "}
              <Link to={`/jobs/${running.id}`}>Zobraziť priebeh →</Link>
            </p>
          </div>
        </div>
      )}
      <nav className="detail-tabs" aria-label="Detail User Story">
        {[
          ["requirements", "Požiadavky"],
          ["scenarios", "Scenáre"],
          ["results", "Výsledky"],
          ["artifacts", "Artefakty"],
        ].map(([key, label]) => (
          <Link
            to={`?tab=${key}`}
            className={tab === key ? "selected" : ""}
            key={key}
          >
            {label}
            {key === "scenarios" && review.data && (
              <span>{review.data.draft.scenarios.length}</span>
            )}
          </Link>
        ))}
      </nav>
      {tab === "requirements" && (
        <>
          {!current && story.isPending ? (
            <Loading />
          ) : !current ? (
            <ErrorBox error={story.error} retry={() => story.refetch()} />
          ) : (
            <div className="requirements-grid">
              <section className="panel prose">
                <p className="eyebrow">KONTEXT POŽIADAVKY</p>
                <h2>Opis User Story</h2>
                <p className="preserve-lines">
                  {current.description || "Opis nie je uvedený."}
                </p>
                <div className="requirements-generate">
                  <h3>Pripravené na ďalší krok?</h3>
                  <p>
                    AI navrhne scenáre podľa akceptačných kritérií. Pred
                    spustením ich skontrolujete.
                  </p>
                  <button
                    className="button button-primary"
                    disabled={
                      busy || generate.isPending || !current.ready_for_llm
                    }
                    onClick={() => {
                      if (
                        !review.data ||
                        window.confirm(
                          "Nahradiť existujúci koncept novým generovaním?",
                        )
                      )
                        generate.mutate();
                    }}
                  >
                    <FileCode2 size={17} />
                    Generovať scenáre <ArrowRight size={17} />
                  </button>
                  {review.data && (
                    <button
                      className="text-button"
                      onClick={() => setParams({ tab: "scenarios" })}
                    >
                      Otvoriť koncept <ArrowRight size={16} />
                    </button>
                  )}
                </div>
                {current.warnings.length > 0 && (
                  <div className="alert">
                    <AlertTriangle size={18} />
                    <div>
                      <strong>Požiadavka vyžaduje kontrolu</strong>
                      <ul>
                        {current.warnings.map((warning, i) => (
                          <li key={i}>{warning}</li>
                        ))}
                      </ul>
                      {current.unparsed_acceptance_criteria && (
                        <p className="preserve-lines">
                          {current.unparsed_acceptance_criteria}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </section>
              <section className="panel criteria-list">
                <div className="panel-heading">
                  <h2>Akceptačné kritériá</h2>
                  <span className="count-label">
                    {current.acceptance_criteria.length} AC
                  </span>
                </div>
                {current.acceptance_criteria.map((ac) => (
                  <article key={ac.id}>
                    <span>{ac.id}</span>
                    <p>{ac.text}</p>
                  </article>
                ))}
              </section>
            </div>
          )}
        </>
      )}
      {tab === "scenarios" &&
        (review.data ? (
          <ScenarioEditor
            key={`${storyId}-${review.data.review_hash}`}
            review={review.data}
            busy={busy}
            onSaved={(value) => client.setQueryData(["review", storyId], value)}
            onGenerate={() => generate.mutate()}
            onApprove={approve}
          />
        ) : review.isPending && !busy ? (
          <Loading />
        ) : (
          <section className="panel">
            {review.error &&
            "status" in review.error &&
            (review.error as { status: number }).status !== 404 ? (
              <ErrorBox error={review.error} retry={() => review.refetch()} />
            ) : (
              <Empty
                title={
                  busy
                    ? "Generátor práve pracuje"
                    : "Scenáre ešte nie sú pripravené"
                }
              >
                <p>Najskôr načítajte požiadavky a spustite generovanie.</p>
                <button
                  className="button button-primary"
                  disabled={busy || !current?.ready_for_llm}
                  onClick={() => generate.mutate()}
                >
                  Generovať scenáre
                </button>
              </Empty>
            )}
          </section>
        ))}
      {tab === "results" && (
        <>
          {executionJob ? (
            <>
              <section className="panel">
                <div className="panel-heading">
                  <h2>Posledný dostupný výsledok</h2>
                  <Link to={`/jobs/${executionJob.id}`} className="text-button">
                    Detail behu <ArrowRight size={16} />
                  </Link>
                </div>
                <Results execution={executionJob.result!.execution!} />
              </section>
              <div className="section-heading">
                <h2>Operácie tejto Story</h2>
              </div>
              <section className="panel">
                <JobTable jobs={jobs.data?.items ?? []} />
              </section>
            </>
          ) : (
            <section className="panel">
              <Empty title="Zatiaľ bez výsledkov">
                <p>
                  Testy sa vytvoria a spustia po schválení pripravených
                  scenárov.
                </p>
              </Empty>
            </section>
          )}
          {review.data?.draft.scenarios.some((s) => s.status === "BLOCKED") && (
            <div className="alert">
              <div>
                <strong>Zablokované scenáre aktuálneho konceptu</strong>
                {review.data.draft.scenarios
                  .filter((s) => s.status === "BLOCKED")
                  .map((s) => (
                    <p key={s.test_id}>
                      {s.test_id} — {s.blocked_reason}
                    </p>
                  ))}
              </div>
            </div>
          )}
        </>
      )}
      {tab === "artifacts" &&
        (artifactJobs.length ? (
          artifactJobs.map((job) => (
            <section className="panel" key={job.id}>
              <div className="panel-heading">
                <h2>
                  {job.kind === "GENERATE" ? "Návrh scenárov" : "Testovací beh"}{" "}
                  / rev. {job.revision ?? "—"}
                </h2>
                <Link to={`/jobs/${job.id}`} className="text-button">
                  Detail <ArrowRight size={15} />
                </Link>
              </div>
              <ul className="artifact-list">
                {job.artifacts.map((file) => (
                  <li key={file.id}>
                    <FileCode2 size={20} />
                    <div>
                      <strong>{file.name}</strong>
                      <small>
                        {Math.max(1, Math.ceil(file.size / 1024))} KB
                      </small>
                    </div>
                    <DownloadLink job={job.id} id={file.id} name={file.name} />
                  </li>
                ))}
              </ul>
            </section>
          ))
        ) : (
          <section className="panel">
            <Empty title="Zatiaľ žiadne artefakty" />
          </section>
        ))}
    </>
  );
}
