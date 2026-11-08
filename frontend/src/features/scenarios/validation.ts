import type { Batch, Scenario, Story } from "../../shared/api/types";

export function nextTestId(scenarios: Scenario[]) {
  const ids = new Set(scenarios.map((s) => s.test_id));
  let index = 1;
  while (ids.has(`TC-${String(index).padStart(3, "0")}`)) index++;
  return `TC-${String(index).padStart(3, "0")}`;
}

export function validateBatch(batch: Batch, story: Story): string[] {
  const errors: string[] = [];
  const ids = new Set<string>();
  if (!batch.scenarios.length) errors.push("Pridajte aspoň jeden scenár.");
  for (const s of batch.scenarios) {
    const prefix = `${s.test_id}: `;
    if (!/^TC-\d{3,6}$/.test(s.test_id) || ids.has(s.test_id))
      errors.push(prefix + "ID musí byť jedinečné vo formáte TC-001.");
    ids.add(s.test_id);
    if (!s.title.trim()) errors.push(prefix + "Doplňte názov.");
    const ac = story.acceptance_criteria.find(
      (ac) => ac.id === s.acceptance_criterion_id,
    );
    const clean = (v: string) => v.replace(/\s+/g, " ").trim();
    if (!ac) errors.push(prefix + "Vyberte platné akceptačné kritérium.");
    else if (
      clean(s.evidence_quote).length < 20 ||
      !clean(ac.text).includes(clean(s.evidence_quote))
    )
      errors.push(
        prefix + "Citácia musí byť presným úryvkom kritéria s aspoň 20 znakmi.",
      );
    if (
      s.status === "READY" &&
      (!s.actions.some((v) => v.trim()) ||
        !s.expected_results.some((v) => v.trim()))
    )
      errors.push(
        prefix + "Pripravený scenár potrebuje kroky aj očakávané výsledky.",
      );
    if (s.status === "BLOCKED" && !s.blocked_reason?.trim())
      errors.push(prefix + "Uveďte dôvod blokovania.");
  }
  for (const ac of story.acceptance_criteria)
    if (!batch.scenarios.some((s) => s.acceptance_criterion_id === ac.id))
      errors.push(`Kritérium ${ac.id} nemá scenár.`);
  return errors;
}
