# AI Test Automation Generator

## O projekte

Nástroj má testerovi pomôcť previesť User Stories z Azure DevOps na testovacie
scenáre a spustiteľné automatizované testy webového UI pomocou LLM a Playwright.
Cieľom je sledovať väzbu medzi požiadavkou, scenárom, testom a výsledkom.
Podrobné zadanie je v [dokumentácii projektu](<AI Automation test generator - Dokumentácia.docx>).

## Workflow

Nasledujúci postup opisuje cieľové riešenie, ktoré ešte nie je celé implementované.

1. Tester vytvorí User Story v Azure DevOps projekte s procesom Agile:
   uvedie názov, opis a akceptačné kritériá.
2. Python backend cez Azure DevOps API načíta všetky User Stories z nastaveného
   boardu. Samostatné riadiace webové UI zobrazí zoznam; tester otvorí konkrétnu
   story a systém ju ďalej spracuje podľa jej ID.
3. Tlačidlom **Generovať scenáre** tester spustí generovanie cez LLM API.
   Každý scenár obsahuje ID, názov, väzbu na akceptačné kritérium, predpoklady,
   testovacie dáta, kroky a očakávaný výsledok.
4. Tester skontroluje celý súbor scenárov a schváli ho alebo požiada
   o opätovné generovanie. Kód testov vznikne až po schválení scenárov.
5. Schválené scenáre sa uložia ako work items prepojené s pôvodnou User Story.
6. Tlačidlo **Spustiť testy** spustí generovanie Playwright kódu zo schválených
   scenárov a následné vykonanie testov nad samostatnou aplikáciou YourTask.
   Vygenerovaný kód sa uloží ako prílohy k User Story.
7. Backend uloží výsledky a vráti ich do riadiaceho UI: prehľad testov a prístup
   k HTML reportu. JSON výstup slúži na automatické spracovanie výsledkov.

Scenáre majú pokrývať úspešný priebeh aj relevantné negatívne a hraničné prípady.
LLM nesmie vymýšľať požiadavky ani selektory; chýbajúce podklady označí ako
`BLOCKED`. Každý test musí konkrétnou kontrolou overovať očakávané správanie.
Testovú logiku generuje AI, nesmie byť vopred naprogramovaná podľa ID stories.
Pri rovnakých východiskových dátach musia byť testy opakovateľné.
Výsledky rozlišujú `PASS`, `FAIL`, chybu generovania alebo spustenia a `BLOCKED`.
Samotný `FAIL` nie je automaticky potvrdenou chybou aplikácie.
Pri neexistujúcej story, chýbajúcich údajoch alebo chybe prístupu UI zobrazí
zrozumiteľnú správu.

## Technológie a výstupy

- **Azure DevOps**: zdroj požiadaviek a miesto prepojenia scenárov a kódu s User Story.
- **Python backend**: komunikácia s Azure DevOps a LLM API, ukladanie výstupov
  a riadenie generovania aj spúšťania testov.
- **LLM API**: generovanie štruktúrovaných scenárov v JSON a Playwright kódu
  s využitím údajov o aplikácii, jej URL, selektorov a testovacích dát.
- **Playwright (JavaScript/Node.js)**: vykonanie testov; HTML report v
  `playwright-report/` a JSON výsledky v `test-results/results.json`.
- **Riadiace UI**: plánované rozhranie pre stories, schvaľovanie, spúšťanie a výsledky.
- **YourTask**: existujúca testovaná aplikácia na registráciu, prihlásenie a správu úloh.

## Aktuálny stav a spustenie

Repozitár obsahuje YourTask, skript [getus.py](getus.py) na načítanie jednej
User Story s pevným ID a konfiguráciu Playwright pre priečinok `generated-tests/`.
Riadiace UI, načítanie zoznamu stories, AI generovanie, ukladanie výstupov do Azure
a návrat výsledkov do UI ešte vyžadujú implementáciu. Vygenerované testy zatiaľ chýbajú.

Na lokálne spustenie aplikácie YourTask je potrebný Node.js s npm:

```sh
npm install
npm run dev
```

Aplikácia bude dostupná na http://127.0.0.1:8000.
