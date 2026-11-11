import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  FolderOpen,
  History as HistoryIcon,
  GitCompareArrows,
  LayoutDashboard,
  Menu,
  Settings2,
  ShieldCheck,
  X,
} from "lucide-react";
import { api } from "../shared/api/client";
import type { Health } from "../shared/api/types";
import { useJobs } from "../features/jobs/useJobs";
import { active } from "../features/jobs/status";

export function Layout() {
  const [open, setOpen] = useState(false);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
    refetchInterval: 30000,
  });
  const jobs = useJobs();
  const current = jobs.data?.items.find(active);
  const nav = [
    { to: "/", label: "Prehľad", icon: LayoutDashboard },
    { to: "/stories", label: "User Stories", icon: FolderOpen },
    { to: "/history", label: "História behov", icon: HistoryIcon },
    { to: "/prompt-comparison", label: "Porovnanie promptov", icon: GitCompareArrows },
    { to: "/connection", label: "Pripojenie", icon: Settings2 },
  ];
  return (
    <>
      <div className="utility-bar">
        <div className="shell">
          <span>
            <span className="tiny-square" /> AI TEST AUTOMATION GENERATOR
          </span>
          <span>
            LOKÁLNE PRACOVISKO <span className="utility-separator">/</span> WEB
            UI · PLAYWRIGHT
          </span>
        </div>
      </div>
      <header className="site-header">
        <div className="shell header-main">
          <Link to="/" className="brand" aria-label="TESTFORGE — prehľad">
            <span className="brand-mark">
              T<span />
            </span>
            <span>
              TESTFORGE<small>AI TEST CONTROL</small>
            </span>
          </Link>
          <div className="project-name">
            <span className="eyebrow">PRIPOJENÝ PROJEKT</span>
            <strong>{health.data?.project || "Azure DevOps"}</strong>
          </div>
          <Link className="connection-status" to="/connection">
            <span
              className={`status-dot ${health.data?.checks.azure ? "online" : "offline"}`}
            />
            {health.isError
              ? "Adaptér nedostupný"
              : health.data?.checks.azure
                ? "Lokálny adaptér"
                : "Nastaviť pripojenie"}
            <ArrowUpRight size={15} />
          </Link>
          <button
            className="icon-button mobile-menu"
            aria-label={open ? "Zavrieť menu" : "Otvoriť menu"}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? <X /> : <Menu />}
          </button>
        </div>
        <nav
          className={`main-nav ${open ? "nav-open" : ""}`}
          aria-label="Hlavná navigácia"
        >
          <div className="shell">
            {nav.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                onClick={() => setOpen(false)}
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
            <span className="nav-right">
              <ShieldCheck size={15} /> HUMAN IN THE LOOP
            </span>
          </div>
        </nav>
      </header>
      {current && (
        <Link to={`/jobs/${current.id}`} className="running-banner">
          <span className="shell">
            <Activity size={16} />{" "}
            {current.kind === "GENERATE"
              ? "Generovanie scenárov"
              : "Testovanie a publikovanie"}{" "}
            · Story #{current.story_id}
            <span>
              Zobraziť operáciu <ArrowRight size={15} />
            </span>
          </span>
        </Link>
      )}
      <main className="shell main-content" id="main-content">
        <Outlet />
      </main>
      <footer>
        <div className="shell">
          <span>
            <b>TESTFORGE</b> / OD POŽIADAVKY K VÝSLEDKU.
          </span>
          <span>
            Azure DevOps <span>·</span> OpenAI <span>·</span> Playwright
          </span>
        </div>
      </footer>
    </>
  );
}
