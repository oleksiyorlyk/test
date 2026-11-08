import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronLeft } from "lucide-react";
import { api } from "../../shared/api/client";
import type { Job } from "../../shared/api/types";
import { useJobs } from "./useJobs";
import { JobContent } from "./JobContent";
import { active } from "./status";
import { PageTitle, Loading, ErrorBox } from "../../shared/ui/components";

export function JobDetail() {
  const { id } = useParams();
  const history = useJobs();
  const query = useQuery({
    queryKey: ["job", id],
    queryFn: () => api<Job>(`/jobs/${id}`),
    refetchInterval: (query) => (active(query.state.data) ? 2000 : false),
  });
  const summary = history.data?.items.find((job) => job.id === id);
  const historyStatus = summary?.status;
  const detailStatus = query.data?.status;
  const { refetch } = query;
  useEffect(() => {
    if (historyStatus && detailStatus && historyStatus !== detailStatus) {
      void refetch();
    }
  }, [historyStatus, detailStatus, refetch]);
  return (
    <>
      <Link className="breadcrumb" to="/history">
        <ChevronLeft size={14} /> História behov
      </Link>
      <PageTitle
        eyebrow={`ARCHÍV OPERÁCIÍ / ${id?.slice(0, 8)}`}
        title={
          query.data ? `User Story #${query.data.story_id}` : "Detail operácie"
        }
      >
        {query.data && (
          <Link
            to={`/stories/${query.data.story_id}`}
            className="button button-secondary"
          >
            Otvoriť Story <ArrowUpRight size={16} />
          </Link>
        )}
      </PageTitle>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorBox error={query.error} />
      ) : (
        <JobContent job={query.data} />
      )}
    </>
  );
}
