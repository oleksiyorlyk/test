import type { components } from "./generated";

// Public aliases derive from the backend schema; do not duplicate wire fields.
export type Criterion = components["schemas"]["Criterion"];
export type Story = components["schemas"]["Story"];
export type Scenario = components["schemas"]["TestScenario"];
export type Batch = components["schemas"]["ScenarioBatch"];
export type Validation = components["schemas"]["Validation"];
export type Review = components["schemas"]["Review"];
export type StoryRow = components["schemas"]["StoryRow"];
export type Catalog = components["schemas"]["Catalog"];
export type TestResult = components["schemas"]["TestResult"];
export type Execution = components["schemas"]["Execution"];
export type JobResult = components["schemas"]["JobResult"];
export type Artifact = components["schemas"]["Artifact"];
export type Job = components["schemas"]["Job"];
export type Health = components["schemas"]["Health"];
