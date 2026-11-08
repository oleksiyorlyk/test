# GitLab CI

[.gitlab-ci.yml](../.gitlab-ci.yml) spúšťa kontroly po push, pri merge requeste
alebo ručne cez **Build → Pipelines → New pipeline / Run pipeline**.
Pri otvorenom MR sa duplicitná push pipeline nevytvára. Samotné klonovanie
repozitára CI nespustí.

## Kontroly

| Job | Obsah |
| --- | --- |
| `backend` | Python 3.12, zmrazené závislosti, Ruff, testy, OpenAPI a kontroly repozitára |
| `frontend` | Node.js 24, typy, formátovanie, zostavenie, komponentné a prehliadačové testy |
| `docker` | Zostavenie obrazov, štart oboch služieb, Chromium/YourTask, Nginx a API |
| `backend_windows` | Voliteľné serverové testy na Windows Runneri |

CI nepoužíva reálne Azure/OpenAI kľúče, nepublikuje do Azure a aplikáciu
nenasadzuje. Zelený výsledok nepotvrdzuje sieť ani konfiguráciu iného počítača.

## Runner

Linux jobs používajú tag `docker`, ktorý majú dostupné instance runners TUKE.
V **Settings → CI/CD → Runners → Instance** musia byť pre projekt povolené.
Tag sám nepotvrdzuje podporu Docker-in-Docker.

Docker job používa DinD s TLS na porte 2376. Administrátor musí mať v konfigurácii
runnera povolený Docker executor, privileged režim a zdieľané certifikáty:

```toml
[[runners]]
  executor = "docker"
  [runners.docker]
    privileged = true
    volumes = ["/certs/client", "/cache"]
```

Tieto oprávnenia sa nenastavujú v repozitári. Runner potrebuje sieťový prístup
k Docker Hub, ghcr.io, mcr.microsoft.com, PyPI, npm a prehliadačom Playwright.
Podrobnosti: [GitLab Docker CI](https://docs.gitlab.com/ci/docker/using_docker_build/).

## Dáta a výsledky

[compose.ci.yaml](../compose.ci.yaml) používa dočasné named volumes a nepublikuje
porty. Každý job má vlastný Compose projekt; pracovná história sa nekopíruje.
Používa sa iba `.env.example`. Skript odmietne prepísať existujúci `.env`.
Po skončení odstráni svoje kontajnery a volumes.

Frontend zostavenie, JUnit výsledky, diagnostické súbory testov a Docker logy
sa uchovávajú sedem dní ako artifacts. Docker logy sú v `.ci-artifacts/`.

Windows job zapnete premennými `RUN_WINDOWS_TESTS=1` a
`WINDOWS_RUNNER_TAG=<tag>`. Vyžaduje Windows shell runner s Git, Python 3.12
a uv 0.13.7. Štandardne sa kontroluje Linux.

## Pri chybe

- `pending`: overte dostupnosť runnera, tag `docker` a obmedzenia vetvy.
- Nedostupný Docker alebo chyba TLS: overte privileged režim a `/certs/client`.
- Chyba inštalácie: overte DNS, proxy a dostupnosť registrov runnera.
- Neaktuálne kontrakty: obnovte exporty podľa dokumentácie backendu.

Konfiguráciu možno overiť v **Pipeline editor → Validate / CI Lint**.
Lokálny skúšobný beh neoveruje oprávnenia školského runnera; tie potvrdí
prvý skutočný pipeline po push.
