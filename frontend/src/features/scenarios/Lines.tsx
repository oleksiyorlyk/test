import { Controller } from "react-hook-form";
import type { Control } from "react-hook-form";
import type { Batch } from "../../shared/api/types";

export function Lines({
  control,
  name,
  label,
}: {
  control: Control<Batch>;
  name: `scenarios.${number}.${"actions" | "expected_results" | "preconditions" | "test_data"}`;
  label: string;
}) {
  return (
    <label>
      {label}
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <textarea
            disabled={field.disabled}
            rows={3}
            value={field.value.join("\n")}
            onBlur={field.onBlur}
            ref={field.ref}
            onChange={(e) =>
              field.onChange(e.target.value ? e.target.value.split("\n") : [])
            }
            placeholder="Každú položku napíšte na nový riadok."
          />
        )}
      />
    </label>
  );
}
