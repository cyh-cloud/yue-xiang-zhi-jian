import { get, post } from "./client";

export const EC_PRODUCTS = [
  "荔枝",
  "龙眼",
  "柑橘",
  "香蕉",
  "水产养殖",
  "水稻",
  "茶叶",
  "蔬菜",
] as const;

export const EC_STYLES = ["热情", "专业", "故事", "高级"] as const;
export type EcStyle = (typeof EC_STYLES)[number];

export const EC_COPY_FORMATS = [
  "详情页",
  "主图文案",
  "朋友圈",
  "小红书",
  "短视频脚本",
] as const;
export type EcCopyFormat = (typeof EC_COPY_FORMATS)[number];

export interface GeneratedScriptResponse {
  success: true;
  script: string;
  degraded?: boolean;
}

export interface LiveFeedback {
  speed_score: number;
  emotion_score: number;
  interaction_score: number;
  selling_score: number;
  overall_score: number;
  summary: string;
  suggestions: string[];
  source: "ai" | "rule";
  source_note: string;
  evidence?: Record<string, string>;
}

export interface LiveFeedbackResponse {
  success: true;
  feedback: LiveFeedback;
}

export interface GeneratedCopyResponse {
  success: true;
  copywriting: string;
  format: EcCopyFormat;
  degraded?: boolean;
}

export interface CopyFeedback {
  structure_score: number;
  selling_score: number;
  format_score: number;
  compliance_score: number;
  overall_score: number;
  suggestions: string[];
  source: "rule";
  source_note: string;
}

export interface CopyFeedbackResponse {
  success: true;
  feedback: CopyFeedback;
}

export interface ServiceScore {
  total: number;
  details: {
    politeness: number;
    professional: number;
    solving: number;
    empathy: number;
  };
  tips: string[];
}

export interface ServiceSentiment {
  level: number;
  label: string;
}

export interface CustomerOpeningResponse {
  success: true;
  message: string;
  degraded?: boolean;
}

export interface CustomerReplyResponse {
  success: true;
  reply: string;
  score: ServiceScore;
  sentiment: ServiceSentiment;
  degraded?: boolean;
}

export interface ServiceHint {
  analysis?: string;
  strategy?: string;
  templates?: string[];
  tips?: string[];
}

export interface ServiceHintResponse {
  success: true;
  hint: ServiceHint;
  degraded?: boolean;
}

export interface TrainingSubmissionResponse {
  success: true;
  submission_id: number;
  assignment_id: number;
  attempts: number;
  rule_score: number;
}

export interface LiveReadingReport {
  coverage: number;
  missed_chars: number;
  spoken_chars: number;
  duration_sec: number;
  speed_cpm: number;
  speed_score: number;
  rubric_score: number;
  rubric_hit: number;
  rubric_total: number;
  rubric_items: Array<{
    name: string;
    in_script: boolean;
    said: boolean;
  }>;
  max_silence_sec: number;
  silence_penalty: number;
  overall_score: number;
  tips: string[];
  source: "rule";
  source_note: string;
}

export interface LiveReadingResponse {
  success: true;
  report: LiveReadingReport;
}

export interface LiveCommentsResponse {
  success: true;
  comments: string[];
  source: "ai";
}

export interface TrainingRecord {
  id: number;
  product?: string;
  score?: number | null;
  rule_score?: number | null;
  status: string;
  status_label: string;
  attempts: number;
  submitted_at?: string;
  graded_at?: string;
  feedback?: string;
  report?: Partial<LiveReadingReport>;
  feedback_detail?: Partial<LiveFeedback>;
  meta?: {
    format?: string;
    raw_product?: string;
    scenario?: string;
    personality?: string;
    difficulty?: string;
    rounds?: number;
  };
}

export interface TrainingRecordsResponse {
  success: true;
  records: TrainingRecord[];
  kind: "live" | "copy" | "cs";
}

export type TrainingKind = "live" | "copy" | "cs";
export type ChatRole = "user" | "assistant";

export interface TrainingTurn {
  role: ChatRole;
  content: string;
}

export function generateLiveScript(
  product: string,
  style: EcStyle,
): Promise<GeneratedScriptResponse> {
  return post<GeneratedScriptResponse>("/api/ecommerce/script", {
    product,
    style,
  });
}

export function scoreLiveScript(script: string): Promise<LiveFeedbackResponse> {
  return post<LiveFeedbackResponse>("/api/ecommerce/feedback", { script });
}

export function generateCopywriting(payload: {
  product: string;
  format: EcCopyFormat;
  audience: string;
  selling_points: string;
}): Promise<GeneratedCopyResponse> {
  return post<GeneratedCopyResponse>("/api/ecommerce/copywriting", payload);
}

export function scoreCopywriting(
  script: string,
  format: EcCopyFormat,
): Promise<CopyFeedbackResponse> {
  return post<CopyFeedbackResponse>("/api/ecommerce/copy/feedback", {
    script,
    format,
  });
}

export function startCustomerService(payload: {
  scenario: string;
  personality: string;
  product: string;
}): Promise<CustomerOpeningResponse> {
  return post<CustomerOpeningResponse>(
    "/api/ecommerce/customer-service/next",
    { ...payload, history: [] },
  );
}

export function sendCustomerServiceReply(payload: {
  message: string;
  history: TrainingTurn[];
  scenario: string;
  personality: string;
  difficulty: string;
  product: string;
}): Promise<CustomerReplyResponse> {
  return post<CustomerReplyResponse>(
    "/api/ecommerce/customer-service",
    payload,
  );
}

export function getCustomerServiceHint(payload: {
  scenario: string;
  personality: string;
  product: string;
  history: TrainingTurn[];
  last_customer_msg: string;
}): Promise<ServiceHintResponse> {
  return post<ServiceHintResponse>(
    "/api/ecommerce/customer-service/hint",
    payload,
  );
}

export function submitLiveTraining(payload: {
  product: string;
  script: string;
  feedback: LiveFeedback | null;
  report: Partial<LiveReadingReport>;
  meta: { style: EcStyle };
}): Promise<TrainingSubmissionResponse> {
  return post<TrainingSubmissionResponse>("/api/ecommerce/live/submit", {
    ...payload,
  });
}

export function analyzeLiveReading(payload: {
  script: string;
  transcript: string;
  duration_sec: number;
  max_silence_sec: number;
}): Promise<LiveReadingResponse> {
  return post<LiveReadingResponse>("/api/ecommerce/live/report", payload);
}

export function generateLiveComments(payload: {
  speech: string;
  product: string;
  difficulty: string;
}): Promise<LiveCommentsResponse> {
  return post<LiveCommentsResponse>("/api/ecommerce/live/comments", payload);
}

export function submitCopyTraining(payload: {
  product: string;
  script: string;
  score: number;
  meta: { format: EcCopyFormat; raw_product: string };
}): Promise<TrainingSubmissionResponse> {
  return post<TrainingSubmissionResponse>(
    "/api/ecommerce/copy/submit",
    payload,
  );
}

export function submitCustomerServiceTraining(payload: {
  product: string;
  transcript: TrainingTurn[];
  score: number;
  meta: {
    scenario: string;
    personality: string;
    difficulty: string;
    rounds: number;
    scored_rounds: number;
  };
}): Promise<TrainingSubmissionResponse> {
  return post<TrainingSubmissionResponse>(
    "/api/ecommerce/cs/submit",
    payload,
  );
}

export function getTrainingRecords(
  kind: TrainingKind,
): Promise<TrainingRecordsResponse> {
  return get<TrainingRecordsResponse>(
    `/api/ecommerce/live/records?kind=${encodeURIComponent(kind)}`,
  );
}
