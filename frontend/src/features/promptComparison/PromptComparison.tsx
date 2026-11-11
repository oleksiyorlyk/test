import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Download, GitCompareArrows, Play, RefreshCw } from "lucide-react";
import { api, post } from "../../shared/api/client";
import { Badge, Empty, ErrorBox, Loading, PageTitle } from "../../shared/ui/components";

type Metrics = {
  scenarios: number; ready: number; blocked: number;
  covered_ac: number; total_ac: number; coverage_percent: number;
  valid: boolean; elapsed_seconds: number;
  model: string; errors: string[]; warnings: string[];
};
type Scenario = {
  test_id: string; title: string; acceptance_criterion_id: string;
  test_type: string; status: string; actions: string[]; expected_results: string[];
};
type ScenarioBatch = { story_id: number; scenarios: Scenario[] };
type Run = {
  id: string; story_id: number; status: string; started_at: string;
  finished_at?: string; message?: string; results?: { A: Metrics; B: Metrics };
  prompt_a?: ScenarioBatch; prompt_b?: ScenarioBatch;
};
type RunList = { items: Run[] };
const inProgress = (s?: string) => s === "RUNNING" || s === "QUEUED";
const metrics: { label: string; key: keyof Metrics }[] = [
  { label: "Počet scenárov", key: "scenarios" },
  { label: "Pripravené (READY)", key: "ready" },
  { label: "Zablokované (BLOCKED)", key: "blocked" },
  { label: "Pokrytie kritérií (%)", key: "coverage_percent" },
  { label: "Validný výstup", key: "valid" },
  { label: "Čas generovania (s)", key: "elapsed_seconds" },
];
function metric(value: number | boolean | string | string[]) {
  if (typeof value === "boolean") return value ? "Áno" : "Nie";
  if (typeof value === "number") return String(value).replace(".", ",");
  return String(value);
}
function Scenarios({ batch, heading }: { batch?: ScenarioBatch; heading: string }) {
  if (!batch) return null;
  return (
    <section className="pc-scenario-column">
      <h3>{heading} <span className="pc-count">{batch.scenarios.length}</span></h3>
      {batch.scenarios.map((scenario) => (
        <details className="pc-scenario" key={scenario.test_id}>
          <summary>
            <span className="pc-scenario-id">{scenario.test_id} · {scenario.acceptance_criterion_id}</span>
            <strong>{scenario.title}</strong>
            <span className="pc-type">{scenario.test_type} · {scenario.status}</span>
          </summary>
          <div className="pc-scenario-body">
            <b>Kroky</b>
            <ol>{scenario.actions.map((step, i) => <li key={i}>{step}</li>)}</ol>
            <b>Očakávané výsledky</b>
            <ul>{scenario.expected_results.map((step, i) => <li key={i}>{step}</li>)}</ul>
          </div>
        </details>
      ))}
    </section>
  );
}
export function PromptComparison() {
  const queryClient = useQueryClient();
  const [storyId, setStoryId] = useState("1");
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({
    queryKey: ["prompt-comparisons"],
    queryFn: () => api<RunList>("/prompt-comparisons"),
    refetchInterval: 3000,
  });
  const activeId = selected ?? list.data?.items[0]?.id ?? null;
  const detail = useQuery({
    queryKey: ["prompt-comparison", activeId],
    queryFn: () => api<Run>(`/prompt-comparisons/${activeId}`),
    enabled: !!activeId,
    refetchInterval: (query) => inProgress(query.state.data?.status) ? 2000 : false,
  });
  const start = useMutation({
    mutationFn: (id: number) => post<Run>("/prompt-comparisons", { story_id: id }),
    onSuccess: (run) => {
      setSelected(run.id);
      void queryClient.invalidateQueries({ queryKey: ["prompt-comparisons"] });
    },
  });
  const detailStatus = detail.data?.status;

useEffect(() => {
  if (detailStatus && !inProgress(detailStatus)) {
    void queryClient.invalidateQueries({ queryKey: ["prompt-comparisons"] });
  }
}, [detailStatus, queryClient]);
  const run = detail.data;
  const items = list.data?.items ?? [];
  return (
    <div className="pc-page">
      <PageTitle eyebrow="EXPERIMENTY / LLM" title="Porovnanie promptov">
        <button className="button button-secondary" type="button" onClick={() => {
          void list.refetch();
          if (activeId) void detail.refetch();
        }}><RefreshCw size={15} /> Obnoviť</button>
      </PageTitle>
      <div className="pc-intro">
        <div>
          <p className="eyebrow">DVE STRATÉGIE · ROVNAKÝ MODEL</p>
          <h2>Jeden príbeh. Dva prompty.<br /><em>Merateľný výsledok.</em></h2>
          <p>Prompt A používa pôvodné inštrukcie. Prompt B pridáva podrobnejšie QA plánovanie. Každé porovnanie sa uloží do lokálneho archívu, bez zmeny bežného generovania testov.</p>
        </div>
        <GitCompareArrows size={94} strokeWidth={1.15} aria-hidden="true" />
      </div>
      <section className="panel pc-launch" aria-label="Spustiť porovnanie">
        <form onSubmit={(e) => {
          e.preventDefault();
          const number = Number(storyId);
          if (Number.isSafeInteger(number) && number > 0) start.mutate(number);
        }}>
          <label htmlFor="pc-story-id">AZURE DEVOPS · USER STORY ID</label>
          <input id="pc-story-id" type="number" min="1" step="1" required value={storyId} onChange={e => setStoryId(e.target.value)} />
          <button className="button button-primary" type="submit" disabled={start.isPending || items.some(i => inProgress(i.status))}>
            <Play size={15} /> {start.isPending ? "Spúšťam…" : "Spustiť porovnanie"}
          </button>
        </form>
        <small>Experiment iba číta User Story z Azure DevOps a používa existujúci OpenAI API prístup. Nezverejňuje výsledky v Azure. Každý beh spotrebuje dva LLM API requesty.</small>
        {start.isError && <ErrorBox error={start.error} />}
      </section>
      <div className="pc-content">
        <section className="panel pc-history">
          <div className="pc-section-head"><div><p className="eyebrow">ULOŽENÉ EXPERIMENTY</p><h2>História porovnaní</h2></div></div>
          {list.isPending ? <Loading /> : list.isError ? <ErrorBox error={list.error} /> : items.length === 0 ? <Empty title="Zatiaľ žiadne porovnanie">Spustite prvý experiment.</Empty> : (
            <div className="pc-run-list">{items.map(item => (
              <button key={item.id} type="button" className={`pc-run ${item.id === activeId ? "pc-run-active" : ""}`} onClick={() => setSelected(item.id)}>
                <span><b>Story #{item.story_id}</b><small>{new Date(item.started_at).toLocaleString("sk-SK")}</small></span>
                <span className="pc-run-side"><Badge status={item.status} /><ArrowRight size={14} /></span>
              </button>
            ))}</div>
          )}
        </section>
        <section className="panel pc-report" aria-live="polite">
          <div className="pc-section-head">
            <div><p className="eyebrow">VÝSLEDKY EXPERIMENTU</p><h2>{run ? `User Story #${run.story_id}` : "Report porovnania"}</h2></div>
            {run && <Badge status={run.status} />}
          </div>
          {!activeId ? <Empty title="Vyberte alebo spustite porovnanie">Výsledky sa zobrazia na tomto mieste.</Empty> : detail.isPending ? <Loading /> : detail.isError ? <ErrorBox error={detail.error} /> : run && inProgress(run.status) ? (
            <div className="pc-wait"><span className="pc-pulse" /><b>Porovnanie práve prebieha</b><p>Načítavame aktuálny stav. Stránka sa automaticky aktualizuje.</p></div>
          ) : run?.status === "SUCCEEDED" && run.results ? (
            <>
              <div className="pc-comparison-head"><span>PÔVODNÝ PROMPT <b>A</b></span><span>ROZŠÍRENÝ PROMPT <b>B</b></span></div>
              <table className="pc-metrics"><thead><tr><th>Metrika</th><th>Prompt A</th><th>Prompt B</th></tr></thead>
                <tbody>{metrics.map(({label, key}) => (
                  <tr key={key}><th scope="row">{label}</th><td>{metric(run.results!.A[key])}</td><td>{metric(run.results!.B[key])}</td></tr>
                ))}</tbody>
              </table>
              <div className="pc-report-actions"><span><CheckCircle2 size={16} /> Report je uložený v lokálnom archíve</span>
                <a className="button button-secondary" href={`/api/prompt-comparisons/${run.id}/report`} download><Download size={15} /> Stiahnuť report</a>
              </div>
              <p className="page-note">Pokrytie a validita sú automatické kontroly. Kvalitu testov je potrebné posúdiť aj manuálne.</p>
            </>
          ) : <div className="pc-wait"><b>Experiment nie je dokončený.</b><p>{run?.message ?? "Skontrolujte nastavenia Azure DevOps a OpenAI."}</p></div>}
        </section>
      </div>
      {run?.status === "SUCCEEDED" && (run.prompt_a || run.prompt_b) && (
        <div className="pc-scenario-grid">
          <Scenarios batch={run.prompt_a} heading="Prompt A · Scenáre" />
          <Scenarios batch={run.prompt_b} heading="Prompt B · Scenáre" />
        </div>
      )}
    </div>
  );
}
