/**
 * Decision Explanation API client layer.
 *
 * Provides strongly typed client methods for interacting with the
 * Day 26 FastAPI Local LLM Explanation Layer endpoint:
 *   POST /api/decisions/{decision_id}/explanation
 *
 * Core Principle: "The system calculates. AI explains. Humans approve."
 */

import type { DecisionExplanation, GenerateExplanationRequest } from "../types/explanation";

export class ExplanationApiError extends Error {
  statusCode: number;
  detail?: string;

  constructor(message: string, statusCode: number, detail?: string) {
    super(message);
    this.name = "ExplanationApiError";
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
 * Requests an AI explanation for an existing business decision from the local LLM.
 *
 * @param decisionId Decision ID
 * @param versionId Optional version ID filter
 */
export async function generateDecisionExplanation(
  decisionId: string,
  versionId?: string | null
): Promise<DecisionExplanation> {
  const normId = decisionId.trim();
  if (!normId) {
    throw new ExplanationApiError("Decision ID must be provided.", 400);
  }

  const baseUrl = getApiBaseUrl();
  const endpoint = `${baseUrl}/api/decisions/${encodeURIComponent(normId)}/explanation`;
  const bodyPayload: GenerateExplanationRequest = {
    version_id: versionId || null,
  };

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(bodyPayload),
      cache: "no-store",
    });
  } catch (err: unknown) {
    const errorMsg =
      err instanceof Error ? err.message : "Network request failed";
    throw new ExplanationApiError(
      `Unable to reach EDOS Explanation API: ${errorMsg}`,
      0
    );
  }

  if (!response.ok) {
    let detail = "";
    try {
      const text = await response.text();
      try {
        const errJson = JSON.parse(text);
        detail = errJson.detail || JSON.stringify(errJson);
      } catch {
        detail = text;
      }
    } catch {
      detail = "Unknown server response";
    }

    if (response.status === 404) {
      throw new ExplanationApiError(
        `Decision not found: ${detail}`,
        404,
        detail
      );
    }
    if (response.status === 422) {
      throw new ExplanationApiError(
        `Insufficient decision context or validation error: ${detail}`,
        422,
        detail
      );
    }
    if (response.status === 503) {
      throw new ExplanationApiError(
        `Local LLM runtime (Ollama) unavailable: ${detail}`,
        503,
        detail
      );
    }
    if (response.status === 502) {
      throw new ExplanationApiError(
        `Ollama returned invalid or ungrounded response: ${detail}`,
        502,
        detail
      );
    }

    throw new ExplanationApiError(
      `Failed to generate decision explanation (HTTP ${response.status}): ${detail}`,
      response.status,
      detail
    );
  }

  return (await response.json()) as DecisionExplanation;
}
