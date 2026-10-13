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


