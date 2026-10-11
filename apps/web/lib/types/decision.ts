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

