/**
 * Decision operational lifecycle statuses matching Day 12 FastAPI DecisionStatus enum.
 */
export type DecisionStatus =
  | 'DRAFT'
  | 'CONTEXTUALIZING'
  | 'CONSTRUCTING'
  | 'VALIDATING'
  | 'EVALUATING'
  | 'READY';

/**
 * Business decision operational state representation matching Day 11/12 FastAPI schema.
 */
export interface DecisionRecord {
  id: string;
  decision_id: string;
  product_id: string;
  warehouse_id: string;
  created_at: string;
  status: DecisionStatus;
}

/**
 * Event types matching Day 13 FastAPI DecisionEventType enum.
 */
export type DecisionEventType = 'DECISION_CREATED' | 'LIFECYCLE_TRANSITION';

/**
 * Audit trail event record representation matching Day 13 FastAPI schema.
 */
export interface DecisionEventRecord {
  id: string;
  event_id: string;
  decision_id: string;
  event_type: DecisionEventType;
  from_status: DecisionStatus | null;
  to_status: DecisionStatus;
  occurred_at: string;
}

import type { DecisionContext } from './context';

/**
 * Decision snapshot operational state matching Day 14 FastAPI DecisionSnapshotResponse schema.
 */
export interface DecisionSnapshotRecord {
  decision_id: string;
  product_id: string;
  warehouse_id: string;
  status: DecisionStatus;
  decision_created_at: string;
  context: DecisionContext | null;
}

/**
 * Historical decision version representation matching Day 14 FastAPI DecisionVersionResponse schema.
 */
export interface DecisionVersionRecord {
  id: string;
  version_id: string;
  decision_id: string;
  version_number: number;
  created_at: string;
  snapshot: DecisionSnapshotRecord;
  description: string | null;
}

/**
 * Decision graph node types matching Day 15 FastAPI GraphNodeType enum.
 */
export type GraphNodeType =
  | 'CONTEXT'
  | 'DECISION_VERSION'
  | 'ACTION'
  | 'VALIDATION'
  | 'SCENARIO'
  | 'RESULT';

/**
 * Decision graph relationship types matching Day 15 FastAPI GraphRelationshipType enum.
 */
export type GraphRelationshipType =
  | 'GENERATES'
  | 'VALIDATES'
  | 'SIMULATES'
  | 'PRODUCES'
  | 'REFERENCES'
  | 'DEPENDS_ON'
  | 'DERIVED_FROM';

/**
 * Decision graph node representation matching Day 15 FastAPI GraphNodeResponse schema.
 */
export interface GraphNodeRecord {
  id: string;
  node_id: string;
  type: GraphNodeType;
  node_type: GraphNodeType;
  decision_id: string;
  label: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

/**
 * Decision graph directed edge representation matching Day 15 FastAPI GraphEdgeResponse schema.
 */
export interface GraphEdgeRecord {
  id: string;
  edge_id: string;
  source_id: string;
  target_id: string;
  relationship_type: GraphRelationshipType;
  decision_id: string | null;
  metadata: Record<string, unknown>;
}

/**
 * Decision graph connecting an operational decision with its stages and lineage,
 * matching Day 15 FastAPI DecisionGraphResponse schema.
 */
export interface DecisionGraphRecord {
  id: string;
  graph_id: string;
  decision_id: string;
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
  created_at: string;
  updated_at: string;
}

/**
 * Candidate action operational types matching Day 16 FastAPI ActionType enum.
 */
export type CandidateActionType = 'DO_NOTHING' | 'PLACE_ORDER' | 'SWITCH_SUPPLIER';

export type ActionType = CandidateActionType;

/**
 * Parameters for DO_NOTHING candidate action.
 */
export type DoNothingParameters = Record<string, never>;

/**
 * Parameters for PLACE_ORDER candidate action.
 */
export interface PlaceOrderParameters {
  quantity: number;
  order_quantity?: number;
}

/**
 * Parameters for SWITCH_SUPPLIER candidate action.
 */
export interface SwitchSupplierParameters {
  target_supplier_id: string;
  supplier_id?: string;
}

export type CandidateActionParameters =
  | DoNothingParameters
  | PlaceOrderParameters
  | SwitchSupplierParameters;

/**
 * Candidate action record matching Day 16 FastAPI CandidateActionResponse schema.
 */
export interface CandidateActionRecord {
  id: string;
  action_id: string;
  decision_id: string;
  type: CandidateActionType;
  action_type: CandidateActionType;
  parameters: CandidateActionParameters;
  created_at: string;
  description: string | null;
  metadata: Record<string, unknown>;
}

export type CandidateActionResponse = CandidateActionRecord;

/**
 * Payload contract for creating a candidate action.
 */
export interface CreateCandidateActionRequest {
  type?: CandidateActionType;
  action_type?: CandidateActionType;
  parameters?: Record<string, unknown>;
  description?: string | null;
}

/**
 * Payload contract for calculating replenishment for an existing decision.
 */
export interface DecisionReplenishmentRequest {
  policy_type?: import('./inventory').ReplenishmentPolicyType;
  target_stock?: number;
  supplier_id?: string;
  enforce_reorder_trigger?: boolean;
}

/**
 * Payload contract for calculating stockout risk for an existing decision.
 */
export interface DecisionStockoutRiskRequest {
  supplier_id?: string;
  model_type?: import('./inventory').StockoutRiskModelType;
}

/**
 * Categorical status of cost impact determination matching Day 19 EvaluationCostStatus enum.
 */
export type EvaluationCostStatus = 'CALCULATED' | 'ZERO_COST' | 'UNAVAILABLE';

/**
 * Stockout exposure evaluation metrics for a candidate action.
 */
export interface StockoutExposureEvaluation {
  is_probability: boolean;
  current_risk_level: import('./inventory').StockoutRiskLevel;
  current_exposure_index: number;
  current_exposure_deficit: number;
  current_buffer_days: number | null;
  projected_risk_level: import('./inventory').StockoutRiskLevel;
  projected_exposure_index: number;
  projected_exposure_deficit: number;
  projected_buffer_days: number | null;
  exposure_index_delta: number;
  is_stockout_prevented_in_lead_time: boolean;
  post_arrival_coverage_days: number | null;
  notes: string[];
}

/**
 * Replenishment shortfall impact evaluation metrics for a candidate action.
 */
export interface ReplenishmentImpactEvaluation {
  policy_type: import('./inventory').ReplenishmentPolicyType;
  target_stock: number;
  available_quantity: number;
  reorder_point: number;
  recommended_replenishment_quantity: number;
  is_replenishment_needed: boolean;
  action_order_quantity: number | null;
  shortfall_addressed: number;
  remaining_shortfall: number;
  excess_quantity: number;
  shortfall_satisfaction_ratio: number | null;
  notes: string[];
}

/**
 * Supplier, lead-time, and reliability parameters affected by an action.
 */
export interface SupplierImpactEvaluation {
  current_supplier_id: string;
  current_supplier_name: string;
  current_lead_time_days: number;
  current_reliability: number;
  current_supplier_risk: string;
  effective_supplier_id: string;
  effective_supplier_name: string;
  effective_lead_time_days: number;
  effective_reliability: number;
  effective_supplier_risk: string;
  is_supplier_switched: boolean;
  lead_time_delta_days: number;
  reliability_delta: number;
  notes: string[];
}

/**
 * Defensible monetary procurement cost evaluation for a candidate action.
 */
export interface CostImpactEvaluation {
  is_cost_calculable: boolean;
  unit_cost: number | null;
  order_quantity: number | null;
  direct_procurement_cost: number | null;
  currency: string;
  cost_status: EvaluationCostStatus;
  unavailability_reason: string | null;
  notes: string[];
}

/**
 * Audit evidence supporting an action evaluation result.
 */
export interface EvaluationEvidence {
  action_id: string;
  action_type: CandidateActionType;
  decision_id: string;
  product_id: string;
  warehouse_id: string;
  inputs_summary: Record<string, unknown>;
  formulas: Record<string, string>;
  assumptions: string[];
  limitations: string[];
  calculation_notes: string[];
}

/**
 * Deterministic evaluation result for an individual candidate action matching Day 19 schema.
 */
export interface ActionEvaluationRecord {
  action_id: string;
  action_type: CandidateActionType;
  decision_id: string;
  product_id: string;
  warehouse_id: string;
  evaluated_at: string;
  stockout_exposure: StockoutExposureEvaluation;
  replenishment_impact: ReplenishmentImpactEvaluation;
  supplier_impact: SupplierImpactEvaluation;
  cost_impact: CostImpactEvaluation;
  evidence: EvaluationEvidence;
  overall_score: number | null;
  scoring_status: string;
  scoring_rationale: string;
}

export type ActionEvaluationResponse = ActionEvaluationRecord;

/**
 * Decision-level collection of evaluations for all applicable candidate actions.
 */
export interface DecisionEvaluationReportRecord {
  decision_id: string;
  product_id: string;
  warehouse_id: string;
  evaluated_at: string;
  total_actions_evaluated: number;
  evaluations: ActionEvaluationRecord[];
  summary_notes: string[];
}

export type DecisionEvaluationReportResponse = DecisionEvaluationReportRecord;

/**
 * Payload contract for evaluating an individual action.
 */
export interface EvaluateActionRequest {
  policy_type?: import('./inventory').ReplenishmentPolicyType;
  target_stock?: number;
  enforce_reorder_trigger?: boolean;
  record_to_graph?: boolean;
}

/**
 * Payload contract for evaluating all candidate actions of a decision.
 */
export interface EvaluateDecisionActionsRequest {
  policy_type?: import('./inventory').ReplenishmentPolicyType;
  target_stock?: number;
  enforce_reorder_trigger?: boolean;
  record_to_graph?: boolean;
}

/**
 * Categorical outcome status of a Day 20 recommendation generation run.
 */
export type RecommendationStatus =
  | 'RECOMMENDED'
  | 'NO_ACTION_REQUIRED'
  | 'NO_CANDIDATE_ACTIONS'
  | 'NO_ELIGIBLE_ACTION'
  | 'ALL_EVALUATIONS_FAILED';

/**
 * Specific deterministic method used to break ties between candidate actions.
 */
export type TieBreakMethod =
  | 'NONE'
  | 'ACTION_TYPE_PRIORITY'
  | 'EARLIEST_TIMESTAMP'
  | 'ACTION_IDENTIFIER';

/**
 * Auditable comparison record for a candidate action evaluated during recommendation.
 */
export interface AlternativeComparisonRecord {
  action_id: string;
  action_type: CandidateActionType;
  is_eligible: boolean;
  ineligibility_reason: string | null;
  rank: number | null;
  shortfall_satisfaction_ratio: number | null;
  shortfall_addressed: number | null;
  excess_quantity: number | null;
  exposure_index_delta: number | null;
  effective_supplier_risk: string | null;
  effective_lead_time_days: number | null;
  effective_reliability: number | null;
  direct_procurement_cost: number | null;
  cost_status: string | null;
  selection_notes: string[];
}

export type AlternativeComparisonResponse = AlternativeComparisonRecord;

/**
 * Deterministic recommendation record matching Day 20 schema.
 */
export interface RecommendationRecord {
  id: string;
  decision_id: string;
  product_id: string;
  warehouse_id: string;
  status: RecommendationStatus;
  selection_rule: string;
  recommended_action_id: string | null;
  recommended_action_type: CandidateActionType | null;
  recommended_action: CandidateActionRecord | null;
  selection_rationale: string;
  tie_broken: boolean;
  tie_break_method: TieBreakMethod;
  tie_breaking_rationale: string | null;
  total_actions_evaluated: number;
  alternatives: AlternativeComparisonRecord[];
  evaluation_evidence: EvaluationEvidence | null;
  selected_evaluation: ActionEvaluationRecord | null;
  created_at: string;
  is_fresh: boolean;
  stale_reason: string | null;
  metadata: Record<string, unknown>;
}


export type RecommendationResponse = RecommendationRecord;

/**
 * Payload contract for generating a deterministic recommendation.
 */
export interface GenerateRecommendationRequest {
  policy_type?: import('./inventory').ReplenishmentPolicyType;
  target_stock?: number;
  enforce_reorder_trigger?: boolean;
  record_to_graph?: boolean;
}

/**
 * Supported deterministic operational hard constraints matching Day 21 ConstraintType enum.
 */
export type ConstraintType =
  | 'WAREHOUSE_CAPACITY'
  | 'WAREHOUSE_ACTIVE'
  | 'PRODUCT_ACTIVE'
  | 'SUPPLIER_ACTIVE'
  | 'ORDER_QUANTITY_POSITIVE'
  | 'ORDER_QUANTITY_BOUNDS'
  | 'SUPPLIER_TARGET_DISTINCT'
  | 'MAX_BUDGET_LIMIT'
  | 'MIN_SUPPLIER_RELIABILITY'
  | 'MAX_SUPPLIER_LEAD_TIME'
  | 'CUSTOM';

/**
 * Outcome of an individual constraint evaluation matching Day 21 ConstraintEvaluationStatus enum.
 */
export type ConstraintEvaluationStatus = 'PASS' | 'FAIL' | 'UNABLE_TO_EVALUATE';

/**
 * Outcome of candidate action constraint evaluations matching Day 21 ActionValidationStatus enum.
 */
export type ActionValidationStatus =
  | 'SATISFIED'
  | 'VIOLATED'
  | 'UNABLE_TO_VALIDATE'
  | 'NO_CONSTRAINTS_APPLICABLE';

/**
 * Decision-level validation status matching Day 21 DecisionValidationStatus enum.
 */
export type DecisionValidationStatus =
  | 'ALL_SATISFIED'
  | 'SOME_VIOLATED'
  | 'ALL_VIOLATED'
  | 'HAS_UNABLE_TO_VALIDATE'
  | 'NO_ACTIONS';

/**
 * Auditable evidence preserved for an individual constraint evaluation.
 */
export interface ConstraintEvaluationEvidence {
  constraint_type: ConstraintType;
  constraint_name: string;
  status: ConstraintEvaluationStatus;
  observed_value: unknown | null;
  threshold_value: unknown | null;
  unit: string | null;
  reason: string;
  missing_inputs: string[];
  evaluated_at: string;
}

export type ConstraintEvaluationEvidenceResponse = ConstraintEvaluationEvidence;

/**
 * Action-level validation result matching Day 21 ActionValidationResponse schema.
 */
export interface ActionValidationRecord {
  action_id: string;
  action_type: CandidateActionType;
  decision_id: string;
  status: ActionValidationStatus;
  is_valid: boolean;
  constraints_evaluated: number;
  constraints_passed: number;
  constraints_failed: number;
  constraints_unable_to_evaluate: number;
  constraint_results: ConstraintEvaluationEvidence[];
  validation_notes: string[];
  evaluated_at: string;
}

export type ActionValidationResponse = ActionValidationRecord;

/**
 * Configuration item for an explicit constraint in API request.
 */
export interface ConstraintConfigRequest {
  constraint_type: ConstraintType;
  name: string;
  description?: string | null;
  is_hard?: boolean;
  parameters?: Record<string, unknown>;
  applicable_action_types?: CandidateActionType[] | null;
}

/**
 * Request payload contract for validating candidate actions of a decision.
 */
export interface ValidateDecisionRequest {
  constraints?: ConstraintConfigRequest[] | null;
  action_ids?: string[] | null;
  record_to_graph?: boolean;
}

/**
 * Request payload contract for validating a single candidate action.
 */
export interface ValidateActionRequest {
  constraints?: ConstraintConfigRequest[] | null;
}

/**
 * Decision-level candidate action validation report matching Day 21 DecisionValidationReportResponse schema.
 */
export interface DecisionValidationRecord {
  id: string;
  validation_id: string;
  decision_id: string;
  product_id: string;
  warehouse_id: string;
  status: DecisionValidationStatus;
  total_actions_evaluated: number;
  valid_action_ids: string[];
  invalid_action_ids: string[];
  unable_to_validate_action_ids: string[];
  action_results: ActionValidationRecord[];
  evaluated_constraints: string[];
  created_at: string;
  metadata: Record<string, unknown>;
}

export type DecisionValidationReportResponse = DecisionValidationRecord;

/**
 * Categorical nature of a decision evidence item matching Day 22 EvidenceType enum.
 */
export type EvidenceType = 'FACT' | 'ASSUMPTION' | 'CALCULATION';

/**
 * Operational domain category matching Day 22 EvidenceCategory enum.
 */
export type EvidenceCategory =
  | 'INVENTORY'
  | 'DEMAND'
  | 'SUPPLIER'
  | 'WAREHOUSE'
  | 'REPLENISHMENT'
  | 'STOCKOUT_RISK'
  | 'CONSTRAINT_VALIDATION'
  | 'COST'
  | 'ACTION_EVALUATION'
  | 'RECOMMENDATION'
  | 'OPERATIONAL';

/**
 * Explicit operational assumption record matching Day 22 DecisionAssumptionResponse schema.
 */
export interface DecisionAssumptionRecord {
  id: string;
  decision_id: string;
  category: EvidenceCategory;
  statement: string;
  assumed_value: unknown | null;
  rationale: string | null;
  source: string | null;
  action_id: string | null;
  version_id: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export type DecisionAssumptionResponse = DecisionAssumptionRecord;

/**
 * Strongly typed decision evidence item matching Day 22 DecisionEvidenceResponse schema.
 */
export interface DecisionEvidenceRecord {
  id: string;
  decision_id: string;
  evidence_type: EvidenceType;
  category: EvidenceCategory;
  description: string;
  value: unknown | null;
  unit: string | null;
  source: string | null;
  is_probability: boolean;
  action_id: string | null;
  version_id: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export type DecisionEvidenceResponse = DecisionEvidenceRecord;

/**
 * Categorical count breakdown of evidence matching Day 22 DecisionEvidenceSummaryResponse schema.
 */
export interface DecisionEvidenceSummaryRecord {
  total_items: number;
  total_facts: number;
  total_assumptions: number;
  total_calculations: number;
  categories_represented: EvidenceCategory[];
  actions_with_evidence: string[];
}

export type DecisionEvidenceSummaryResponse = DecisionEvidenceSummaryRecord;

/**
 * Consolidated decision evidence sheet matching Day 22 DecisionEvidenceSheetResponse schema.
 */
export interface DecisionEvidenceSheetRecord {
  id: string;
  decision_id: string;
  product_id: string;
  warehouse_id: string;
  created_at: string;
  items: DecisionEvidenceRecord[];
  assumptions: DecisionAssumptionRecord[];
  summary: DecisionEvidenceSummaryRecord;
  metadata: Record<string, unknown>;
}

export type DecisionEvidenceSheetResponse = DecisionEvidenceSheetRecord;

/**
 * Payload contract for creating an evidence item.
 */
export interface CreateEvidenceRequest {
  evidence_type: EvidenceType;
  category: EvidenceCategory;
  description: string;
  id?: string | null;
  value?: unknown | null;
  unit?: string | null;
  source?: string | null;
  is_probability?: boolean;
  action_id?: string | null;
  version_id?: string | null;
  metadata?: Record<string, unknown>;
}

/**
 * Payload contract for creating an explicit assumption.
 */
export interface CreateAssumptionRequest {
  category: EvidenceCategory;
  statement: string;
  id?: string | null;
  assumed_value?: unknown | null;
  rationale?: string | null;
  source?: string | null;
  action_id?: string | null;
  version_id?: string | null;
  metadata?: Record<string, unknown>;
}

/**
 * ---------------------------------------------------------------------------
 * Day 23: Decision Provenance Engine TypeScript Contracts
 * ---------------------------------------------------------------------------
 */

export type ProvenanceStage = 'INPUT' | 'RULE' | 'CALCULATION' | 'RESULT';

export type ProvenanceStepStatus = 'SUCCESS' | 'FAILED' | 'MISSING' | 'UNAVAILABLE' | 'SKIPPED';

export type ProvenanceInputType =
  | 'PRODUCT'
  | 'WAREHOUSE'
  | 'INVENTORY'
  | 'DEMAND'
  | 'SUPPLIER'
  | 'CANDIDATE_ACTION'
  | 'ASSUMPTION'
  | 'CONTEXT_SNAPSHOT'
  | 'DECISION_VERSION';

export type ProvenanceRuleType =
  | 'REPLENISHMENT_POLICY'
  | 'CONSTRAINT_CHECK'
  | 'SELECTION_STRATEGY'
  | 'TIE_BREAKER';

export type ProvenanceCalculationType =
  | 'REPLENISHMENT_QUANTITY'
  | 'STOCKOUT_EXPOSURE'
  | 'RUNWAY_COVERAGE'
  | 'SUPPLIER_RISK'
  | 'COST_IMPACT'
  | 'ACTION_SCORING';

export type ProvenanceResultType =
  | 'ACTION_EVALUATION'
  | 'VALIDATION_REPORT'
  | 'RECOMMENDATION'
  | 'EVIDENCE_SHEET';

export interface ProvenanceInputRecord {
  id: string;
  input_type: ProvenanceInputType;
  source_id: string;
  name: string;
  value: unknown | null;
  unit: string | null;
  status: ProvenanceStepStatus;
  evidence_id: string | null;
  metadata: Record<string, unknown>;
}

export type ProvenanceInputResponse = ProvenanceInputRecord;

export interface ProvenanceRuleRecord {
  id: string;
  rule_type: ProvenanceRuleType;
  rule_name: string;
  action_id: string | null;
  inputs_considered: string[];
  status: ProvenanceStepStatus;
  condition_met: boolean | null;
  outcome: string;
  validation_report_id: string | null;
  notes: string[];
  metadata: Record<string, unknown>;
}

export type ProvenanceRuleResponse = ProvenanceRuleRecord;

export interface ProvenanceCalculationRecord {
  id: string;
  calculation_type: ProvenanceCalculationType;
  calculation_name: string;
  action_id: string | null;
  formula: string | null;
  inputs_used: string[];
  rules_applied: string[];
  status: ProvenanceStepStatus;
  output_value: unknown | null;
  unit: string | null;
  error_message: string | null;
  evidence_id: string | null;
  metadata: Record<string, unknown>;
}

export type ProvenanceCalculationResponse = ProvenanceCalculationRecord;

export interface ProvenanceResultRecord {
  id: string;
  result_type: ProvenanceResultType;
  result_id: string;
  action_id: string | null;
  status: ProvenanceStepStatus;
  outcome_status: string;
  summary: string;
  calculations_used: string[];
  rules_applied: string[];
  value: unknown | null;
  metadata: Record<string, unknown>;
}

export type ProvenanceResultResponse = ProvenanceResultRecord;

export interface ProvenanceLineageEdge {
  source_id: string;
  target_id: string;
  relationship: string;
  metadata: Record<string, unknown>;
}

export type ProvenanceLineageEdgeResponse = ProvenanceLineageEdge;

export interface DecisionProvenanceTraceRecord {
  id: string;
  decision_id: string;
  version_id: string | null;
  execution_id: string;
  created_at: string;
  trigger: string;
  status: ProvenanceStepStatus;
  inputs: ProvenanceInputRecord[];
  rules: ProvenanceRuleRecord[];
  calculations: ProvenanceCalculationRecord[];
  results: ProvenanceResultRecord[];
  lineage_edges: ProvenanceLineageEdge[];
  graph_id: string | null;
  summary: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export type DecisionProvenanceTraceResponse = DecisionProvenanceTraceRecord;

export interface ProvenanceDerivationResponse {
  result: ProvenanceResultRecord;
  calculations: ProvenanceCalculationRecord[];
  rules: ProvenanceRuleRecord[];
  inputs: ProvenanceInputRecord[];
  lineage_edges: ProvenanceLineageEdge[];
}

export interface CaptureProvenanceRequest {
  version_id?: string | null;
  policy_type?: string;
  target_stock?: number | null;
  enforce_reorder_trigger?: boolean;
  record_to_graph?: boolean;
  trigger?: string;
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Day 24: Decision Replay Engine TypeScript Contracts
// ---------------------------------------------------------------------------

export type ReplayStatus = 'MATCHED' | 'DIFFERENT' | 'INCOMPLETE' | 'FAILED';

export type IncompleteReasonCode =
  | 'MISSING_PROVENANCE_TRACE'
  | 'MISSING_INPUT_RECORD'
  | 'UNAVAILABLE_HISTORICAL_INPUT'
  | 'UNAVAILABLE_RULE_DEFINITION'
  | 'MISSING_CANDIDATE_ACTIONS'
  | 'NO_RECORDED_RESULTS'
  | 'UNSUPPORTED_REPLAY_OPERATION';

export interface IncompleteReason {
  code: IncompleteReasonCode;
  message: string;
  details: Record<string, unknown>;
}

export type IncompleteReasonResponse = IncompleteReason;

export interface ReplayFieldDifference {
  field_path: string;
  original_value: unknown;
  replayed_value: unknown;
  difference_description: string;
}

export type ReplayFieldDifferenceResponse = ReplayFieldDifference;

export interface ReplayActionEvaluationRecord {
  action_id: string;
  scoring_status?: string | null;
  overall_score?: number | null;
  recommended_replenishment_quantity?: number | null;
  shortfall_addressed?: number | null;
  remaining_shortfall?: number | null;
  exposure_index_delta?: number | null;
  current_exposure_index?: number | null;
  projected_exposure_index?: number | null;
  direct_procurement_cost?: number | null;
  cost_status?: string | null;
}

export type ReplayActionEvaluationResponse = ReplayActionEvaluationRecord;

export interface ReplayResultSnapshotRecord {
  recommendation_id?: string | null;
  status?: string | null;
  recommended_action_id?: string | null;
  recommended_action_type?: string | null;
  tie_broken?: boolean | null;
  tie_break_method?: string | null;
  selection_rule?: string | null;
  evaluations: Record<string, ReplayActionEvaluationRecord>;
  metadata: Record<string, unknown>;
}

export type ReplayResultSnapshotResponse = ReplayResultSnapshotRecord;

export interface ReplayComparisonRecord {
  status: ReplayStatus;
  compared_fields: string[];
  ignored_fields: string[];
  differences: ReplayFieldDifference[];
  summary: string;
}

export type ReplayComparisonResponse = ReplayComparisonRecord;

export interface DecisionReplayRecord {
  id: string;
  decision_id: string;
  version_id?: string | null;
  original_trace_id?: string | null;
  original_execution_id?: string | null;
  replay_execution_id: string;
  created_at: string;
  status: ReplayStatus;
  original_result?: ReplayResultSnapshotRecord | null;
  replayed_result?: ReplayResultSnapshotRecord | null;
  comparison?: ReplayComparisonRecord | null;
  incomplete_reasons: IncompleteReason[];
  error_message?: string | null;
  reconstructed_inputs_summary: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export type DecisionReplayResponse = DecisionReplayRecord;

export interface ReplayDecisionRequest {
  version_id?: string | null;
  trace_id?: string | null;
  record_to_graph?: boolean;
  metadata?: Record<string, unknown>;
}


