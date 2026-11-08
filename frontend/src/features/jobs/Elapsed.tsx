import { useEffect, useState } from "react";
import type { Job } from "../../shared/api/types";
import { active } from "./status";

export function Elapsed({ job }: { job: Job }) {
  const [time, setTime] = useState(Date.now());
  useEffect(() => {
    if (!active(job)) return;
    const timer = setInterval(() => setTime(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [job]);
  const seconds = Math.max(
    0,
    Math.floor(
      ((active(job) ? time : new Date(job.updated_at).getTime()) -
        new Date(job.created_at).getTime()) /
        1000,
    ),
  );
  return (
    <span>
      {Math.floor(seconds / 60)} min {seconds % 60} s
    </span>
  );
}
