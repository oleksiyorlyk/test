import { Search } from "lucide-react";
type Props = {
  search: string;
  status: string;
  type: string;
  setSearch: (value: string) => void;
  setStatus: (value: string) => void;
  setType: (value: string) => void;
};
export function ScenarioFilters({
  search,
  status,
  type,
  setSearch,
  setStatus,
  setType,
}: Props) {
  return (
    <div className="scenario-filters">
      <div className="search-field">
        <Search size={16} />
        <input
          aria-label="Hľadať scenár"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Hľadať scenár…"
        />
      </div>
      <select
        aria-label="Stav scenára"
        value={status}
        onChange={(e) => setStatus(e.target.value)}
      >
        <option value="">Všetky stavy</option>
        <option value="READY">Pripravené</option>
        <option value="BLOCKED">Zablokované</option>
      </select>
      <select
        aria-label="Typ testu"
        value={type}
        onChange={(e) => setType(e.target.value)}
      >
        <option value="">Všetky typy</option>
        <option value="positive">Pozitívne</option>
        <option value="negative">Negatívne</option>
        <option value="boundary">Hraničné</option>
      </select>
    </div>
  );
}
