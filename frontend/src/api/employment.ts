import { del, get, post, put } from "./client";

export interface EnterpriseJob {
  id: number;
  title: string;
  company: string;
  salary: string;
  requirements: string[];
  description: string;
  location: string;
  category: string;
  job_type: string;
  education: string;
  experience: string;
  company_size: string;
  industry: string;
  enterprise_id: string;
  review_status: string;
  posted_at: string;
  source_type: "enterprise";
  is_demo?: number;
}

export interface RecruitmentSource {
  title: string;
  url: string;
  media: string;
  date: string;
}

export interface PublicRecruitment {
  key: string;
  title: string;
  org: string;
  region: string;
  category: string;
  job_type?: string;
  headcount?: string;
  education?: string;
  experience?: string;
  salary?: string;
  signup_start?: string;
  deadline?: string;
  signup_way?: string;
  contact?: string;
  publish_date?: string;
  description?: string;
  sources?: RecruitmentSource[];
  status: "open" | "upcoming" | "closed" | "unknown";
  status_label: string;
  days_left?: number | null;
  starts_in?: number | null;
  source_type: "public_recruit";
}

export interface CategoryOption {
  value: string;
  count: number;
}

export interface CategoryOptions {
  enterprise: CategoryOption[];
  recruit: CategoryOption[];
}

export interface JobListResponse {
  success: true;
  jobs: EnterpriseJob[];
  recruitments: PublicRecruitment[];
  recruit_source_note: string;
  recruit_disclaimer: string;
  category_options: CategoryOptions;
  recruit_hidden_by_salary: number;
  enterprise_review_pending: number;
}

export interface JobDetailResponse {
  success: boolean;
  job?: EnterpriseJob;
  message?: string;
}

export interface SimilarJobsResponse {
  success: true;
  jobs: EnterpriseJob[];
}

export interface Application {
  id: number;
  user_id: string;
  job_id: number;
  status: "pending" | "interview" | "approved" | "rejected" | string;
  applied_at: string;
  title: string;
  company: string;
  salary: string;
  location: string;
  category: string;
  enterprise_id: string;
  channel: "enterprise";
}

export interface JobIntent {
  channel: "public_recruit";
  recruit_key: string;
  note: string;
  created_at: string;
  title: string;
  org: string;
  region: string;
  category: string;
  deadline: string;
  status: string;
  status_label: string;
}

export interface MyJobsResponse {
  success: true;
  applications: Application[];
  intents: JobIntent[];
  intent_notice: string;
  has_resume: boolean;
}

export interface LearnerProfileBasic {
  username: string;
  name: string;
  email: string;
  phone: string;
  bio: string;
  region: string;
}

export interface LearnerCertificate {
  name: string;
  status: "earned" | "in_progress" | "locked" | string;
  earned: boolean;
  progress: number;
  date: string;
}

export interface LearnerTrainingRecord {
  title: string;
  score: number | null;
  scored: boolean;
  status: string;
  submitted_at: string;
}

export interface LearnerLearningProgress {
  direction: string;
  progress: number;
}

export interface LearnerProfile {
  basic: LearnerProfileBasic;
  certificates: LearnerCertificate[];
  points: number;
  learning: LearnerLearningProgress | null;
  training: LearnerTrainingRecord[];
}

export interface ResumeExperience {
  company: string;
  position: string;
  period: string;
  desc: string;
}

export interface ResumeRecord {
  id?: number;
  user_id: string;
  title: string;
  region: string;
  education: string;
  work_years: string;
  phone: string;
  email: string;
  self_eval: string;
  skills: string;
  experience: ResumeExperience[];
  ai_used: number;
  ai_sections?: ResumeAiSection[];
  created_at?: string;
  updated_at?: string;
}

export interface ResumePayload {
  title: string;
  region: string;
  education: string;
  work_years: string;
  phone: string;
  email: string;
  self_eval: string;
  skills: string;
  experience: ResumeExperience[];
}

export type ResumeAiSection = "self_eval" | "skills" | "experience";

export interface EmploymentStats {
  applied: number;
  saved: number;
  intents: number;
  messages: number;
}

export interface LearnerProfileResponse {
  success: true;
  profile: LearnerProfile;
}

export interface ResumeResponse {
  success: true;
  resume: ResumeRecord | null;
}

export interface SaveResumeResponse {
  success: true;
  message: string;
  resume: ResumeRecord;
}

export interface ResumeAiResponse {
  success: true;
  section: ResumeAiSection;
  section_label: string;
  text: string;
  notice: string;
}

export interface EmploymentStatsResponse {
  success: true;
  stats: EmploymentStats;
}

export interface SavedJobsResponse {
  success: true;
  saved_ids: number[];
}

export interface MutationResponse {
  success: boolean;
  message: string;
  has_resume?: boolean;
  created?: boolean;
  notice?: string;
  code?: string;
}

export interface EmploymentQuery {
  keyword?: string;
  location?: string;
  salary?: string;
  category?: string;
}

export function getJobs(query: EmploymentQuery = {}): Promise<JobListResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value) params.set(key, value);
  }
  const suffix = params.size ? `?${params.toString()}` : "";
  return get<JobListResponse>(`/api/employment/jobs${suffix}`);
}

export function getJobDetail(jobId: number): Promise<JobDetailResponse> {
  return get<JobDetailResponse>(`/api/employment/jobs/${jobId}`);
}

export function getSimilarJobs(jobId: number): Promise<SimilarJobsResponse> {
  return get<SimilarJobsResponse>(`/api/employment/jobs/${jobId}/similar`);
}

export function getSavedJobs(userId: string): Promise<SavedJobsResponse> {
  return get<SavedJobsResponse>(
    `/api/employment/saved/${encodeURIComponent(userId)}`,
  );
}

export function saveJob(
  userId: string,
  jobId: number,
): Promise<MutationResponse> {
  return post<MutationResponse>("/api/employment/save", {
    user_id: userId,
    job_id: jobId,
  });
}

export function unsaveJob(
  userId: string,
  jobId: number,
): Promise<MutationResponse> {
  return del<MutationResponse>("/api/employment/save", {
    data: { user_id: userId, job_id: jobId },
  });
}

export function applyForJob(
  userId: string,
  jobId: number,
): Promise<MutationResponse> {
  return post<MutationResponse>("/api/employment/apply", {
    user_id: userId,
    job_id: jobId,
  });
}

export function getMyJobs(userId: string): Promise<MyJobsResponse> {
  return get<MyJobsResponse>(
    `/api/employment/my-jobs/${encodeURIComponent(userId)}`,
  );
}

export function addJobIntent(
  userId: string,
  recruitKey: string,
  note = "",
): Promise<MutationResponse> {
  return post<MutationResponse>("/api/employment/intent", {
    user_id: userId,
    recruit_key: recruitKey,
    note,
  });
}

export function removeJobIntent(
  userId: string,
  recruitKey: string,
): Promise<MutationResponse> {
  return del<MutationResponse>("/api/employment/intent", {
    data: { user_id: userId, recruit_key: recruitKey },
  });
}

export function getLearnerProfile(
  userId: string,
): Promise<LearnerProfileResponse> {
  return get<LearnerProfileResponse>(
    `/api/employment/profile/${encodeURIComponent(userId)}`,
  );
}

export function getResume(userId: string): Promise<ResumeResponse> {
  return get<ResumeResponse>(
    `/api/employment/resume/${encodeURIComponent(userId)}`,
  );
}

export function saveResume(
  userId: string,
  payload: ResumePayload,
): Promise<SaveResumeResponse> {
  return put<SaveResumeResponse>(
    `/api/employment/resume/${encodeURIComponent(userId)}`,
    payload,
  );
}

export function generateResumeSection(
  userId: string,
  section: ResumeAiSection,
  draft: string,
): Promise<ResumeAiResponse> {
  return post<ResumeAiResponse>("/api/employment/resume/ai", {
    user_id: userId,
    section,
    draft,
  });
}

export function getEmploymentStats(
  userId: string,
): Promise<EmploymentStatsResponse> {
  return get<EmploymentStatsResponse>(
    `/api/employment/stats/${encodeURIComponent(userId)}`,
  );
}
