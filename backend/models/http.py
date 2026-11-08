"""Public wire models. Preserve extension metadata and omitted optional fields."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.models.scenarios import ScenarioBatch


class WireModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Criterion(WireModel):
    id: str
    text: str
    source_label: str | None = None


class StorySource(WireModel):
    url: str | None = None


class Story(WireModel):
    id: int
    revision: int
    title: str
    description: str
    acceptance_criteria: list[Criterion]
    ready_for_llm: bool
    warnings: list[str]
    unparsed_acceptance_criteria: str | None = None
    source: StorySource | None = None


class Validation(WireModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
    coverage: dict[str, list[str]]
    scenario_count: int
    ready_count: int
    blocked_count: int


class Review(WireModel):
    story_id: int
    revision: int
    status: str
    story: Story
    draft: ScenarioBatch
    validation: Validation
    review_hash: str


class EditRequest(BaseModel):
    draft: dict[str, Any]
    review_hash: str = Field(min_length=1)


class ApproveRequest(BaseModel):
    review_hash: str = Field(min_length=1)
    revision: int = Field(gt=0)


class StoryRow(WireModel):
    id: int
    title: str
    state: str
    assigned_to: str
    changed_at: str


class Catalog(WireModel):
    items: list[StoryRow]
    total: int
    states: list[str]
    page: int
    page_size: int


class Failure(WireModel):
    type: str
    message: str
    expected: str | None = None
    received: str | None = None


class TestResult(WireModel):
    test_id: str
    acceptance_criterion_id: str
    title: str
    status: str
    duration_ms: int
    attempts: int | None = None
    failure: Failure | None = None


class Execution(WireModel):
    total: int
    passed: int
    failed: int
    timed_out: int
    flaky: int
    skipped: int
    not_run: int
    interrupted: int
    unknown: int
    tests: list[TestResult]


class DevopsResult(WireModel):
    test_cases: dict[str, int]
    test_case_actions: dict[str, str] | None = None
    blocked: list[str] | None = None


class JobResult(WireModel):
    execution: Execution | None = None
    devops: DevopsResult | None = None
    publication: str | None = None
    result_uploads: dict[str, Any] | None = None
    draft: ScenarioBatch | None = None
    story: Story | None = None
    validation: Validation | None = None
    review_hash: str | None = None
    revision: int | None = None
    status: str | None = None


class Artifact(WireModel):
    id: str
    name: str
    size: int


class JobError(WireModel):
    code: str
    message: str
    details: str | None = None


class Job(WireModel):
    id: str
    story_id: int
    kind: Literal["GENERATE", "EXECUTE"]
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "INTERRUPTED"]
    created_at: str
    updated_at: str
    revision: int | None
    result: JobResult | None
    error: JobError | None
    artifacts: list[Artifact]
    log: str | None = None


class JobList(WireModel):
    items: list[Job]


class JobStarted(WireModel):
    job_id: str
    status: Literal["QUEUED"]


class Health(WireModel):
    organization: str
    project: str
    checks: dict[str, bool]
    mode: str


class ErrorResponse(BaseModel):
    error: JobError
