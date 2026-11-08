# Playwright runner

Runner vykonáva JavaScript testy vytvorené backendom nad aplikáciou
[YourTask](../target-app/). Nie je testovacím projektom riadiaceho frontend.
Celý postup spustenia je v [hlavnom README](../README.md).

## Obsah

- `playwright.config.js`: prehliadač, server a výstupné reporty.
- `app-context.json`: kontext YourTask pre generátor.
- `test-data.json`, `tests/helpers/app-state.js`: potrebné dáta a príprava testov.
- `generated-tests/`: lokálne vygenerované testy podľa Story a revízie.
- `test-results/`, `playwright-report/`: JSON výsledky a HTML report.

Testovacie dáta a helper patria do Git; generované testy a reporty nie.
Relatívne importy existujúcich `.spec.js` sa pri presune nemenia.

## Inštalácia

Z koreňa repozitára v PowerShell:

```powershell
npm.cmd --prefix runner ci
Push-Location runner
npx.cmd playwright install chromium
Pop-Location
```

Používa sa Playwright Test **1.64.1**. Docker ho inštaluje samostatne a kontroluje
zhodu s verziou obrazu. Balík je v `runner/node_modules/@playwright/test`;
prehliadače v `%LOCALAPPDATA%/ms-playwright`, v kontajneri v `/ms-playwright`.

## Vykonanie

Stage 2 spúšťa `npx --no-install playwright test generated-tests/story-…`
z runnera. Playwright obsluhuje `target-app` na `127.0.0.1:8000`.
Port nesmie používať iná aplikácia. V Compose zostáva YourTask aj runner
v backend službe, bez publikovania portu 8000.

V runneri `npm run dev` spustí iba YourTask a `npm run report` otvorí report.
`npm run test:e2e` vykoná všetky nájdené testy a prepíše pracovné výsledky;
nespúšťajte ho súčasne s backend workflow. Na bežný chod používajte schválenie v UI.

Po rozbalení archivovaného ZIP reportu použite
`npx playwright show-report <adresar>`. Kontajnerový smoke test spustíte z koreňa:

```powershell
docker compose exec -T backend python -m backend.tests.container_smoke
```

Smoke používa vlastný dočasný test a nemení používateľské reporty.
Nevolá Azure/OpenAI ani nevykonáva vygenerované používateľské testy.
