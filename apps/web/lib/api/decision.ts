/**
 * Decision Workspace API client layer.
 *
 * Provides strongly typed client methods for interacting with EDOS Decision APIs:
 * - Decision lifecycle & context: GET /api/decisions, GET /api/decisions/{id}, PATCH /api/decisions/{id}/status
 * - Candidate actions: GET /api/decisions/{id}/actions, POST /api/decisions/{id}/actions
 * - Action evaluation & recommendation: GET /api/decisions/{id}/recommendation, GET /api/decisions/{id}/evaluation
 * - Constraint validation: GET /api/decisions/{id}/validation
 * - Evidence & assumptions: GET /api/decisions/{id}/evidence-sheet, GET /api/decisions/{id}/evidence
 * - Provenance: GET /api/decisions/{id}/provenance
 * - Replay: GET /api/decisions/{id}/replay/latest, POST /api/decisions/{id}/replay
 * - Scenarios: GET /api/decisions/{id}/scenarios, GET /api/decisions/{id}/scenarios/{scenario_id}/comparison, POST /api/decisions/{id}/scenarios
 *
 * Core Principle: "The system calculates. AI explains. Humans approve."
 */

import type {
  DecisionRecord,
  DecisionStatus,
  DecisionEventRecord,
  DecisionVersionRecord,
  CandidateActionRecord,
  DecisionEvaluationReportRecord,
  RecommendationRecord,
  DecisionValidationRecord,
  DecisionEvidenceSheetRecord,
  DecisionEvidenceRecord,
  DecisionAssumptionRecord,
  DecisionProvenanceTraceRecord,
  DecisionReplayRecord,
  DecisionScenarioRecord,
  ScenarioComparisonRecord,
  ScenarioOverrides,
} from "../types/decision";

export class DecisionApiError extends Error {
  statusCode: number;
  errorCode?: string;
  category?: string;
  detail?: string;
  isRetryable: boolean;

  constructor(
    message: string,
    statusCode: number,
    detail?: string,
    errorCode?: string,
    category?: string
  ) {
    super(message);
    this.name = "DecisionApiError";
    this.statusCode = statusCode;
    this.detail = detail;
    this.errorCode = errorCode;
    this.category = category;
    this.isRetryable =
      statusCode === 0 ||
      statusCode === 408 ||
      statusCode === 429 ||
      statusCode >= 500;
  }
}

/**
 * Resolves the operational API base URL for either server-side or browser execution.
 */
function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "";
  }
  return (
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000"
  );
}

async function handleResponse<T>(response: Response, entityName: string): Promise<T> {
  if (!response.ok) {
    let detail = "";
    let errorCode: string | undefined;
    let category: string | undefined;
    let serverMessage: string | undefined;

    try {
      const errJson = await response.json();
      detail =
        typeof errJson.detail === "string"
          ? errJson.detail
          : JSON.stringify(errJson.detail || errJson);
      errorCode = errJson.error_code;
      category = errJson.category;
      serverMessage = errJson.message;
    } catch {
      try {
        detail = await response.text();
      } catch {
        detail = response.statusText;
      }
    }

    const message =
      serverMessage ||
      (response.status === 404
        ? `${entityName} not found: ${detail}`
        : response.status === 422
        ? `Validation error for ${entityName}: ${detail}`
        : `Failed request for ${entityName} (HTTP ${response.status}): ${detail}`);

    throw new DecisionApiError(
      message,
      response.status,
      detail,
      errorCode,
      category
    );
  }
  return (await response.json()) as T;
}

/**
 * Lists all business decisions with optional product/warehouse filtering.
 */
export async function listDecisions(filters?: {
  product_id?: string;
  warehouse_id?: string;
}): Promise<DecisionRecord[]> {
  const baseUrl = getApiBaseUrl();
  const params = new URLSearchParams();
  if (filters?.product_id) params.set("product_id", filters.product_id);
  if (filters?.warehouse_id) params.set("warehouse_id", filters.warehouse_id);
  const qs = params.toString() ? `?${params.toString()}` : "";

  try {
    const res = await fetch(`${baseUrl}/api/decisions${qs}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    return await handleResponse<DecisionRecord[]>(res, "Decisions list");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to reach EDOS Decision API: ${msg}`, 0);
  }
}

/**
 * Retrieves a single business decision by ID.
 */
export async function getDecision(decisionId: string): Promise<DecisionRecord> {
  const normId = decisionId.trim();
  if (!normId) throw new DecisionApiError("Decision ID must be provided", 400);

  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/api/decisions/${encodeURIComponent(normId)}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    return await handleResponse<DecisionRecord>(res, `Decision '${normId}'`);
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve decision '${normId}': ${msg}`, 0);
  }
}

/**
 * Creates a new business decision in initial DRAFT lifecycle state.
 */
export async function createDecision(payload: {
  product_id: string;
  warehouse_id: string;
}): Promise<DecisionRecord> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/api/decisions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });
    return await handleResponse<DecisionRecord>(res, "Decision creation");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to create decision: ${msg}`, 0);
  }
}

/**
 * Transitions decision lifecycle status following strict sequential rules.
 */
export async function updateDecisionStatus(
  decisionId: string,
  newStatus: DecisionStatus
): Promise<DecisionRecord> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/status`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ status: newStatus }),
    });
    return await handleResponse<DecisionRecord>(res, "Decision status update");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to update decision status: ${msg}`, 0);
  }
}

/**
 * Lists audit trail events for a decision.
 */
export async function getDecisionEvents(decisionId: string): Promise<DecisionEventRecord[]> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/events`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    return await handleResponse<DecisionEventRecord[]>(res, "Decision events");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve decision events: ${msg}`, 0);
  }
}

/**
 * Lists historical versions for a decision.
 */
export async function getDecisionVersions(decisionId: string): Promise<DecisionVersionRecord[]> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/versions`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    return await handleResponse<DecisionVersionRecord[]>(res, "Decision versions");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve decision versions: ${msg}`, 0);
  }
}

/**
 * Lists candidate actions for a decision.
 */
export async function getCandidateActions(decisionId: string): Promise<CandidateActionRecord[]> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/actions`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    return await handleResponse<CandidateActionRecord[]>(res, "Candidate actions");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve candidate actions: ${msg}`, 0);
  }
}

/**
 * Creates a candidate action for a decision.
 */
export async function createCandidateAction(
  decisionId: string,
  action: {
    type: string;
    parameters?: Record<string, unknown>;
    description?: string;
  }
): Promise<CandidateActionRecord> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/actions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(action),
    });
    return await handleResponse<CandidateActionRecord>(res, "Create candidate action");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to create candidate action: ${msg}`, 0);
  }
}

/**
 * Retrieves the latest recommendation or generates one using backend lexicographic dominance.
 */
export async function getDecisionRecommendation(
  decisionId: string,
  options?: { recompute?: boolean }
): Promise<RecommendationRecord> {
  const baseUrl = getApiBaseUrl();
  const qs = options?.recompute ? "?recompute=true" : "";
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/recommendation${qs}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      }
    );
    return await handleResponse<RecommendationRecord>(res, "Decision recommendation");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve recommendation: ${msg}`, 0);
  }
}

/**
 * Retrieves latest evaluation report across candidate actions.
 */
export async function getDecisionEvaluation(decisionId: string): Promise<DecisionEvaluationReportRecord> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/evaluation`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      }
    );
    return await handleResponse<DecisionEvaluationReportRecord>(res, "Decision evaluation");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve evaluation report: ${msg}`, 0);
  }
}

/**
 * Retrieves the latest hard-constraint validation report for a decision.
 */
export async function getDecisionValidation(
  decisionId: string,
  recompute: boolean = false
): Promise<DecisionValidationRecord> {
  const baseUrl = getApiBaseUrl();
  const qs = recompute ? "?recompute=true" : "";
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/validation${qs}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      }
    );
    return await handleResponse<DecisionValidationRecord>(res, "Decision validation");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve validation report: ${msg}`, 0);
  }
}

/**
 * Retrieves the consolidated evidence sheet (facts, assumptions, calculations).
 */
export async function getDecisionEvidenceSheet(
  decisionId: string,
  autoCompile: boolean = true
): Promise<DecisionEvidenceSheetRecord> {
  const baseUrl = getApiBaseUrl();
  const qs = autoCompile ? "?auto_compile=true" : "";
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/evidence-sheet${qs}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      }
    );
    return await handleResponse<DecisionEvidenceSheetRecord>(res, "Evidence sheet");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve evidence sheet: ${msg}`, 0);
  }
}

/**
 * Retrieves the latest provenance trace for a decision.
 */
export async function getDecisionProvenance(
  decisionId: string,
  versionId?: string
): Promise<DecisionProvenanceTraceRecord | null> {
  const baseUrl = getApiBaseUrl();
  const qs = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/provenance${qs}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      }
    );
    if (res.status === 404) {
      return null;
    }
    return await handleResponse<DecisionProvenanceTraceRecord>(res, "Decision provenance");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError && err.statusCode === 404) return null;
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve provenance: ${msg}`, 0);
  }
}

/**
 * Retrieves latest replay record for a decision.
 */
export async function getDecisionReplay(decisionId: string): Promise<DecisionReplayRecord | null> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/replay/latest`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      }
    );
    if (res.status === 404) {
      return null;
    }
    return await handleResponse<DecisionReplayRecord>(res, "Decision replay");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError && err.statusCode === 404) return null;
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve replay record: ${msg}`, 0);
  }
}

/**
 * Triggers a decision replay run to verify deterministic reproducibility.
 */
export async function executeDecisionReplay(decisionId: string): Promise<DecisionReplayRecord> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/replay`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({}),
      }
    );
    return await handleResponse<DecisionReplayRecord>(res, "Execute replay");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to execute decision replay: ${msg}`, 0);
  }
}

/**
 * Lists scenario execution records for a decision.
 */
export async function getDecisionScenarios(decisionId: string): Promise<DecisionScenarioRecord[]> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/scenarios`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      }
    );
    return await handleResponse<DecisionScenarioRecord[]>(res, "Decision scenarios");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve scenarios: ${msg}`, 0);
  }
}

/**
 * Retrieves baseline-versus-scenario comparison.
 */
export async function getDecisionScenarioComparison(
  decisionId: string,
  scenarioId: string
): Promise<ScenarioComparisonRecord> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/scenarios/${encodeURIComponent(scenarioId.trim())}/comparison`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      }
    );
    return await handleResponse<ScenarioComparisonRecord>(res, "Scenario comparison");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to retrieve scenario comparison: ${msg}`, 0);
  }
}

/**
 * Executes a what-if scenario run with supported overrides.
 */
export async function executeDecisionScenario(
  decisionId: string,
  overrides: ScenarioOverrides,
  description?: string
): Promise<DecisionScenarioRecord> {
  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(
      `${baseUrl}/api/decisions/${encodeURIComponent(decisionId.trim())}/scenarios`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          overrides,
          description: description || "What-if scenario exploration",
        }),
      }
    );
    return await handleResponse<DecisionScenarioRecord>(res, "Execute scenario");
  } catch (err: unknown) {
    if (err instanceof DecisionApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new DecisionApiError(`Unable to execute scenario: ${msg}`, 0);
  }
}
