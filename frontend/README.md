# Riadiaci frontend

Slovenské rozhranie React/TypeScript na výber Stories, kontrolu scenárov,
schválenie, sledovanie operácií a stiahnutie výsledkov. Backend a Docker
spustíte podľa [hlavného README](../README.md).

## Vývoj

Z koreňa repozitára po inštalácii závislostí:

```powershell
uv run --frozen python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001
```

V druhom termináli:

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run dev
```

Rozhranie je na http://127.0.0.1:5173. Používa relatívne `/api`, ktoré Vite
presmeruje na port 8001. V Docker režime rovnakú úlohu vykonáva Nginx na 8080.
Frontend nikdy nedostáva Azure/OpenAI kľúče.

## Zdrojový kód

- `src/app/`: router, providers a spoločné rozloženie.
- `src/features/`: prehľad, Stories, scenáre, operácie, výsledky a pripojenie.
- `src/shared/`: HTTP klient, typy API, spoločné prvky a štýly.
- `e2e/`: prehliadačové testy; komponentné testy sú pri príslušnej funkcii.

Rozhranie používa React Router, TanStack Query a React Hook Form.
Dizajn: žltá `#FFCD11`, grafitová `#171717`, svetlé pozadie `#F4F4F1`.
Barlow Condensed a IBM Plex Sans sa načítavajú lokálne. Podporovaná šírka
začína na 360 px; ovládanie zahŕňa klávesnicu a viditeľné zameranie prvkov.

## Správanie

- Obrazovky: **Prehľad**, **User Stories**, **História behov**, **Pripojenie**.
- Detail Story: **Požiadavky**, **Scenáre**, **Výsledky**, **Artefakty**.
- Editor umožňuje pridávať, mazať a filtrovať scenáre `READY`/`BLOCKED`.
  Citácia z kritéria musí mať aspoň 20 znakov; rozhoduje serverová validácia.
- Neuložené zmeny blokujú schválenie a vyžadujú potvrdenie pri odchode.
  Pri konflikte hash zostávajú úpravy na obrazovke do vedomého načítania konceptu.
- Stav operácie sa obnovuje každé dve sekundy. Úspech testov a publikácie
  sa vyhodnocuje oddelene; čiastočná publikácia sa automaticky neopakuje.

## Kontroly a typy API

Príkazy v priečinku `frontend/`:

```powershell
npm.cmd run build
npm.cmd run lint -- --max-warnings=0
npm.cmd run format:check
npm.cmd test
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Pri zmene API exportujte z koreňa schému cez
`uv run --frozen python -m backend.export_openapi` a spustite
`npm.cmd --prefix frontend run api:generate`. `npm run api:check` overí zhodu.
Schéma aj generované typy patria do Git; `types.ts` obsahuje iba aliasy.

Testy používajú náhrady API. Skutočné pripojenie Azure/OpenAI sa overuje osobitne.
Ak API nie je dostupné, skontrolujte Uvicorn alebo `docker compose ps` a log backendu.
