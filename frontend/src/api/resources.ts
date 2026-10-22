import { ApiError, get, post } from "./client";

export interface DialectSummary {
  id: string;
  name: string;
  region: string;
  emoji: string;
  areas: string;
  speakers: string;
}

export interface DialectPhrase {
  dialect: string;
  mandarin: string;
  pinyin: string;
}

export interface DialectInfo extends DialectSummary {
  greeting: string;
  greeting_meaning: string;
  features: string[];
  phrases: DialectPhrase[];
  quick_questions: string[];
}

export interface DialectsResponse {
  success: true;
  dialects: DialectSummary[];
}

export interface DialectInfoResponse {
  success: true;
  info: DialectInfo;
}

export interface DialectVoiceHistory {
  user: string;
  bot: string;
}

export interface DialectVoiceResult {
  text: string;
  dialect: string;
  dialect_name: string;
  answer: string;
  suggestions: string[];
  source: "ai" | "fallback";
  chem_notice: string;
}

export interface DialectVoiceResponse {
  success: true;
  result: DialectVoiceResult;
}

export interface DialectVoiceFailure {
  success: false;
  code?: string;
  message: string;
}

export interface CaseStat {
  icon: string;
  label: string;
  value: string;
}

export interface CaseMilestone {
  period: string;
  title: string;
  desc: string;
}

export interface CaseSource {
  date: string;
  media: string;
  title: string;
  url: string;
}

export interface SuccessCase {
  id: number;
  title: string;
  description: string;
  location: string;
  region: string;
  background: string;
  stats: CaseStat[];
  milestones: CaseMilestone[];
  quote: string;
  quote_author: string;
  lessons: string[];
  sources: CaseSource[];
}

export interface CaseReviewStats {
  approved: number;
  pending: number;
  rejected: number;
  total: number;
}

export interface CasesResponse {
  success: true;
  cases: SuccessCase[];
  case_review: CaseReviewStats;
  source_note: string;
  lessons_note: string;
}

export interface PolicySource {
  title: string;
  media?: string;
  date?: string;
  url?: string;
}

export interface Policy {
  id: number;
  title: string;
  summary: string;
  category: string;
  date: string;
  content: string;
  sources: PolicySource[];
  author_id?: string;
  created_at?: string;
  updated_at?: string;
  is_published?: number;
}

export interface PoliciesResponse {
  success: true;
  policies: Policy[];
  source_note: string;
  disclaimer: string;
}

export function getDialects(): Promise<DialectsResponse> {
  return get<DialectsResponse>("/api/resources/dialects");
}

export function getDialectInfo(dialect: string): Promise<DialectInfoResponse> {
  return get<DialectInfoResponse>(
    `/api/resources/dialect-info?dialect=${encodeURIComponent(dialect)}`,
  );
}

export async function askDialectVoice(payload: {
  text: string;
  dialect: string;
  history: DialectVoiceHistory[];
}): Promise<DialectVoiceResult> {
  const response = await post<
    DialectVoiceResponse | DialectVoiceFailure
  >("/api/resources/voice", payload);
  if (!response.success) {
    throw new ResourcesApiFailure({
      status: 200,
      code: response.code ?? null,
      message: response.message,
    });
  }
  return response.result;
}

export function getCases(): Promise<CasesResponse> {
  return get<CasesResponse>("/api/resources/cases");
}

export function getCase(caseId: number): Promise<SuccessCase> {
  return get<{ success: true; case: SuccessCase }>(
    `/api/resources/cases/${caseId}`,
  ).then((response) => response.case);
}

export function getPolicies(): Promise<PoliciesResponse> {
  return get<PoliciesResponse>("/api/resources/policies");
}

export class ResourcesApiFailure extends ApiError {}
