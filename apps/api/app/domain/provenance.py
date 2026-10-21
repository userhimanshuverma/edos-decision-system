from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProvenanceStage(str, Enum):
    """Execution pipeline stage in the provenance lifecycle.

    Adheres strictly to the core pipeline:
    Input -> Rule -> Calculation -> Result.
    """

    INPUT = "INPUT"
    RULE = "RULE"
    CALCULATION = "CALCULATION"
    RESULT = "RESULT"


class ProvenanceStepStatus(str, Enum):
    """Deterministic status of an individual provenance step.

    Distinguishes:
    - SUCCESS: Step executed or observed successfully.
    - FAILED: Step execution raised an error or exception.
    - MISSING: Prerequisite operational entity or context was not found.
    - UNAVAILABLE: Metric or input cannot be defensibly calculated or observed.
    - SKIPPED: Step was bypassed due to upstream condition or eligibility.
    """

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"
    SKIPPED = "SKIPPED"


class ProvenanceInputType(str, Enum):
    """Categorical nature of an operational input."""

    PRODUCT = "PRODUCT"
    WAREHOUSE = "WAREHOUSE"
    INVENTORY = "INVENTORY"
    DEMAND = "DEMAND"
    SUPPLIER = "SUPPLIER"
    CANDIDATE_ACTION = "CANDIDATE_ACTION"
    ASSUMPTION = "ASSUMPTION"
    CONTEXT_SNAPSHOT = "CONTEXT_SNAPSHOT"
    DECISION_VERSION = "DECISION_VERSION"


class ProvenanceRuleType(str, Enum):
    """Category of operational or policy rule evaluated."""

    REPLENISHMENT_POLICY = "REPLENISHMENT_POLICY"
    CONSTRAINT_CHECK = "CONSTRAINT_CHECK"
    SELECTION_STRATEGY = "SELECTION_STRATEGY"
    TIE_BREAKER = "TIE_BREAKER"


class ProvenanceCalculationType(str, Enum):
    """Category of deterministic mathematical calculation executed."""

    REPLENISHMENT_QUANTITY = "REPLENISHMENT_QUANTITY"
    STOCKOUT_EXPOSURE = "STOCKOUT_EXPOSURE"
    RUNWAY_COVERAGE = "RUNWAY_COVERAGE"
    SUPPLIER_RISK = "SUPPLIER_RISK"
    COST_IMPACT = "COST_IMPACT"
    ACTION_SCORING = "ACTION_SCORING"


class ProvenanceResultType(str, Enum):
    """Category of decision result output produced."""

    ACTION_EVALUATION = "ACTION_EVALUATION"
    VALIDATION_REPORT = "VALIDATION_REPORT"
    RECOMMENDATION = "RECOMMENDATION"
    EVIDENCE_SHEET = "EVIDENCE_SHEET"


class ProvenanceLineageEdge(BaseModel):
    """Directed relationship link connecting steps in the provenance pipeline.

    Connects:
    - INPUT -> RULE (e.g. inventory & reorder point feed into replenishment policy rule)
    - INPUT -> CALCULATION (e.g. demand & lead time feed into stockout exposure calculation)
    - RULE -> CALCULATION (e.g. reorder trigger rule initiates replenishment quantity calculation)
    - CALCULATION -> RESULT (e.g. exposure delta feeds into action evaluation result)
    - RULE -> RESULT (e.g. lexicographic dominance rule produces final recommendation)
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(..., min_length=1, description="Source provenance step identifier")
    target_id: str = Field(..., min_length=1, description="Target provenance step identifier")
    relationship: str = Field(
        ...,
        min_length=1,
        description="Semantic relationship type (e.g. FEEDS_INTO, APPLIES_RULE, PRODUCES, DERIVED_FROM)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary edge metadata")

    @field_validator("source_id", "target_id", "relationship")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace-only")
        return trimmed

    @model_validator(mode="after")
    def validate_no_self_loop(self) -> ProvenanceLineageEdge:
        if self.source_id == self.target_id:
            raise ValueError(
                f"Self-loop lineage edge not permitted: source_id and target_id are both '{self.source_id}'"
            )
        return self


class ProvenanceInputRecord(BaseModel):
    """Strongly typed provenance record for an operational input.

    Captures ground truth operational inputs, catalog attributes, inventory positions,
    and explicit assumptions.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique input step identifier (INP-XXXX)")
    input_type: ProvenanceInputType = Field(..., description="Categorical nature of input")
    source_id: str = Field(..., min_length=1, description="Originating domain entity identifier (e.g. prod-001, wh-001)")
    name: str = Field(..., min_length=1, description="Human-readable label for this input")
    value: Any | None = Field(default=None, description="Observed or assumed input value")
    unit: str | None = Field(default=None, description="Measurement unit (e.g. units, days, USD)")
    status: ProvenanceStepStatus = Field(
        default=ProvenanceStepStatus.SUCCESS,
        description="Observation status (SUCCESS, MISSING, UNAVAILABLE)",
    )
    evidence_id: str | None = Field(
        default=None,
        description="Optional cross-reference to Day 22 DecisionEvidence (EVD-XXXX) or DecisionAssumption (ASM-XXXX)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @field_validator("id", "source_id", "name")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace-only")
        return trimmed


class ProvenanceRuleRecord(BaseModel):
    """Strongly typed provenance record for an operational rule or policy evaluation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique rule step identifier (RUL-XXXX)")
    rule_type: ProvenanceRuleType = Field(..., description="Category of rule evaluated")
    rule_name: str = Field(..., min_length=1, description="Standard identifier or name of the rule")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-scoped")
    inputs_considered: list[str] = Field(
        default_factory=list,
        description="Identifiers of input steps (INP-XXXX) or domain sources evaluated by this rule",
    )
    status: ProvenanceStepStatus = Field(
        default=ProvenanceStepStatus.SUCCESS,
        description="Rule evaluation status (SUCCESS, FAILED, UNAVAILABLE, SKIPPED)",
    )
    condition_met: bool | None = Field(
        default=None,
        description="True if rule trigger/condition was satisfied, False otherwise, None if un-evaluated",
    )
    outcome: str = Field(..., min_length=1, description="Rule evaluation outcome description (e.g. PASS, FAIL, TRIGGERED)")
    validation_report_id: str | None = Field(
        default=None,
        description="Optional cross-reference to DecisionValidationReport (VAL-XXXX)",
    )
    notes: list[str] = Field(default_factory=list, description="Step-by-step rule evaluation rationale")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @field_validator("id", "rule_name", "outcome")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace-only")
        return trimmed


class ProvenanceCalculationRecord(BaseModel):
    """Strongly typed provenance record for a deterministic mathematical calculation.

    Guarantees:
    - Never fabricates a calculation that did not run.
    - Explicitly captures formula applied, inputs used, status, and output.
    - Distinguishes missing/unavailable calculations from successful ones.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique calculation step identifier (CLC-XXXX)")
    calculation_type: ProvenanceCalculationType = Field(..., description="Category of mathematical derivation")
    calculation_name: str = Field(..., min_length=1, description="Descriptive name of the calculation")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-specific")
    formula: str | None = Field(default=None, description="Human-readable mathematical expression or policy formula")
    inputs_used: list[str] = Field(
        default_factory=list,
        description="Identifiers of input steps (INP-XXXX) used in the derivation",
    )
    rules_applied: list[str] = Field(
        default_factory=list,
        description="Identifiers of rule steps (RUL-XXXX) that governed this calculation",
    )
    status: ProvenanceStepStatus = Field(
        default=ProvenanceStepStatus.SUCCESS,
        description="Calculation status (SUCCESS, FAILED, UNAVAILABLE, SKIPPED)",
    )
    output_value: Any | None = Field(default=None, description="Calculated metric, value, or structured outcome")
    unit: str | None = Field(default=None, description="Unit of measurement (e.g. units, days, USD, ratio)")
    error_message: str | None = Field(default=None, description="Error message if calculation failed")
    evidence_id: str | None = Field(
        default=None,
        description="Optional cross-reference to Day 22 DecisionEvidence (EVD-XXXX)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @field_validator("id", "calculation_name")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace-only")
        return trimmed


class ProvenanceResultRecord(BaseModel):
    """Strongly typed provenance record for an evaluation or decision outcome.

    Connects downstream results directly to the calculations and rules that produced them.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique result step identifier (RES-XXXX)")
    result_type: ProvenanceResultType = Field(..., description="Category of decision result")
    result_id: str = Field(..., min_length=1, description="Domain identifier of the result (e.g. ACT-0001, REC-0001, VAL-0001)")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-scoped")
    status: ProvenanceStepStatus = Field(
        default=ProvenanceStepStatus.SUCCESS,
        description="Result derivation status (SUCCESS, FAILED, UNAVAILABLE)",
    )
    outcome_status: str = Field(..., min_length=1, description="Domain status (e.g. RECOMMENDED, VALID, NO_ACTION_REQUIRED)")
    summary: str = Field(..., min_length=1, description="Concise human-readable explanation of the result")
    calculations_used: list[str] = Field(
        default_factory=list,
        description="Identifiers of calculation steps (CLC-XXXX) feeding this result",
    )
    rules_applied: list[str] = Field(
        default_factory=list,
        description="Identifiers of rule steps (RUL-XXXX) governing this result",
    )
    value: Any | None = Field(default=None, description="Structured outcome payload or primary score")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @field_validator("id", "result_id", "outcome_status", "summary")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace-only")
        return trimmed


class ProvenanceDerivationChain(BaseModel):
    """Extracted upstream derivation chain for a specific result step.

    Traces: Result <- Calculations <- Rules <- Inputs.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    result: ProvenanceResultRecord = Field(..., description="Target result step being traced")
    calculations: list[ProvenanceCalculationRecord] = Field(default_factory=list, description="Direct upstream calculations")
    rules: list[ProvenanceRuleRecord] = Field(default_factory=list, description="Direct upstream rules evaluated")
    inputs: list[ProvenanceInputRecord] = Field(default_factory=list, description="Grounding operational inputs")
    lineage_edges: list[ProvenanceLineageEdge] = Field(default_factory=list, description="Directed lineage path edges")


class DecisionProvenanceTrace(BaseModel):
    """Consolidated, auditable provenance trace for a business decision execution.

    Records the exact derivation pipeline:
    Input -> Rule -> Calculation -> Result.

    Guarantees:
    - Decision and Version isolation: strictly bound to a decision (and optional version).
    - Disambiguated execution tracking: distinct execution_id per run.
    - Deterministic ordering: steps indexed and sorted predictably.
    - Zero fabricated calculations: missing data explicitly recorded as MISSING/UNAVAILABLE.
    - Graph lineage consistency: semantic alignment with Decision Graph.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique provenance trace identifier (PRV-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier (DEC-XXXX)")
    version_id: str | None = Field(default=None, description="Optional associated decision version identifier (VER-XXXX)")
    execution_id: str = Field(..., min_length=1, description="Unique execution identifier distinguishing repeated evaluations")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the trace was captured",
    )
    trigger: str = Field(
        default="RECOMMENDATION",
        description="Execution trigger: RECOMMENDATION, EVALUATION, VALIDATION, EVIDENCE_COMPILATION",
    )
    status: ProvenanceStepStatus = Field(
        default=ProvenanceStepStatus.SUCCESS,
        description="Overall execution status: SUCCESS, FAILED, or UNAVAILABLE",
    )
    inputs: list[ProvenanceInputRecord] = Field(default_factory=list, description="Recorded operational inputs")
    rules: list[ProvenanceRuleRecord] = Field(default_factory=list, description="Recorded policy and constraint rules")
    calculations: list[ProvenanceCalculationRecord] = Field(default_factory=list, description="Recorded calculations")
    results: list[ProvenanceResultRecord] = Field(default_factory=list, description="Recorded outputs and recommendations")
    lineage_edges: list[ProvenanceLineageEdge] = Field(default_factory=list, description="Directed lineage connections")
    graph_id: str | None = Field(default=None, description="Optional linked Decision Graph identifier (GRA-XXXX)")
    summary: dict[str, Any] = Field(default_factory=dict, description="Summary statistics and execution counts")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @field_validator("id", "decision_id", "execution_id")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace-only")
        return trimmed

    @field_validator("version_id")
    @classmethod
    def validate_optional_id(cls, value: str | None) -> str | None:
        if value is not None:
            trimmed = value.strip()
            if not trimmed:
                return None
            return trimmed
        return None

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_trace_integrity(self) -> DecisionProvenanceTrace:
        """Validates trace internal consistency and builds summary statistics."""
        input_ids = {item.id for item in self.inputs}
        rule_ids = {item.id for item in self.rules}
        calc_ids = {item.id for item in self.calculations}
        result_ids = {item.id for item in self.results}

        all_ids = input_ids | rule_ids | calc_ids | result_ids
        expected_count = len(self.inputs) + len(self.rules) + len(self.calculations) + len(self.results)
        if len(all_ids) != expected_count:
            raise ValueError("Provenance step identifiers within a trace must be globally unique")

        # Check edge endpoint references
        for edge in self.lineage_edges:
            if edge.source_id not in all_ids:
                raise ValueError(f"Lineage edge references unknown source step '{edge.source_id}'")
            if edge.target_id not in all_ids:
                raise ValueError(f"Lineage edge references unknown target step '{edge.target_id}'")

        has_failures = any(
            s.status == ProvenanceStepStatus.FAILED
            for container in (self.inputs, self.rules, self.calculations, self.results)
            for s in container
        )
        has_missing = any(
            s.status == ProvenanceStepStatus.MISSING
            for container in (self.inputs, self.rules, self.calculations, self.results)
            for s in container
        )

        # Invariant: Trace status must reflect partial/failed executions honestly
        if has_failures and self.status == ProvenanceStepStatus.SUCCESS:
            self.status = ProvenanceStepStatus.FAILED

        # Auto-compute summary counts if missing
        if not self.summary:
            actions_traced = sorted(
                list(
                    {
                        getattr(item, "action_id", None)
                        for container in (self.rules, self.calculations, self.results)
                        for item in container
                        if getattr(item, "action_id", None) is not None
                    }
                )
            )
            self.summary = {
                "total_inputs": len(self.inputs),
                "total_rules": len(self.rules),
                "total_calculations": len(self.calculations),
                "total_results": len(self.results),
                "total_edges": len(self.lineage_edges),
                "actions_traced": actions_traced,
                "has_failures": has_failures,
                "has_missing": has_missing,
            }

        return self

    def get_derivation_path(self, result_id: str | None = None) -> ProvenanceDerivationChain:
        """Extracts the exact upstream chain (Result <- Calculations <- Rules <- Inputs) for a result.

        If result_id is None, selects the primary result (first RECOMMENDATION or first result in trace).
        Raises ValueError if result_id is not found.
        """
        target_res: ProvenanceResultRecord | None = None
        if result_id is not None:
            norm_res_id = result_id.strip()
            target_res = next((r for r in self.results if r.id == norm_res_id or r.result_id == norm_res_id), None)
            if target_res is None:
                raise ValueError(f"Result step with identifier '{result_id}' not found in trace '{self.id}'")
        else:
            # Default to recommendation result, or the first result
            target_res = next((r for r in self.results if r.result_type == ProvenanceResultType.RECOMMENDATION), None)
            if target_res is None and self.results:
                target_res = self.results[0]
            if target_res is None:
                raise ValueError(f"No results available in trace '{self.id}'")

        # Build lookup maps
        input_map = {inp.id: inp for inp in self.inputs}
        rule_map = {r.id: r for r in self.rules}
        calc_map = {c.id: c for c in self.calculations}
        result_map = {res.id: res for res in self.results}
        all_ids = set(input_map.keys()) | set(rule_map.keys()) | set(calc_map.keys()) | set(result_map.keys())

        # Collect upstream step IDs via backward BFS traversal over lineage_edges and explicit references
        visited_ids: set[str] = {target_res.id}
        queue: list[str] = [target_res.id]

        incoming_edges: dict[str, list[ProvenanceLineageEdge]] = {}
        for edge in self.lineage_edges:
            incoming_edges.setdefault(edge.target_id, []).append(edge)

        while queue:
            curr_id = queue.pop(0)

            # Traverse direct incoming lineage edges
            for edge in incoming_edges.get(curr_id, []):
                src = edge.source_id
                if src not in visited_ids:
                    visited_ids.add(src)
                    queue.append(src)

            # Also check explicit references from calculations, rules, and results
            if curr_id in calc_map:
                c = calc_map[curr_id]
                for ref_id in (*c.inputs_used, *c.rules_applied):
                    if ref_id in all_ids and ref_id not in visited_ids:
                        visited_ids.add(ref_id)
                        queue.append(ref_id)

            if curr_id in rule_map:
                r = rule_map[curr_id]
                for ref_id in r.inputs_considered:
                    if ref_id in all_ids and ref_id not in visited_ids:
                        visited_ids.add(ref_id)
                        queue.append(ref_id)

            if curr_id in result_map:
                res = result_map[curr_id]
                for ref_id in (*res.calculations_used, *res.rules_applied):
                    if ref_id in all_ids and ref_id not in visited_ids:
                        visited_ids.add(ref_id)
                        queue.append(ref_id)

        relevant_calcs = [c for c in self.calculations if c.id in visited_ids]
        relevant_rules = [r for r in self.rules if r.id in visited_ids]
        relevant_inputs = [inp for inp in self.inputs if inp.id in visited_ids]

        relevant_edges = [
            edge
            for edge in self.lineage_edges
            if edge.source_id in visited_ids and edge.target_id in visited_ids
        ]

        return ProvenanceDerivationChain(
            result=target_res,
            calculations=relevant_calcs,
            rules=relevant_rules,
            inputs=relevant_inputs,
            lineage_edges=relevant_edges,
        )
