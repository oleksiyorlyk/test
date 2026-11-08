# TESTFORGE — AI Test Automation Generator

Lokálna aplikácia na prevod Azure DevOps User Stories na testovacie scenáre
a Playwright testy. Používateľ návrh skontroluje, upraví a výslovne schváli.
Backend potom vykoná testy a publikuje Test Cases, kód a reporty do Azure.

## Štruktúra

| Priečinok | Obsah |
| --- | --- |
| `backend/` | Python API, Azure/OpenAI, generovanie, operácie a úložisko |
| `frontend/` | Riadiace rozhranie React/TypeScript |
| `runner/` | Playwright, testovacie dáta, generované testy a reporty |
| `target-app/` | YourTask, testovaná aplikácia HTML/CSS/JavaScript |
| `contracts/` | OpenAPI schéma pre spoločné typy API |
| `scripts/` | Kontroly repozitára, závislostí a CI |
| `docs/` | Príručka CI a pôvodné zadanie projektu |

Prehliadač → frontend/Nginx → backend/FastAPI → Azure, OpenAI a Playwright.
Runner aj YourTask sú v backend kontajneri; Compose má presne dve služby.

## Spustenie cez Docker

Potrebujete Docker Desktop s Linux kontajnermi alebo Docker Engine s Compose.
Všetky príkazy spúšťajte z koreňa repozitára.

1. Ak `backend/.env` neexistuje, skopírujte `backend/.env.example` ako `.env`
   v tom istom priečinku. Existujúci súbor neprepisujte.
2. Vyplňte organizáciu a projekt Azure, PAT, OpenAI kľúč a dostupný model.
   Azure projekt musí podporovať User Story a Test Case; PAT potrebuje
   čítanie a zápis work items. Kľúče sa neposielajú do frontend ani do Git.
3. Spustite:

```powershell
docker compose up --build -d
```

- Rozhranie: **http://localhost:8080**
- API dokumentácia: http://localhost:8080/docs
- Diagnostika: http://localhost:8080/api/health

```powershell
docker compose ps
docker compose logs -f backend
docker compose down
```

Pred zastavením počkajte na dokončenie operácie. Dáta zostávajú na disku
aj po zastavení alebo opätovnom zostavení kontajnerov.

## Používanie

1. V **Pripojenie** skontrolujte konfiguráciu a nástroje. Táto kontrola
   overuje ich prítomnosť, nie platnosť kľúčov.
2. Vyberte Story; požiadavky musia obsahovať jednoznačné kritériá AC1, AC2…
3. Spustite **Generovať scenáre** a skontrolujte návrh.
4. Upravte scenáre a zvoľte **Uložiť zmeny**.
5. **Schváliť a spustiť** vykoná testy aj publikovanie.
6. V histórii otvorte výsledky, denník a artefakty.

`SUCCEEDED` označuje dokončený pracovný postup, nie úspech všetkých testov.
Scenáre `BLOCKED` sa nevykonávajú. Pri čiastočnej publikácii skontrolujte
manifest a Azure pred opakovaním; dokončené vzdialené zápisy sa nevracajú späť.

## Lokálny vývoj

Potrebujete Python 3.12–3.14, uv 0.13.7 a Node.js 24. PowerShell:

```powershell
uv sync --frozen
npm.cmd --prefix frontend ci
npm.cmd --prefix runner ci
Push-Location runner
npx.cmd playwright install chromium
Pop-Location
```

V samostatných termináloch:

```powershell
uv run --frozen python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001
npm.cmd --prefix frontend run dev
```

Otvorte http://127.0.0.1:5173; Vite presmeruje `/api` na backend. Po zostavení
frontend a reštarte API možno používať aj http://127.0.0.1:8001.
Na Linux/macOS použite `npm` a `npx` bez `.cmd`.

## Dáta a overenie

História, scenáre a archív sú v `backend/data/`; pracovné testy a reporty
v `runner/`. Závislosti, dáta, zostavenie, reporty a `.env` sa necommitujú.
Zdrojové súbory, automatické testy, konfigurácie, schéma a lock-súbory zostávajú v Git.

Nespúšťajte lokálny a Docker backend súčasne nad rovnakými dátami. Aplikácia
je určená pre jedného lokálneho používateľa a jednu aktívnu operáciu.

```powershell
uv run --frozen python -m unittest discover -s backend/tests -v
uv run --frozen python scripts/check_repository.py
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

GitLab pipeline sa spúšťa po push, pri merge requeste alebo ručne.
Používa runner s tagom `docker`; Docker job vyžaduje privileged DinD a TLS.
CI používa náhrady Azure/OpenAI a aplikáciu nenasadzuje.

Podrobnosti: [backend](backend/README_BACKEND.md), [frontend](frontend/README.md),
[runner](runner/README.md), [GitLab CI](docs/ci.md).
Pôvodné zadanie: [dokument projektu](docs/project-specification.docx).
