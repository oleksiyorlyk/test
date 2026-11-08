import { useState } from "react";
import { useJobs } from "./useJobs";
import { PageTitle, Loading, ErrorBox } from "../../shared/ui/components";
import { JobTable } from "./JobTable";

export function History() {
  const query = useJobs();
  const [filter, setFilter] = useState("");
  const items = (query.data?.items ?? []).filter(
    (j) => !filter || j.status === filter,
  );
  return (
    <>
      <PageTitle eyebrow="LOKÁLNY ARCHÍV" title="História behov">
        <label className="filter-label">
          Stav operácie
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">Všetky operácie</option>
            <option value="SUCCEEDED">Dokončené</option>
            <option value="FAILED">Zlyhania</option>
            <option value="RUNNING">Prebiehajúce</option>
            <option value="QUEUED">Čakajúce</option>
            <option value="INTERRUPTED">Prerušené</option>
          </select>
        </label>
      </PageTitle>
      <section className="panel">
        {query.isPending ? (
          <Loading />
        ) : query.isError ? (
          <ErrorBox error={query.error} />
        ) : (
          <JobTable jobs={items} />
        )}
      </section>
      <p className="page-note">
        História obsahuje operácie spustené cez TESTFORGE. Každý beh má vlastné
        uložené artefakty.
      </p>
    </>
  );
}
