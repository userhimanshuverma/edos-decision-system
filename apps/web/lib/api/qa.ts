/**
 * Decision Q&A API client layer.
 *
 * Provides strongly typed client methods for interacting with the
 * Day 27 FastAPI Local LLM Decision Q&A Layer endpoint:
 *   POST /api/decisions/{decision_id}/questions
 *
 * Core Principle: "The system calculates. AI explains. Humans approve."
 */

import type {
  DecisionQuestionRequest,
  DecisionQuestionResponse,
} from "../types/qa";

export class DecisionQuestionApiError extends Error {
  statusCode: number;
  detail?: string;

  constructor(message: string, statusCode: number, detail?: string) {
    super(message);
    this.name = "DecisionQuestionApiError";
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

/**
 * Resolves the operational API base URL for either server-side or browser execution.
 */
function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  }
  return (
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000"
  );
}

/**
 * Asks a grounded natural-language question about an existing business decision.
 *
 * @param decisionId Decision ID
 * @param question Question text from the reviewer
 * @param versionId Optional version ID filter
 */
export async function askDecisionQuestion(
  decisionId: string,
  question: string,
  versionId?: string | null
): Promise<DecisionQuestionResponse> {
  const normId = decisionId.trim();
  if (!normId) {
    throw new DecisionQuestionApiError("Decision ID must be provided.", 400);
  }

  const normQuestion = question.trim();
  if (!normQuestion) {
    throw new DecisionQuestionApiError("Question text must not be empty.", 422);
  }

  const baseUrl = getApiBaseUrl();
  const endpoint = `${baseUrl}/api/decisions/${encodeURIComponent(normId)}/questions`;
  const bodyPayload: DecisionQuestionRequest = {
    question: normQuestion,
    version_id: versionId || null,
  };

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(bodyPayload),
    });
  } catch (err: unknown) {
    const errorMsg =
      err instanceof Error ? err.message : "Failed to connect to EDOS API";
    throw new DecisionQuestionApiError(
      `Network communication error: ${errorMsg}`,
      0
    );
  }

  if (!response.ok) {
    let errorDetail = "";
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.message || response.statusText;
    } catch {
      errorDetail = response.statusText;
    }

    if (response.status === 404) {
      throw new DecisionQuestionApiError(
        `Decision not found: ${errorDetail}`,
        404,
        errorDetail
      );
    }
    if (response.status === 422) {
      throw new DecisionQuestionApiError(
        `Invalid question or context: ${errorDetail}`,
        422,
        errorDetail
      );
    }
    if (response.status === 503) {
      throw new DecisionQuestionApiError(
        `Local LLM service unavailable: ${errorDetail}`,
        503,
        errorDetail
      );
    }
    if (response.status === 502) {
      throw new DecisionQuestionApiError(
        `Model returned invalid or ungrounded response: ${errorDetail}`,
        502,
        errorDetail
      );
    }

    throw new DecisionQuestionApiError(
      `EDOS Q&A API error (${response.status}): ${errorDetail}`,
      response.status,
      errorDetail
    );
  }

  const data: DecisionQuestionResponse = await response.json();
  return data;
}
