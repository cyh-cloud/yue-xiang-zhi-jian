import { ApiError, del, get, post } from "./client";

export interface AgricultureProduct {
  id: string;
  name: string;
  icon: string;
  desc: string;
}

export interface AgricultureSource {
  key: string;
  name: string;
  org: string;
  doc_type: string;
  doc_no: string;
  url: string;
}

export interface AgriculturePhenophase {
  id: number;
  name: string;
  start_month: number;
  end_month: number;
  color: string | null;
  description: string;
  in_month?: boolean;
}

export interface AgricultureTask {
  id: number;
  date: string | null;
  day: number | null;
  task_md: string | null;
  title: string;
  category: string;
  category_label: string;
  priority: string;
  icon: string;
  description: string;
  tip: string;
  phase_id: number | null;
  phase_name: string | null;
  phase_color: string | null;
  sort_order: number;
  is_verified: number;
  evidence_level: "verified" | "sourced" | "unsourced";
  date_basis: string;
  source: AgricultureSource | null;
}

export interface AgricultureSolarTerm {
  date: string;
  day: number;
  name: string;
}

export interface AgricultureSourceSummary {
  total: number;
  verified: number;
  sourced: number;
  unsourced: number;
  sources: AgricultureSource[];
}

export interface AgricultureCalendar {
  success: true;
  product: Pick<AgricultureProduct, "id" | "name" | "icon">;
  year: number;
  month: number;
  is_configured: boolean;
  dates_provisional: boolean;
  source_summary: AgricultureSourceSummary;
  sources_all: AgricultureSource[];
  phenophase_current: Pick<
    AgriculturePhenophase,
    "id" | "name" | "color" | "description"
  > | null;
  phenophases: AgriculturePhenophase[];
  solar_terms: AgricultureSolarTerm[];
  tasks: AgricultureTask[];
}

export interface AgricultureProductsResponse {
  success: true;
  products: AgricultureProduct[];
}

export interface AgricultureSubscriptionsResponse {
  success: true;
  product_ids: string[];
}

export interface AgricultureSubscriptionResponse
  extends AgricultureSubscriptionsResponse {
  subscribed: boolean;
}

export interface AgricultureReminderDetail {
  product_id: string;
  product_name: string;
  period: string;
  title: string;
  items: string[];
}

export interface AgricultureReminderResponse {
  success: true;
  period: string;
  sent: number;
  details: AgricultureReminderDetail[];
}

export interface AgricultureQuestionHistory {
  question: string;
  answer: string;
}

export interface AgricultureAskPayload {
  question: string;
  product: string;
  history?: AgricultureQuestionHistory[];
}

export interface AgricultureSuggestionsResponse {
  success: true;
  suggestions: string[];
}

export interface AgricultureStreamCallbacks {
  onContent: (content: string) => void;
  onDone: () => void;
  onSuggestions: (suggestions: string[]) => void;
}

export interface PestSource {
  key: string;
  name: string;
  org: string;
  doc_type: string;
  doc_no: string;
  date: string;
  url: string;
}

export interface PestImage {
  file: string;
  credit: string;
  license: string;
  shot_date: string;
  source_url: string;
  caption: string;
}

export interface PestChemRow {
  agent: string;
  dose: string | number | null;
  interval_days: string | number | null;
  max_times: string | number | null;
}

export interface PestEntry {
  id: string;
  crop: string;
  crop_name: string;
  crop_icon: string;
  disease: string;
  alias: string;
  kind: "disease" | "pest";
  pathogen: string;
  part: string;
  severity: string;
  symptoms: string[];
  occurrence: string;
  treatment: string[];
  prevention: string[];
  registered: string[];
  chem_table: PestChemRow[];
  safety_note: string;
  image: PestImage | null;
  sources: PestSource[];
  is_verified: number;
}

export interface PestCrop {
  id: string;
  name: string;
  icon: string;
  summary: string;
  count: number;
}

export interface PestKnowledgeResponse {
  success: true;
  crops: PestCrop[];
  entries: PestEntry[];
  total: number;
  stats: {
    crops: number;
    entries: number;
    with_image: number;
    verified: number;
  };
  disclaimer: string;
}

export interface PestKnowledgeQuery {
  crop?: string;
  kind?: "" | "disease" | "pest";
  q?: string;
  limit?: number;
  offset?: number;
}

export interface PestDiagnosisPayload {
  crop: string;
  symptoms: string;
  image?: string[];
}

export interface PestDiagnosis {
  disease: string;
  severity: string;
  symptoms: string[];
  treatment: string[];
  prevention: string[];
  timing: string;
  note: string;
  crop: string;
  crop_icon: string;
  source: "ai" | "knowledge_base";
  source_label: string;
  source_note: string;
}

export interface PestDiagnosisResponse {
  success: true;
  diagnosis: PestDiagnosis;
}

export interface PestDiagnosisFailureResponse {
  success: false;
  code: string;
  message: string;
}

export function getAgricultureProducts(): Promise<AgricultureProductsResponse> {
  return get<AgricultureProductsResponse>("/api/agriculture/products");
}

export function getAgricultureCalendar(
  productId: string,
  month?: number,
): Promise<AgricultureCalendar> {
  const query = month ? `?month=${month}` : "";
  return get<AgricultureCalendar>(
    `/api/agriculture/calendar/${encodeURIComponent(productId)}${query}`,
  );
}

export function getAgricultureSubscriptions(): Promise<AgricultureSubscriptionsResponse> {
  return get<AgricultureSubscriptionsResponse>(
    "/api/agriculture/subscriptions",
  );
}

export function subscribeAgriculture(
  productId: string,
): Promise<AgricultureSubscriptionResponse> {
  return post<AgricultureSubscriptionResponse>("/api/agriculture/subscribe", {
    product_id: productId,
  });
}

export function unsubscribeAgriculture(
  productId: string,
): Promise<AgricultureSubscriptionResponse> {
  return del<AgricultureSubscriptionResponse>(
    `/api/agriculture/subscribe/${encodeURIComponent(productId)}`,
  );
}

export function checkAgricultureReminders(): Promise<AgricultureReminderResponse> {
  return post<AgricultureReminderResponse>(
    "/api/agriculture/reminders/check",
  );
}

export function getAgricultureSuggestions(
  productId: string,
): Promise<AgricultureSuggestionsResponse> {
  return get<AgricultureSuggestionsResponse>(
    `/api/agriculture/suggestions?product=${encodeURIComponent(productId)}`,
  );
}

export function getPestKnowledge(
  query: PestKnowledgeQuery = {},
): Promise<PestKnowledgeResponse> {
  const params = new URLSearchParams();
  if (query.crop) params.set("crop", query.crop);
  if (query.kind) params.set("kind", query.kind);
  if (query.q?.trim()) params.set("q", query.q.trim());
  if (query.limit) params.set("limit", String(query.limit));
  if (query.offset) params.set("offset", String(query.offset));
  const suffix = params.size ? `?${params.toString()}` : "";
  return get<PestKnowledgeResponse>(
    `/api/agriculture/pest-knowledge${suffix}`,
  );
}

export async function diagnoseAgriculture(
  payload: PestDiagnosisPayload,
): Promise<PestDiagnosisResponse> {
  const response = await post<
    PestDiagnosisResponse | PestDiagnosisFailureResponse
  >(
    "/api/agriculture/diagnose",
    payload,
  );
  if (!response.success) {
    throw new ApiError({
      status: 200,
      code: response.code,
      message: response.message,
    });
  }
  return response;
}

export async function streamAgricultureQuestion(
  payload: AgricultureAskPayload,
  sessionId: string,
  callbacks: AgricultureStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (sessionId) headers["X-Session-Id"] = sessionId;

  let response: Response;
  try {
    response = await fetch("/api/agriculture/ask/stream", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: "无法连接 AI 农技问答服务，请检查网络后重试。",
    });
  }

  if (!response.ok) {
    const failure = await readFailure(response);
    throw new ApiError({
      status: response.status,
      code: failure.code,
      message: failure.message,
    });
  }
  if (!response.body) {
    throw new ApiError({
      status: response.status,
      code: "empty_stream",
      message: "AI 服务没有返回可读取的回答。",
    });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawContent = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        const event = parseSseBlock(block);
        if (!event.data) continue;

        if (event.type === "error") {
          const failure = parseJsonRecord(event.data);
          throw new ApiError({
            status: 503,
            code: textValue(failure?.code) || "ai_unavailable",
            message:
              textValue(failure?.message) ||
              "AI 服务暂时不可用，请稍后重试。",
          });
        }
        if (event.type === "done") {
          callbacks.onDone();
          continue;
        }
        if (event.type === "suggestions") {
          const body = parseJsonRecord(event.data);
          const suggestions = Array.isArray(body?.suggestions)
            ? body.suggestions.filter(
                (item): item is string =>
                  typeof item === "string" && item.trim().length > 0,
              )
            : [];
          if (suggestions.length) callbacks.onSuggestions(suggestions);
          continue;
        }

        const body = parseJsonRecord(event.data);
        const content = textValue(body?.content);
        if (content) {
          sawContent = true;
          callbacks.onContent(content);
        }
      }
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      // The stream is already closed.
    }
  }

  if (!sawContent) {
    throw new ApiError({
      status: response.status,
      code: "empty_answer",
      message: "AI 服务未返回内容，请重试。",
    });
  }
}

interface ParsedSseBlock {
  type: string;
  data: string;
}

function parseSseBlock(block: string): ParsedSseBlock {
  let type = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      type = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
  }
  return { type, data: dataLines.join("\n") };
}

function parseJsonRecord(value: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(value);
    return typeof parsed === "object" && parsed !== null
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

async function readFailure(
  response: Response,
): Promise<{ code: string | null; message: string }> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const record =
    typeof body === "object" && body !== null
      ? (body as Record<string, unknown>)
      : null;
  return {
    code: textValue(record?.code) || null,
    message:
      textValue(record?.message) ||
      (response.status === 503
        ? "AI 服务暂时不可用，请稍后重试。"
        : "AI 农技问答请求失败，请稍后重试。"),
  };
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
