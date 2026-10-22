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
  review_comment: string;
  reviewed_at: string;
  posted_at: string;
  is_demo?: number;
}

export interface EnterpriseJobInput {
  title: string;
  salary: string;
  description: string;
  location: string;
  category: string;
  requirements: string[];
  job_type?: string;
  education?: string;
  experience?: string;
  industry?: string;
}

export interface EnterpriseApplication {
  id: number;
  user_id: string;
  job_id: number;
  status: string;
  applied_at: string;
  job_title: string;
  applicant_name: string;
  applicant_phone: string;
  applicant_email: string;
  applicant_bio: string;
  resume_title: string | null;
  resume_region: string | null;
  resume_education: string | null;
  resume_work_years: string | number | null;
  resume_phone: string | null;
  resume_email: string | null;
  resume_self_eval: string | null;
  resume_skills: string | null;
  resume_experience: string | null;
  resume_updated_at: string | null;
}

export interface EnterpriseStats {
  total_jobs: number;
  pending_jobs: number;
  total_applications: number;
}

interface EnterpriseStatsResponse {
  success: true;
  stats: EnterpriseStats;
}

interface EnterpriseJobsResponse {
  success: true;
  jobs: EnterpriseJob[];
}

interface EnterpriseJobMutationResponse {
  success: boolean;
  id?: number;
  message: string;
}

interface EnterpriseApplicationsResponse {
  success: true;
  applications: EnterpriseApplication[];
}

export async function getEnterpriseStats(): Promise<EnterpriseStats> {
  const response = await get<EnterpriseStatsResponse>("/api/enterprise/stats");
  return response.stats;
}

export async function getEnterpriseJobs(): Promise<EnterpriseJob[]> {
  const response = await get<EnterpriseJobsResponse>("/api/enterprise/jobs");
  return response.jobs;
}

export function createEnterpriseJob(
  input: EnterpriseJobInput,
): Promise<EnterpriseJobMutationResponse> {
  return post<EnterpriseJobMutationResponse>("/api/enterprise/jobs", input);
}

export function updateEnterpriseJob(
  jobId: number,
  input: EnterpriseJobInput,
): Promise<EnterpriseJobMutationResponse> {
  return put<EnterpriseJobMutationResponse>(
    `/api/enterprise/jobs/${jobId}`,
    input,
  );
}

export function deleteEnterpriseJob(
  jobId: number,
): Promise<EnterpriseJobMutationResponse> {
  return del<EnterpriseJobMutationResponse>(`/api/enterprise/jobs/${jobId}`);
}

export async function getEnterpriseApplications(): Promise<
  EnterpriseApplication[]
> {
  const response = await get<EnterpriseApplicationsResponse>(
    "/api/enterprise/applications",
  );
  return response.applications;
}

export function updateEnterpriseApplicationStatus(
  applicationId: number,
  status: "interview" | "approved" | "rejected",
): Promise<EnterpriseJobMutationResponse> {
  return put<EnterpriseJobMutationResponse>(
    `/api/enterprise/applications/${applicationId}`,
    { status },
  );
}
