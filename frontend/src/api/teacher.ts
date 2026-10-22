import { del, get, post, put } from "./client";

export interface TeacherStats {
  total_students: number;
  certificates_earned: number;
  completion_rate: number;
  avg_score: number;
  no_cert_count: number;
}

export interface TeacherStudent {
  id: string;
  user_id: string;
  name: string;
  class_name: string;
  direction: string;
  progress: number;
  status: string;
  created_at?: string;
  cert_total: number;
  cert_earned: number;
  completion: number;
  has_cert_data: boolean;
}

export interface LinkableAccount {
  username: string;
  name: string;
}

export interface TeacherAnnouncement {
  id: number;
  title: string;
  content: string;
  category: string;
  pinned: number;
  created_at: string;
}

export interface ProgressDistribution {
  label: string;
  count: number;
}

export interface DirectionDistribution {
  direction: string;
  count: number;
}

export interface DirectionProgress {
  direction: string;
  student_count: number;
  avg_progress: number;
  cert_earned: number;
  no_cert_count: number;
}

export interface TeacherAnalytics {
  basis: string;
  basis_label: string;
  roster_count: number;
  no_cert_count: number;
  progress_distribution: ProgressDistribution[];
  direction_distribution: DirectionDistribution[];
  direction_progress: DirectionProgress[];
}

export interface TrainingTranscriptTurn {
  role: string;
  content: string;
}

export interface TeacherTraining {
  id: number;
  student_id: string;
  student_name: string;
  assignment_id: number;
  assignment_title: string;
  kind: string;
  product: string;
  attempts: number;
  score: number | null;
  rule_score: number | null;
  script: string;
  transcript: TrainingTranscriptTurn[];
  meta: Record<string, unknown>;
  script_len: number;
  feedback: string;
  status: string;
  status_label: string;
  submitted_at: string;
  graded_at: string;
  regrade_needed: boolean;
}

export interface TeacherTrainingList {
  trainings: TeacherTraining[];
  pending_regrade: number;
}

export interface TeacherReportOverview {
  title?: string;
  focus?: string;
  total?: number;
  avg_progress?: number;
  no_cert_count?: number;
  direction_count?: number;
  completed_count?: number;
  risk_count?: number;
  excellent_count?: number;
  at_risk?: Array<{ name: string; progress: number; direction: string }>;
  excellent?: Array<{ name: string; progress: number; direction: string }>;
  [key: string]: unknown;
}

export interface TeacherReport {
  title: string;
  generated_at: string;
  content: string;
  overview?: TeacherReportOverview;
  degraded: boolean;
  degraded_reason: "" | "ai_unavailable" | "no_roster_data";
}

export interface TeacherModel3d {
  id: number;
  title: string;
  description: string;
  craft_type: string;
  file_path: string;
  file_name: string;
  file_size: number;
  thumbnail_url: string;
  teacher_id: string;
  review_status: string;
  review_comment: string;
  reviewed_by: string;
  reviewed_at: string;
  is_published: number;
  created_at: string;
}

interface DashboardResponse {
  success: true;
  dashboard: { stats: TeacherStats };
}

interface StudentsResponse {
  success: true;
  students: TeacherStudent[];
}

interface StudentResponse {
  success: boolean;
  student?: TeacherStudent;
  message?: string;
}

interface LinkableAccountsResponse {
  success: true;
  accounts: LinkableAccount[];
}

interface AnnouncementsResponse {
  success: true;
  announcements: TeacherAnnouncement[];
}

interface AnnouncementMutationResponse {
  success: boolean;
  message: string;
  id?: number;
}

interface AnalyticsResponse {
  success: true;
  analytics: TeacherAnalytics;
}

interface TrainingsResponse {
  success: true;
  trainings: TeacherTraining[];
  pending_regrade: number;
}

interface ReportResponse {
  success: true;
  report: TeacherReport;
}

interface TeacherModels3dResponse {
  success: true;
  models: TeacherModel3d[];
}

interface MutationResponse {
  success: boolean;
  message: string;
}

export interface AddStudentPayload {
  name: string;
  class_name?: string;
  direction?: string;
  link_username?: string;
  new_username?: string;
  new_password?: string;
}

export interface UpdateStudentPayload {
  name: string;
  class_name?: string;
  direction: string;
  status: "active" | "suspended";
}

export interface AnnouncementPayload {
  title: string;
  content: string;
  category: string;
  pinned: boolean;
}

export interface GradePayload {
  submission_id: number;
  score: number;
  feedback: string;
}

export async function getTeacherStats(): Promise<TeacherStats> {
  const response = await get<DashboardResponse>("/api/teacher/dashboard");
  return response.dashboard.stats;
}

export async function getTeacherStudents(search = ""): Promise<TeacherStudent[]> {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  const response = await get<StudentsResponse>(`/api/teacher/students${query}`);
  return response.students;
}

export async function getTeacherStudent(studentId: string): Promise<TeacherStudent> {
  const response = await get<StudentResponse>(
    `/api/teacher/students/${encodeURIComponent(studentId)}`,
  );
  if (!response.success || !response.student) {
    throw new Error(response.message || "未找到学员");
  }
  return response.student;
}

export async function getLinkableAccounts(): Promise<LinkableAccount[]> {
  const response = await get<LinkableAccountsResponse>(
    "/api/teacher/linkable-accounts",
  );
  return response.accounts;
}

export async function addTeacherStudent(
  payload: AddStudentPayload,
): Promise<MutationResponse & { student_id?: string; linked_account?: string }> {
  return post<MutationResponse & { student_id?: string; linked_account?: string }>(
    "/api/teacher/students/add",
    payload,
  );
}

export async function updateTeacherStudent(
  studentId: string,
  payload: UpdateStudentPayload,
): Promise<MutationResponse> {
  return put<MutationResponse>(
    `/api/teacher/students/${encodeURIComponent(studentId)}`,
    payload,
  );
}

export async function linkTeacherStudent(
  studentId: string,
  username: string,
): Promise<MutationResponse & { user_id?: string }> {
  return post<MutationResponse & { user_id?: string }>(
    `/api/teacher/students/${encodeURIComponent(studentId)}/link`,
    { username },
  );
}

export async function deleteTeacherStudent(
  studentId: string,
): Promise<MutationResponse> {
  return del<MutationResponse>(
    `/api/teacher/students/${encodeURIComponent(studentId)}`,
  );
}

export async function getTeacherAnnouncements(): Promise<TeacherAnnouncement[]> {
  const response = await get<AnnouncementsResponse>(
    "/api/teacher/announcements",
  );
  return response.announcements;
}

export async function createTeacherAnnouncement(
  payload: AnnouncementPayload,
): Promise<AnnouncementMutationResponse> {
  const response = await post<AnnouncementMutationResponse>(
    "/api/teacher/announcements",
    payload,
  );
  if (!response.success) throw new Error(response.message || "发布失败");
  return response;
}

export async function deleteTeacherAnnouncement(
  announcementId: number,
): Promise<MutationResponse> {
  const response = await del<MutationResponse>(
    `/api/teacher/announcements/${announcementId}`,
  );
  if (!response.success) throw new Error(response.message || "删除失败");
  return response;
}

export async function getTeacherAnalytics(): Promise<TeacherAnalytics> {
  const response = await get<AnalyticsResponse>("/api/teacher/analytics");
  return response.analytics;
}

export async function getTeacherTrainings(): Promise<TeacherTrainingList> {
  const response = await get<TrainingsResponse>("/api/teacher/trainings");
  return {
    trainings: response.trainings,
    pending_regrade: response.pending_regrade,
  };
}

export async function gradeTeacherTraining(
  payload: GradePayload,
): Promise<MutationResponse> {
  const response = await post<MutationResponse>(
    "/api/teacher/assignments/grade",
    payload,
  );
  if (!response.success) throw new Error(response.message || "批改失败");
  return response;
}

export async function generateTeacherReport(
  prompt: string,
): Promise<TeacherReport> {
  const response = await post<ReportResponse>(
    "/api/teacher/reports/generate",
    { prompt },
  );
  return response.report;
}

export async function getTeacherModels3d(): Promise<TeacherModel3d[]> {
  const response = await get<TeacherModels3dResponse>(
    "/api/teacher/models-3d",
  );
  return response.models;
}

export async function deleteTeacherModel3d(
  modelId: number,
): Promise<MutationResponse> {
  const response = await del<MutationResponse>(
    `/api/teacher/models-3d/${modelId}`,
  );
  if (!response.success) throw new Error(response.message || "删除失败");
  return response;
}
