/**
 * Day 27 Decision Q&A TypeScript domain types.
 * Matches apps/api/app/api/schemas.py (DecisionQuestionRequest, DecisionQuestionResponse)
 * and apps/api/app/domain/explanation.py (DecisionQuestionStatus, DecisionQuestionAnswer).
 *
 * Core Principle: "The system calculates. AI explains. Humans approve."
 */

export type DecisionQuestionStatus =
  | "ANSWERED"
  | "INSUFFICIENT_CONTEXT"
  | "UNANSWERABLE";

export interface DecisionQuestionRequest {
  question: string;
  version_id?: string | null;
}

export interface DecisionQuestionResponse {
  decision_id: string;
  decision_version_id: string | null;
  question: string;
  answer: string;
  status: DecisionQuestionStatus;
  supporting_evidence: string[];
  limitations: string[];
  model_name: string;
  generated_at: string;
}
