/**
 * Day 26 Local LLM Explanation Layer TypeScript domain types.
 * Matches apps/api/app/api/schemas.py (DecisionExplanationResponse, GenerateExplanationRequest)
 * and app/domain/explanation.py (DecisionExplanation).
 *
 * Core Principle: "The system calculates. AI explains. Humans approve."
 */

export interface DecisionExplanation {
  decision_id: string;
  decision_version_id: string | null;
  recommendation_summary: string;
  reasoning_summary: string;
  supporting_evidence: string[];
  risks_and_constraints: string[];
  assumptions_and_missing_information: string[];
  review_considerations: string[];
  limitations: string[];
  model_name: string;
  generated_at: string;
}

export interface GenerateExplanationRequest {
  version_id?: string | null;
}
