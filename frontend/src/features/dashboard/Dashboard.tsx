import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Box,
  Check,
  CircleCheck,
  FileCode2,
  FlaskConical,
  FolderOpen,
} from "lucide-react";
import { useJobs } from "../jobs/useJobs";
import { OpenStory } from "../stories/OpenStory";
import { Loading, ErrorBox } from "../../shared/ui/components";
import { JobTable } from "../jobs/JobTable";

export function Dashboard() {
  const jobs = useJobs();
  const all = jobs.data?.items ?? [];
  const executions = all.filter((j) => j.kind === "EXECUTE");
  const counts = [
    {
      label: "SPRACOVANÉ STORIES",
      value: new Set(all.map((j) => j.story_id)).size,
      icon: FolderOpen,
    },
    {
      label: "VYGENEROVANÉ NÁVRHY",
      value: all.filter(
        (j) => j.kind === "GENERATE" && j.status === "SUCCEEDED",
      ).length,
      icon: FileCode2,
    },
    { label: "TESTOVACIE BEHY", value: executions.length, icon: FlaskConical },
    {
      label: "ÚSPEŠNÉ TESTY",
      value: executions.reduce(
        (sum, j) => sum + (j.result?.execution?.passed ?? 0),
        0,
      ),
      icon: CircleCheck,
    },
  ];
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span /> VAŠE TESTOVACIE PRACOVISKO
          </p>
          <h1>
            OD POŽIADAVKY
            <br />K <em>ISTOTE.</em>
          </h1>
          <p className="hero-description">
            Premeňte User Stories na testy, ktorým rozumiete.
            <br />
            Navrhnite. Skontrolujte. Spustite.
          </p>
          <Link to="/stories" className="button button-primary">
            Prehliadať User Stories <ArrowUpRight size={18} />
          </Link>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="drawing-grid" />
          <div className="machine-ring ring-outer" />
          <div className="machine-ring ring-inner" />
          <div className="circuit circuit-one" />
          <div className="circuit circuit-two" />
          <div className="diagram-core">
            <Box size={58} strokeWidth={1} />
          </div>
          <div className="diagram-tag tag-one">
            01 / POŽIADAVKA <Check size={12} />
          </div>
          <div className="diagram-tag tag-two">
            02 / AI SCENÁRE <Check size={12} />
          </div>
          <div className="diagram-tag tag-three">
            03 / OVERENÝ VÝSLEDOK <ArrowDown size={12} />
          </div>
          <span className="drawing-label">
            SYSTEM / QUALITY ASSURANCE
            <br />
            ENGINEERED FOR CONFIDENCE
          </span>
        </div>
        <OpenStory hero />
      </section>
      <section
        className="metrics-grid"
        aria-label="Štatistiky lokálnej histórie"
      >
        {counts.map(({ label, value, icon: Icon }, index) => (
          <article className="metric" key={label}>
            <div>
              <span className="metric-index">0{index + 1}</span>
              <Icon size={20} />
            </div>
            <strong>
              {jobs.isError ? "—" : value.toString().padStart(2, "0")}
            </strong>
            <p>{label}</p>
          </article>
        ))}
      </section>
      <div className="section-heading">
        <div>
          <p className="eyebrow">VAŠA AKTIVITA</p>
          <h2>Posledné operácie</h2>
        </div>
        <Link to="/history" className="text-button">
          Celá história <ArrowRight size={16} />
        </Link>
      </div>
      <section className="panel">
        {jobs.isPending ? (
          <Loading />
        ) : jobs.isError ? (
          <ErrorBox error={jobs.error} retry={() => jobs.refetch()} />
        ) : (
          <JobTable jobs={all.slice(0, 5)} />
        )}
      </section>
      <section className="workflow-strip">
        <div>
          <span>01</span>
          <h3>Vyberte požiadavku</h3>
          <p>Načítajte Story z Azure DevOps.</p>
        </div>
        <ArrowRight />
        <div>
          <span>02</span>
          <h3>Skontrolujte scenáre</h3>
          <p>AI navrhne. Rozhodujete vy.</p>
        </div>
        <ArrowRight />
        <div>
          <span>03</span>
          <h3>Overte výsledok</h3>
          <p>Spustite testy a otvorte report.</p>
        </div>
      </section>
    </>
  );
}
