import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Search,
  ShieldCheck,
} from "lucide-react";
import { api } from "../../shared/api/client";
import type { Catalog } from "../../shared/api/types";
import { OpenStory } from "./OpenStory";
import { date } from "../../shared/format";
import {
  PageTitle,
  Empty,
  Loading,
  ErrorBox,
} from "../../shared/ui/components";

export function Stories() {
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const [sort, setSort] = useState("changed");
  const [page, setPage] = useState(1);
  const [submitted, setSubmitted] = useState("");
  const query = useQuery({
    queryKey: ["stories", submitted, state, sort, page],
    queryFn: () =>
      api<Catalog>(
        `/stories?${new URLSearchParams({ search: submitted, state, sort, page: String(page) })}`,
      ),
  });
  return (
    <>
      <PageTitle
        eyebrow="AZURE DEVOPS / KATALÓG POŽIADAVIEK"
        title="User Stories"
      >
        <OpenStory />
      </PageTitle>
      <section className="panel catalog-panel">
        <div className="toolbar">
          <form
            className="search-field"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted(search);
              setPage(1);
            }}
          >
            <Search size={18} />
            <input
              aria-label="Hľadať User Stories"
              placeholder="Hľadať podľa názvu alebo #ID…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button className="button button-dark" type="submit">
              Hľadať
            </button>
          </form>
          <label className="filter-label">
            Stav
            <select
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Všetky stavy</option>
              {query.data?.states.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="filter-label">
            Zoradenie
            <select
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setPage(1);
              }}
            >
              <option value="changed">Naposledy zmenené</option>
              <option value="title">Názov A–Z</option>
              <option value="id">ID zostupne</option>
            </select>
          </label>
        </div>
        {query.isPending ? (
          <Loading />
        ) : query.isError ? (
          <ErrorBox error={query.error} retry={() => query.refetch()} />
        ) : query.data.items.length ? (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Názov User Story</th>
                    <th>Stav v Azure</th>
                    <th>Priradené</th>
                    <th>Posledná zmena</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <Link className="story-id" to={`/stories/${row.id}`}>
                          #{row.id}
                        </Link>
                      </td>
                      <td>
                        <Link className="table-link" to={`/stories/${row.id}`}>
                          {row.title}
                        </Link>
                        <small>USER STORY</small>
                      </td>
                      <td>
                        <span className="azure-state">{row.state}</span>
                      </td>
                      <td>
                        {row.assigned_to || (
                          <span className="muted">Nepriradené</span>
                        )}
                      </td>
                      <td>{date(row.changed_at)}</td>
                      <td>
                        <Link
                          className="icon-button"
                          aria-label={`Otvoriť Story ${row.id}`}
                          to={`/stories/${row.id}`}
                        >
                          <ArrowUpRight size={19} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <span>
                {query.data.total} User Stories · strana {page} z{" "}
                {Math.max(1, Math.ceil(query.data.total / 20))}
              </span>
              <div>
                <button
                  className="icon-button"
                  aria-label="Predchádzajúca strana"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  <ChevronLeft size={18} />
                </button>
                <button
                  className="icon-button"
                  aria-label="Ďalšia strana"
                  disabled={page * 20 >= query.data.total}
                  onClick={() => setPage(page + 1)}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          </>
        ) : (
          <Empty title="Nenašli sa žiadne User Stories">
            <p>Zmeňte hľadaný výraz alebo filter stavu.</p>
          </Empty>
        )}
      </section>
      <p className="page-note">
        <ShieldCheck size={16} /> Požiadavky sa načítavajú z nakonfigurovaného
        Azure projektu. Generovanie spustíte až v detaile Story.
      </p>
    </>
  );
}
