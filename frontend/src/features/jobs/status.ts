import type { Job } from "../../shared/api/types";

export const active = (job?: Job) =>
  !!job && ["QUEUED", "RUNNING"].includes(job.status);
