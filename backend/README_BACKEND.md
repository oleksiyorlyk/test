# Backend

Python balík poskytuje HTTP API a riadi generovanie, schvaľovanie,
vykonanie testov a publikovanie. Inštalácia a konfigurácia sú v
[hlavnom README](../README.md).

## Moduly

| Priečinok | Zodpovednosť |
| --- | --- |
| `routes/` | HTTP požiadavky a odpovede |
| `services/` | Generovanie scenárov, schvaľovanie a správa operácií |
| `integrations/` | Azure, OpenAI a zadania pre model |
| `execution/` | Generovanie JS, Playwright, spracovanie výsledkov a worker |
| `storage/` | SQLite, JSON, archív artefaktov a migrácie |
| `models/` | Modely scenárov a HTTP kontrakty |
| `core/` | Konfigurácia, cesty, chyby a blokovanie súbežných operácií |
| `tests/` | Automatické testy s náhradami externých služieb |

## Spustenie a pracovný postup

Z koreňa repozitára:

```powershell
uv sync --frozen
uv run --frozen python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001
```

Používajte jeden API worker a počas operácií nepoužívajte `--reload`.
Kľúče sa čítajú z `backend/.env`. Swagger je na `/docs`.

- **Stage 1:** načítanie Story, normalizácia a návrh scenárov bez zápisu do Azure.
- **Stage 2:** výslovné schválenie, generovanie kódu, testy a publikovanie.
- Uloženie a schválenie vyžadujú aktuálny `review_hash`; schválenie aj revíziu.
- Naraz beží jedna operácia v samostatnom Python procese. Stratený proces sa
  označí `INTERRUPTED`, bez automatického opakovania.

## HTTP API

| Metóda a cesta | Účel |
| --- | --- |
| `GET /api/health` | Bezpečná lokálna diagnostika |
| `GET /api/stories` | Katalóg, hľadanie, stav, zoradenie a stránkovanie |
| `GET /api/stories/{id}` | Normalizované požiadavky bez LLM |
| `POST /api/stories/{id}/generate` | Stage 1; odpoveď `202` s `job_id` |
| `GET /api/stories/{id}/review` | Koncept a hash |
| `PUT /api/stories/{id}/review` | Uloženie celého konceptu s hashom |
| `POST /api/stories/{id}/approve-and-run` | Stage 2 s hashom a revíziou |
| `GET /api/jobs`, `GET /api/jobs/{id}` | História, stav, výsledky a denník |
| `GET /api/jobs/{id}/artifacts/{artifact_id}` | Stiahnutie uloženého súboru |

Chyby majú tvar `{error: {code, message, details?}}`. Rozhranie je lokálne;
povolené origin používajú porty 5173, 8001 a 8080. Úspešné vykonanie testov
nezaručuje úspešnú publikáciu. Výsledky a nové artefakty sa zachovajú aj pri chybe.

## Dáta, migrácie a CLI

Scenáre sú v `data/stories/`, SQLite a nemenné artefakty v `data/control/`.
`CONTROL_DATA_DIR` umožňuje zmeniť adresár histórie.

Pri aktualizácii zo starej štruktúry zastavte API aj Compose a dokončite operácie:

```powershell
uv run --frozen python -m backend.migrate_data
uv run --frozen python -m backend.migrate_runner
```

Prvá migrácia prenáša starú históriu `control_api/data`; druhá testy a reporty
z `test aplikacia` do runnera. Vytvárajú overené zálohy v `data/backups/`,
odmietajú konfliktný cieľ a nemenia už prenesené dáta.

Kompatibilné CLI zostávajú: `backend.stage1`, `backend.stage2`,
`backend.generate_playwright`, `backend.process_results`, `backend.publish_outputs`
a `backend.worker`. Parametre zobrazíte cez `--help`. Stage 2 predstavuje schválenie;
samostatné CLI nespúšťajte súčasne s operáciou z UI.

## Kontroly a kontrakty

```powershell
uv run --frozen python -m unittest discover -s backend/tests -v
uv run --frozen ruff check backend scripts
uv run --frozen ruff format --check backend scripts
uv run --frozen python -m backend.export_openapi --check
uv run --frozen python scripts/check_requirements.py
```

Zdrojom závislostí je `pyproject.toml` a `uv.lock`. Kompatibilný pip export obnovíte:

```powershell
uv export --frozen --no-dev --no-emit-project --format requirements-txt --no-header --no-annotate --no-hashes --output-file backend/requirements.txt --quiet
```

Pri zmene HTTP modelov spustite `python -m backend.export_openapi`, potom
`npm.cmd --prefix frontend run api:generate`. Import ani export nevytvára databázu.
