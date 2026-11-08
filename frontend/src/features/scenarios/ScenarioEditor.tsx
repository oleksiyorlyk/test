import { useUnsavedChanges } from "./useUnsavedChanges";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  Play,
  Plus,
  RotateCcw,
  Save,
  ShieldCheck,
} from "lucide-react";
import { ScenarioFilters } from "./ScenarioFilters";
import { ApiError, api } from "../../shared/api/client";
import type { Batch, Review } from "../../shared/api/types";
import { nextTestId, validateBatch } from "./validation";
import { ScenarioCard } from "./ScenarioCard";
import { Badge, Empty, ErrorBox } from "../../shared/ui/components";

export function ScenarioEditor({
  review,
  busy,
  onSaved,
  onGenerate,
  onApprove,
}: {
  review: Review;
  busy: boolean;
  onSaved: (review: Review) => void;
  onGenerate: () => void;
  onApprove: () => void;
}) {
  const {
    register,
    control,
    watch,
    reset,
    setValue,
    handleSubmit,
    formState: { isDirty },
  } = useForm<Batch>({ defaultValues: review.draft, disabled: busy });
  const { fields, append, remove } = useFieldArray({
    control,
    name: "scenarios",
  });
  const scenarios = watch("scenarios");
  const [criterion, setCriterion] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");
  const [localErrors, setLocalErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const { blocker, dialogRef } = useUnsavedChanges(isDirty);
  const save = useMutation({
    mutationFn: (draft: Batch) =>
      api<Review>(`/stories/${review.story_id}/review`, {
        method: "PUT",
        body: JSON.stringify({ draft, review_hash: review.review_hash }),
      }),
    onSuccess: (value) => {
      reset(value.draft);
      setLocalErrors([]);
      setSaved(true);
      onSaved(value);
    },
  });
  const reload = useMutation({
    mutationFn: () => api<Review>(`/stories/${review.story_id}/review`),
    onSuccess: (value) => {
      reset(value.draft);
      setLocalErrors([]);
      save.reset();
      onSaved(value);
    },
  });
  const submit = handleSubmit((data) => {
    setSaved(false);
    const errors = validateBatch(data, review.story);
    setLocalErrors(errors);
    if (!errors.length) save.mutate(data);
  });
  const ready = scenarios.filter((s) => s.status === "READY").length;
  const add = () => {
    append({
      test_id: nextTestId(scenarios),
      title: "",
      acceptance_criterion_id:
        criterion || review.story.acceptance_criteria[0]?.id || "",
      evidence_quote: "",
      test_type: "positive",
      preconditions: [],
      test_data: [],
      actions: [],
      expected_results: [],
      status: "READY",
      blocked_reason: null,
    });
    setStatus("");
    setType("");
    setSearch("");
    setSaved(false);
  };
  return (
    <form onSubmit={submit} className="editor">
      <div className="review-meta">
        <div>
          <ShieldCheck size={19} />
          <strong>Kontrola pred spustením</strong>
          <span>Revízia {review.revision}</span>
        </div>
        <div>
          <Badge status="READY" /> {ready}
          <Badge status="BLOCKED" /> {scenarios.length - ready}
        </div>
      </div>
      <ErrorBox error={save.error || reload.error} />
      {save.error instanceof ApiError && save.error.code === "STALE_REVIEW" && (
        <button
          type="button"
          className="button button-secondary"
          disabled={reload.isPending}
          onClick={() => {
            if (
              window.confirm(
                "Načítať aktuálny koncept a zahodiť lokálne úpravy?",
              )
            )
              reload.mutate();
          }}
        >
          Načítať aktuálny koncept
        </button>
      )}
      {!!localErrors.length && (
        <div className="alert alert-error" role="alert">
          <AlertTriangle size={20} />
          <div>
            <strong>Skontrolujte scenáre</strong>
            <ul>
              {localErrors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {review.validation.warnings.length > 0 && (
        <details className="validation-notes">
          <summary>
            Upozornenia validátora ({review.validation.warnings.length})
          </summary>
          <ul>
            {review.validation.warnings.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ul>
        </details>
      )}
      <div className="editor-grid">
        <aside className="criteria-panel">
          <p className="eyebrow">POKRYTIE POŽIADAVIEK</p>
          <h3>Akceptačné kritériá</h3>
          <button
            type="button"
            className={`criterion-button ${!criterion ? "selected" : ""}`}
            onClick={() => setCriterion("")}
          >
            Všetky kritériá <span>{scenarios.length}</span>
          </button>
          {review.story.acceptance_criteria.map((ac) => {
            const count = scenarios.filter(
              (s) => s.acceptance_criterion_id === ac.id,
            ).length;
            return (
              <button
                type="button"
                className={`criterion-button ${criterion === ac.id ? "selected" : ""}`}
                key={ac.id}
                onClick={() => setCriterion(ac.id)}
              >
                <span className="criterion-top">
                  <b>{ac.id}</b>
                  <span className={count ? "text-green" : "text-red"}>
                    {count ? <Check size={14} /> : <AlertTriangle size={14} />}{" "}
                    {count} scenárov
                  </span>
                </span>
                <p>{ac.text}</p>
              </button>
            );
          })}
        </aside>
        <div className="scenario-column">
          <ScenarioFilters
            {...{ search, status, type, setSearch, setStatus, setType }}
          />
          {fields.map((field, index) => {
            const scenario = scenarios[index];
            const hidden = !!(
              (criterion && criterion !== scenario.acceptance_criterion_id) ||
              (status && status !== scenario.status) ||
              (type && type !== scenario.test_type) ||
              (search &&
                !`${scenario.test_id} ${scenario.title}`
                  .toLowerCase()
                  .includes(search.toLowerCase()))
            );
            const errors = localErrors.filter((e) =>
              e.startsWith(scenario.test_id + ":"),
            );
            return (
              <ScenarioCard
                key={field.id}
                {...{
                  field,
                  scenario,
                  index,
                  errors,
                  hidden,
                  review,
                  busy,
                  register,
                  setValue,
                  control,
                  remove,
                }}
              />
            );
          })}
          {!fields.length && <Empty title="Koncept neobsahuje scenáre" />}
          <button
            type="button"
            className="add-scenario"
            onClick={add}
            disabled={busy}
          >
            <Plus size={18} /> Pridať scenár
          </button>
        </div>
      </div>
      <div className="editor-actions">
        <div>
          <span className={`status-dot ${isDirty ? "unsaved" : "online"}`} />
          {isDirty
            ? "Neuložené zmeny"
            : saved
              ? "Zmeny boli uložené"
              : "Koncept pripravený na kontrolu"}
        </div>
        <div>
          <button
            className="button button-secondary"
            type="button"
            disabled={busy || save.isPending}
            onClick={() => {
              if (
                window.confirm(
                  "Generovať scenáre znova? Aktuálny koncept aj neuložené úpravy sa nahradia.",
                )
              ) {
                reset(review.draft);
                onGenerate();
              }
            }}
          >
            <RotateCcw size={16} />
            Generovať znova
          </button>
          <button
            type="submit"
            className="button button-secondary"
            disabled={!isDirty || busy || save.isPending}
          >
            <Save size={16} />
            {save.isPending ? "Ukladám…" : "Uložiť zmeny"}
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={
              isDirty ||
              busy ||
              save.isPending ||
              !ready ||
              !review.validation.valid
            }
            onClick={onApprove}
          >
            <Play size={16} />
            Schváliť a spustiť
          </button>
        </div>
      </div>
      {blocker.state === "blocked" && (
        <div className="modal-overlay">
          <div
            ref={dialogRef}
            onKeyDown={(event) => {
              if (event.key === "Escape") blocker.reset?.();
              if (event.key === "Tab") {
                const buttons = event.currentTarget.querySelectorAll("button");
                const first = buttons[0],
                  last = buttons[buttons.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                  event.preventDefault();
                  last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                  event.preventDefault();
                  first.focus();
                }
              }
            }}
            className="confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="leave-title"
          >
            <AlertTriangle size={28} />
            <h2 id="leave-title">Máte neuložené zmeny</h2>
            <p>Ak odídete, úpravy konceptu sa stratia.</p>
            <div>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => blocker.reset()}
              >
                Zostať
              </button>
              <button
                className="button button-primary"
                type="button"
                onClick={() => blocker.proceed()}
              >
                Zahodiť a odísť
              </button>
            </div>
          </div>
        </div>
      )}
    </form>
  );
}
