import {
  AlertCircle,
  Download,
  ExternalLink,
  LoaderCircle,
  RefreshCw,
  Search,
} from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import { ApiError } from "../api/client";

const labels: Record<string, string> = {
  READY: "Pripravený",
  BLOCKED: "Zablokovaný",
  QUEUED: "Čaká na spustenie",
  RUNNING: "Prebieha",
  SUCCEEDED: "Dokončené",
  FAILED: "Zlyhanie",
  INTERRUPTED: "Prerušené",
  PASSED: "Úspešný",
  TIMED_OUT: "Čas vypršal",
  SKIPPED: "Preskočený",
  NOT_RUN: "Nespustený",
  FLAKY: "Nestabilný",
  UNKNOWN: "Neznámy",
  PUBLISHED: "Publikované",
};

export function Badge({ status }: { status: string }) {
  return (
    <span className={`badge badge-${status.toLowerCase()}`}>
      <span className="status-dot" />
      {labels[status] || status}
    </span>
  );
}

export function PageTitle({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
      </div>
      {children}
    </div>
  );
}

export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Search size={27} />
      </div>
      <h3>{title}</h3>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" /> Načítavam údaje…
    </div>
  );
}

export function ErrorBox({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div className="alert alert-error" role="alert">
      <AlertCircle size={20} />
      <div>
        <strong>
          {error instanceof Error ? error.message : String(error)}
        </strong>
        {error instanceof ApiError && error.details && (
          <p className="error-detail">{error.details}</p>
        )}
        {retry && (
          <button className="text-button" onClick={retry}>
            <RefreshCw size={14} /> Skúsiť znova
          </button>
        )}
      </div>
    </div>
  );
}

export function External({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="external"
    >
      {children}
      <ExternalLink size={14} />
    </a>
  );
}

export function DownloadLink({
  job,
  id,
  name,
}: {
  job: string;
  id: string;
  name: string;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  return (
    <div>
      <a
        className="button button-secondary"
        href={`/api/jobs/${job}/artifacts/${id}`}
        download={name}
        aria-disabled={pending}
        onClick={async (event) => {
          event.preventDefault();
          if (pending) return;
          setPending(true);
          setError("");
          try {
            const response = await fetch(`/api/jobs/${job}/artifacts/${id}`);
            if (!response.ok)
              throw new Error("Súbor sa nepodarilo stiahnuť. Skúste to znova.");
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement("a");
            link.href = url;
            link.download = name;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 10000);
          } catch (exc) {
            setError(
              exc instanceof Error ? exc.message : "Sťahovanie zlyhalo.",
            );
          } finally {
            setPending(false);
          }
        }}
      >
        {pending ? (
          <LoaderCircle size={16} className="spin" />
        ) : (
          <Download size={16} />
        )}
        Stiahnuť
      </a>
      {error && (
        <p className="text-red" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
