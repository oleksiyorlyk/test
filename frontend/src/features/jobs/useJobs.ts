import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type { Job } from "../../shared/api/types";

export function useJobs(storyId?: number) {
  return useQuery({
    queryKey: ["jobs", storyId ?? "all"],
    queryFn: () =>
      api<{ items: Job[] }>(`/jobs${storyId ? `?story_id=${storyId}` : ""}`),
    refetchInterval: 2000,
  });
}
