import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import type { Job } from "../../shared/api/types";
import { date } from "../../shared/format";
import { Badge, Empty } from "../../shared/ui/components";

export function JobTable({ jobs }: { jobs: Job[] }) {
  return jobs.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Operácia / User Story</th>
            <th>Revízia</th>
            <th>Vytvorené</th>
            <th>Stav operácie</th>
            <th>Testy</th>
            <th>
              <span className="sr-only">Otvoriť</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>
                <Link className="table-link" to={`/jobs/${job.id}`}>
                  {job.kind === "GENERATE"
                    ? "Generovanie scenárov"
                    : "Spustenie a publikovanie"}
                </Link>
                <small>USER STORY #{job.story_id}</small>
              </td>
              <td>{job.revision ?? "—"}</td>
              <td>{date(job.created_at)}</td>
              <td>
                <Badge status={job.status} />
              </td>
              <td>
                {job.result?.execution ? (
                  <span>
                    <b className="text-green">{job.result.execution.passed}</b>{" "}
                    / {job.result.execution.total} úspešných
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td>
                <Link
                  to={`/jobs/${job.id}`}
                  className="icon-button"
                  aria-label={`Otvoriť operáciu pre Story ${job.story_id}`}
                >
                  <ArrowRight size={18} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty title="Zatiaľ žiadne operácie">
      <p>História sa vytvorí po prvom generovaní scenárov.</p>
      <Link className="text-button" to="/stories">
        Vybrať User Story <ArrowRight size={16} />
      </Link>
    </Empty>
  );
}
