import type { UseFormReturn } from "react-hook-form";
import type { Batch, Review, Scenario } from "../../shared/api/types";
import { Trash2 } from "lucide-react";
import { Badge } from "../../shared/ui/components";
import { Lines } from "./Lines";

type Props = Pick<UseFormReturn<Batch>, "register" | "setValue" | "control"> & {
  field: { id: string; title: string };
  scenario: Scenario;
  index: number;
  errors: string[];
  hidden: boolean;
  review: Review;
  busy: boolean;
  remove: (index: number) => void;
};
export function ScenarioCard({
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
}: Props) {
  return (
    <details
      className="scenario-card"
      open={index === 0 || !field.title || errors.length > 0}
      hidden={hidden}
    >
      <summary>
        <span className="scenario-number">{scenario.test_id}</span>
        <span className="scenario-name">{scenario.title || "Nový scenár"}</span>
        <Badge status={scenario.status} />
      </summary>
      <div className="scenario-body">
        <div className="form-grid">
          <label>
            ID scenára
            <input
              {...register(`scenarios.${index}.test_id`)}
              required
              pattern="TC-[0-9]{3,6}"
            />
          </label>
          <label>
            Akceptačné kritérium
            <select {...register(`scenarios.${index}.acceptance_criterion_id`)}>
              {review.story.acceptance_criteria.map((ac) => (
                <option key={ac.id}>{ac.id}</option>
              ))}
            </select>
          </label>
          <label className="span-two">
            Názov scenára
            <input {...register(`scenarios.${index}.title`)} required />
          </label>
          <label>
            Typ testu
            <select {...register(`scenarios.${index}.test_type`)}>
              <option value="positive">Pozitívny</option>
              <option value="negative">Negatívny</option>
              <option value="boundary">Hraničný</option>
            </select>
          </label>
          <label>
            Stav
            <select
              {...register(`scenarios.${index}.status`, {
                onChange: (event) => {
                  if (event.target.value === "READY")
                    setValue(`scenarios.${index}.blocked_reason`, null, {
                      shouldDirty: true,
                    });
                },
              })}
            >
              <option value="READY">Pripravený</option>
              <option value="BLOCKED">Zablokovaný</option>
            </select>
          </label>
          <label className="span-two">
            Citácia z akceptačného kritéria
            <textarea
              {...register(`scenarios.${index}.evidence_quote`)}
              rows={2}
              required
            />
            <small>Presný úryvok s minimálne 20 znakmi.</small>
          </label>
          {scenario.status === "BLOCKED" && (
            <label className="span-two">
              Dôvod blokovania
              <textarea
                {...register(`scenarios.${index}.blocked_reason`)}
                required
                rows={2}
              />
            </label>
          )}
          {(
            [
              ["preconditions", "Predpoklady"],
              ["test_data", "Testovacie dáta"],
              ["actions", "Kroky"],
              ["expected_results", "Očakávané výsledky"],
            ] as const
          ).map(([key, label]) => (
            <Lines
              key={key}
              control={control}
              name={`scenarios.${index}.${key}`}
              label={label}
            />
          ))}
        </div>
        {errors.map((text) => (
          <p className="text-red" key={text}>
            {text}
          </p>
        ))}
        <button
          type="button"
          className="text-button danger"
          disabled={busy}
          onClick={() => {
            if (window.confirm(`Odstrániť scenár ${scenario.test_id}?`))
              remove(index);
          }}
        >
          <Trash2 size={15} /> Odstrániť scenár
        </button>
      </div>
    </details>
  );
}
