import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
const ac = "Correct credentials open the workspace.";
function review() {
  return {
    story_id: 1,
    revision: 84,
    status: "PENDING_REVIEW",
    review_hash: "hash1",
    story: {
      id: 1,
      revision: 84,
      title: "User login",
      description: "As a registered user I want to sign in.",
      ready_for_llm: true,
      warnings: [],
      acceptance_criteria: [{ id: "AC1", text: ac }],
      source: { url: "https://dev.azure.com/org/project/_workitems/edit/1" },
    },
    draft: {
      story_id: 1,
      scenarios: [
        {
          test_id: "TC-001",
          title: "Successful login",
          acceptance_criterion_id: "AC1",
          evidence_quote: ac,
          test_type: "positive",
          preconditions: ["User exists"],
          test_data: [],
          actions: ["Log in"],
          expected_results: ["Workspace visible"],
          status: "READY",
          blocked_reason: null,
        },
      ],
    },
    validation: {
      valid: true,
      errors: [],
      warnings: [],
      coverage: { AC1: ["TC-001"] },
      scenario_count: 1,
      ready_count: 1,
      blocked_count: 0,
    },
  };
}
async function setup(
  page: Page,
  {
    conflict = false,
    empty = false,
    missing = false,
    azureError = false,
    partial = false,
  } = {},
) {
  let current = review();
  let started = false;
  let reads = 0;
  const job = () => ({
    id: "run-1",
    story_id: 1,
    revision: 84,
    kind: "EXECUTE",
    status: reads < 2 ? "RUNNING" : partial ? "FAILED" : "SUCCEEDED",
    created_at: "2026-11-06T10:00:00Z",
    updated_at: "2026-11-06T10:01:00Z",
    artifacts:
      reads < 2
        ? []
        : [{ id: "a1", name: "execution.summary.json", size: 123 }],
    error: partial
      ? { code: "WORKFLOW_FAILED", message: "Publikovanie zlyhalo." }
      : null,
    result:
      reads < 2
        ? null
        : {
            publication: partial ? "PARTIAL" : undefined,
            execution: {
              total: 1,
              passed: 0,
              failed: 1,
              timed_out: 0,
              flaky: 0,
              skipped: 0,
              not_run: 0,
              interrupted: 0,
              unknown: 0,
              tests: [
                {
                  test_id: "TC-001",
                  acceptance_criterion_id: "AC1",
                  title: "Successful login",
                  status: "FAILED",
                  duration_ms: 10,
                  attempts: 1,
                  failure: {
                    type: "ASSERTION_MISMATCH",
                    message: "Expected workspace",
                  },
                },
              ],
            },
            devops: { test_cases: { "TC-001": 8 }, blocked: [] },
          },
    log: "Running Playwright…",
  });
  await page.context().route(
    (url) => url.pathname.startsWith("/api/"),
    async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      let body: unknown = {};
      let status = 200;
      if (path === "/api/health")
        body = {
          organization: "tuke",
          project: "AI Test Automation",
          checks: {
            azure: true,
            openai: true,
            node: true,
            npm: true,
            playwright: true,
          },
          mode: "local",
        };
      else if (path === "/api/stories") {
        if (azureError) {
          status = 502;
          body = {
            error: { code: "AZURE_ACCESS", message: "Azure odmietlo prístup." },
          };
        } else
          body = {
            items: empty
              ? []
              : [
                  {
                    id: 1,
                    title: "User login",
                    state: "New",
                    assigned_to: "Test Engineer",
                    changed_at: "2026-11-06T09:00:00Z",
                  },
                ],
            total: empty ? 0 : 1,
            states: ["New"],
            page: 1,
            page_size: 20,
          };
      } else if (path === "/api/stories/1") body = current.story;
      else if (path.endsWith("/review")) {
        if (missing) {
          status = 404;
          body = {
            error: { code: "NOT_FOUND", message: "Koncept sa nenašiel." },
          };
        } else if (route.request().method() === "PUT") {
          if (conflict) {
            status = 409;
            body = {
              error: {
                code: "STALE_REVIEW",
                message: "Koncept sa zmenil. Načítajte aktuálnu verziu.",
              },
            };
          } else {
            current = {
              ...current,
              draft: route.request().postDataJSON().draft,
              review_hash: "hash2",
            };
            body = current;
          }
        } else body = current;
      } else if (path.endsWith("/approve-and-run")) {
        started = true;
        status = 202;
        body = { job_id: "run-1", status: "QUEUED" };
      } else if (path === "/api/jobs") body = { items: started ? [job()] : [] };
      else if (path === "/api/jobs/run-1") {
        reads++;
        body = job();
      } else if (path.endsWith("/artifacts/a1")) {
        await route.fulfill({
          status: 200,
          contentType: "application/octet-stream",
          headers: {
            "Content-Disposition":
              'attachment; filename="execution.summary.json"',
          },
          body: '{"failed":1}',
        });
        return;
      }
      await route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    },
  );
}
test("catalog → edit → save → approve → report and download", async ({
  page,
}) => {
  await setup(page);
  await page.context().route("**/api/stories/1/generate", (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ job_id: "generate-1", status: "QUEUED" }),
    }),
  );
  await page.context().route("**/api/jobs/generate-1", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "generate-1",
        story_id: 1,
        revision: 84,
        kind: "GENERATE",
        status: "SUCCEEDED",
        created_at: "2026-11-06T10:00:00Z",
        updated_at: "2026-11-06T10:00:10Z",
        artifacts: [],
        error: null,
        result: review(),
      }),
    }),
  );
  await page.goto("/stories");
  await page.getByRole("link", { name: "User login", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Otvoriť koncept" }),
  ).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Generovať scenáre", exact: false })
    .click();
  await expect(page).toHaveURL(/jobs\/generate-1/);
  await page.getByRole("link", { name: "Otvoriť aktuálne scenáre" }).click();
  await page
    .getByLabel("Názov scenára", { exact: true })
    .fill("Updated login test");
  await expect(
    page.getByRole("button", { name: "Schváliť a spustiť" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Uložiť zmeny" }).click();
  await expect(
    page.getByRole("button", { name: "Schváliť a spustiť" }),
  ).toBeEnabled();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Schváliť a spustiť" }).click();
  await expect(page).toHaveURL(/jobs\/run-1/);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Operácia dokončená" }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Publikované", { exact: true })).toBeVisible();
  await expect(page.getByText("Zlyhanie", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Stiahnuť", exact: true }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("execution.summary.json");
  expect(await file.failure()).toBeNull();
});
test("hash conflict preserves edits and leaving needs confirmation", async ({
  page,
}) => {
  await setup(page, { conflict: true });
  await page.goto("/stories/1?tab=scenarios");
  await page
    .getByLabel("Názov scenára", { exact: true })
    .fill("Do not lose this");
  await page.getByRole("button", { name: "Uložiť zmeny" }).click();
  await expect(page.getByRole("alert")).toContainText("Koncept sa zmenil");
  await expect(page.getByLabel("Názov scenára", { exact: true })).toHaveValue(
    "Do not lose this",
  );
  await page.getByRole("link", { name: "Požiadavky", exact: true }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByRole("button", { name: "Zostať", exact: true }).click();
  await expect(page.getByLabel("Názov scenára", { exact: true })).toHaveValue(
    "Do not lose this",
  );
});
test("add and delete a blocked scenario", async ({ page }) => {
  await setup(page);
  await page.goto("/stories/1?tab=scenarios");
  await page.getByRole("button", { name: "Pridať scenár" }).click();
  const card = page.locator("details.scenario-card").last();
  await expect(card).toContainText("TC-002");
  await card
    .getByRole("combobox", { name: "Stav", exact: true })
    .selectOption("BLOCKED");
  await card.getByLabel("Dôvod blokovania").fill("Missing requirements");
  page.once("dialog", (dialog) => dialog.accept());
  await card.getByRole("button", { name: "Odstrániť scenár" }).click();
  await expect(page.locator("details.scenario-card")).toHaveCount(1);
});
test("empty catalog and narrow layout", async ({ page }, testInfo) => {
  await setup(page, { empty: true });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "OD POŽIADAVKY K ISTOTE." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: testInfo.outputPath("dashboard.png"),
    fullPage: true,
  });
  await page.goto("/stories");
  await expect(page.getByText("Nenašli sa žiadne User Stories")).toBeVisible();
});
test("Azure error and missing draft are explicit", async ({ page }) => {
  await setup(page, { azureError: true, missing: true });
  await page.goto("/stories");
  await expect(page.getByRole("alert")).toContainText("Azure odmietlo");
  await page.goto("/stories/1?tab=scenarios");
  await expect(page.getByText("Scenáre ešte nie sú pripravené")).toBeVisible();
});
test("partial publication is a failed operation with available results", async ({
  page,
}) => {
  await setup(page, { partial: true });
  await page.goto("/stories/1?tab=scenarios");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Schváliť a spustiť" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Niektoré položky už mohli byť publikované",
    { timeout: 15000 },
  );
  await expect(page.getByText("Publikované", { exact: true })).toHaveCount(0);
});

test("job detail refreshes when history corrects a terminal status", async ({
  page,
}) => {
  await setup(page);
  let recovered = false;
  const job = () => ({
    id: "recover-1",
    story_id: 1,
    revision: 84,
    kind: "EXECUTE",
    status: recovered ? "SUCCEEDED" : "INTERRUPTED",
    created_at: "2026-11-06T10:00:00Z",
    updated_at: "2026-11-06T10:01:00Z",
    artifacts: [],
    result: recovered ? { status: "PUBLISHED" } : null,
    error: recovered
      ? null
      : { code: "INTERRUPTED", message: "Proces bol prerušený." },
  });
  await page.context().route("**/api/jobs", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items: [job()] }),
    }),
  );
  await page.context().route("**/api/jobs/recover-1", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(job()),
    }),
  );
  await page.goto("/jobs/recover-1");
  await expect(page.getByRole("alert")).toContainText("Proces bol prerušený.");
  recovered = true;
  await expect(
    page.getByRole("heading", { name: "Operácia dokončená" }),
  ).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("alert")).toHaveCount(0);
});
