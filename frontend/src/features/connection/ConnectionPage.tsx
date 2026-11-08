import { useQuery } from "@tanstack/react-query";
import { Check, ShieldCheck, Terminal, X } from "lucide-react";
import { api } from "../../shared/api/client";
import type { Health } from "../../shared/api/types";
import { PageTitle, Loading, ErrorBox } from "../../shared/ui/components";

const checkLabels: Record<string, { label: string; help: string }> = {
  azure: {
    label: "Azure DevOps",
    help: "Doplňte AZURE_DEVOPS_ORGANIZATION, AZURE_DEVOPS_PROJECT a AZURE_DEVOPS_PAT v backend/.env.",
  },
  openai: {
    label: "OpenAI API",
    help: "Doplňte OPENAI_API_KEY v backend/.env. Model môžete nastaviť cez OPENAI_MODEL.",
  },
  node: {
    label: "Node.js",
    help: "Nainštalujte Node.js a pridajte ho do PATH.",
  },
  npm: {
    label: "npm / npx",
    help: "Skontrolujte inštaláciu npm. V PowerShell môžete použiť npm.cmd.",
  },
  playwright: {
    label: "Playwright",
    help: "V priečinku runner spustite npm ci a npx playwright install chromium.",
  },
};

export function Connection() {
  const query = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
  });
  return (
    <>
      <PageTitle eyebrow="PROSTREDIE / DIAGNOSTIKA" title="Pripojenie">
        <button
          className="button button-secondary"
          onClick={() => query.refetch()}
        >
          Obnoviť kontrolu
        </button>
      </PageTitle>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorBox error={query.error} />
      ) : (
        <>
          <div className="connection-overview panel">
            <div>
              <span className="eyebrow">ORGANIZÁCIA AZURE</span>
              <h2>{query.data.organization || "Nenastavené"}</h2>
            </div>
            <div>
              <span className="eyebrow">PROJEKT</span>
              <h2>{query.data.project || "Nenastavené"}</h2>
            </div>
            <span className="mode-label">
              <Terminal size={16} /> LOKÁLNY REŽIM
            </span>
          </div>
          <div className="diagnostic-list">
            {Object.entries(query.data.checks).map(([key, ok]) => (
              <article className="panel diagnostic" key={key}>
                <span
                  className={`check-icon ${ok ? "check-ok" : "check-missing"}`}
                >
                  {ok ? <Check size={21} /> : <X size={21} />}
                </span>
                <div>
                  <h3>{checkLabels[key]?.label || key}</h3>
                  <p>
                    {ok
                      ? "Lokálna konfigurácia je dostupná."
                      : checkLabels[key]?.help}
                  </p>
                </div>
                <span className={`diagnostic-status ${ok ? "text-green" : ""}`}>
                  {ok ? "PRIPRAVENÉ" : "VYŽADUJE NASTAVENIE"}
                </span>
              </article>
            ))}
          </div>
          <div className="alert">
            <ShieldCheck size={20} />
            <div>
              <strong>Kľúče zostávajú na vašom počítači.</strong>
              <p>
                Táto kontrola overuje prítomnosť konfigurácie a nástrojov, nie
                platnosť prihlasovacích údajov ani inštaláciu prehliadača. Po
                zmene .env reštartujte adaptér. API kľúče sa v rozhraní
                nezobrazujú.
              </p>
            </div>
          </div>
        </>
      )}
    </>
  );
}
