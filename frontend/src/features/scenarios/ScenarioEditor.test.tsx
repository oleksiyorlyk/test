import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { ScenarioEditor } from "./ScenarioEditor";
import { nextTestId, validateBatch } from "./validation";
import { Results } from "../results/Results";
import type { Review, Scenario } from "../../shared/api/types";

const criterion = "Correct credentials open the workspace.";
const scenario: Scenario = {
  test_id: "TC-001",
  title: "Successful login",
  acceptance_criterion_id: "AC1",
  evidence_quote: criterion,
  test_type: "positive",
  preconditions: ["User exists"],
  test_data: [],
  actions: ["Submit credentials"],
  expected_results: ["Workspace is visible"],
  status: "READY",
  blocked_reason: null,
};
const review: Review = {
  story_id: 1,
  revision: 1,
  status: "PENDING_REVIEW",
  review_hash: "original",
  story: {
    id: 1,
    revision: 1,
    title: "Login",
    description: "Sign in",
    ready_for_llm: true,
    warnings: [],
    acceptance_criteria: [{ id: "AC1", text: criterion }],
  },
  draft: { story_id: 1, scenarios: [scenario] },
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
function editor() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter([
    {
      path: "/",
      element: (
        <ScenarioEditor
          review={structuredClone(review)}
          busy={false}
          onSaved={vi.fn()}
          onGenerate={vi.fn()}
          onApprove={vi.fn()}
        />
      ),
    },
    { path: "/other", element: <p>Other</p> },
  ]);
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}
describe("scenario editing", () => {
  it("chooses the next free supported ID", () => {
    expect(nextTestId([scenario, { ...scenario, test_id: "TC-003" }])).toBe(
      "TC-002",
    );
  });
  it("validates coverage, quotes, blocked reasons and completeness", () => {
    expect(validateBatch(review.draft, review.story)).toEqual([]);
    expect(
      validateBatch(
        {
          story_id: 1,
          scenarios: [
            {
              ...scenario,
              evidence_quote: "wrong",
              status: "BLOCKED",
              blocked_reason: "",
            },
          ],
        },
        review.story,
      ),
    ).toHaveLength(2);
    expect(
      validateBatch({ story_id: 1, scenarios: [] }, review.story),
    ).toHaveLength(2);
  });
  it("disables approval while edits are unsaved", () => {
    editor();
    expect(
      screen.getByRole("button", { name: "Schváliť a spustiť" }),
    ).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Názov scenára"), {
      target: { value: "Updated" },
    });
    expect(
      screen.getByRole("button", { name: "Schváliť a spustiť" }),
    ).toBeDisabled();
    expect(screen.getByText("Neuložené zmeny")).toBeInTheDocument();
  });
  it("keeps user edits after a hash conflict", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "STALE_REVIEW", message: "Koncept sa zmenil." },
        }),
        { status: 409 },
      ),
    );
    editor();
    fireEvent.change(screen.getByLabelText("Názov scenára"), {
      target: { value: "My unsaved title" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Uložiť zmeny" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Koncept sa zmenil."),
    );
    expect(screen.getByLabelText("Názov scenára")).toHaveValue(
      "My unsaved title",
    );
    fetch.mockRestore();
  });
  it("blocks internal navigation when dirty", async () => {
    const router = editor();
    fireEvent.change(screen.getByLabelText("Názov scenára"), {
      target: { value: "Unsaved" },
    });
    await router.navigate("/other");
    expect(await screen.findByRole("alertdialog")).toHaveTextContent(
      "Máte neuložené zmeny",
    );
    fireEvent.click(screen.getByRole("button", { name: "Zostať" }));
    expect(screen.getByLabelText("Názov scenára")).toHaveValue("Unsaved");
  });
  it("shows failed tests independently of the workflow", () => {
    render(
      <Results
        execution={{
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
              title: "Requirement",
              status: "FAILED",
              duration_ms: 1000,
              attempts: 1,
              failure: {
                type: "ASSERTION_MISMATCH",
                message: "Expected workspace",
              },
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("Zlyhanie")).toBeInTheDocument();
    expect(screen.getByText("Podrobnosti zlyhania")).toBeInTheDocument();
  });
});
