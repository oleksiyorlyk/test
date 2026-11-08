import type { Execution } from "../../shared/api/types";
import { Badge } from "../../shared/ui/components";

export function Results({ execution }: { execution: Execution }) {
  const stats = [
    ["Úspešné", execution.passed, "green"],
    ["Neúspešné", execution.failed, "red"],
    ["Čas vypršal", execution.timed_out, "amber"],
    [
      "Ostatné",
      execution.total -
        execution.passed -
        execution.failed -
        execution.timed_out,
      "neutral",
    ],
  ];
  return (
    <>
      <div className="result-stats">
        {stats.map(([label, value, color]) => (
          <div className={`result-stat ${color}`} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Test / kritérium</th>
              <th>Výsledok</th>
              <th>Trvanie</th>
              <th>Pokusy</th>
            </tr>
          </thead>
          <tbody>
            {execution.tests.map((test) => (
              <tr key={test.test_id}>
                <td>
                  <strong>{test.test_id}</strong>
                  <small>
                    {test.acceptance_criterion_id} ·{" "}
                    {test.title.replace(/^TC-\d+\s*\|\s*/, "")}
                  </small>
                  {test.failure && (
                    <details className="failure-detail">
                      <summary>Podrobnosti zlyhania</summary>
                      <p>{test.failure.message}</p>
                      {test.failure.expected != null && (
                        <pre>
                          Očakávané: {test.failure.expected}
                          {"\n"}Získané: {test.failure.received}
                        </pre>
                      )}
                    </details>
                  )}
                </td>
                <td>
                  <Badge status={test.status} />
                </td>
                <td>{(test.duration_ms / 1000).toFixed(1)} s</td>
                <td>{test.attempts ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
