import { del, get, post, put } from "./client";
import type { Role } from "./types";

export interface AdminOverview {
  users: {
    total: number;
    suspended: number;
    student?: number;
    teacher?: number;
    enterprise?: number;
    government?: number;
    operator?: number;
    super_admin?: number;
  };
  reviews: {
    pending: number;
    approved: number;
    rejected: number;
    oldest_pending_at: string | null;
    oldest_pending_days: number | null;
  };
  content: {
    jobs?: number;
    jobs_published?: number;
    models?: number;
    courses?: number;
    policies?: number;
    policies_published?: number;
    announcements?: number;
    cases?: number | null;
  };
  pending_jobs: number;
  pending_reviews: number;
}

export interface UserRelation {
  table: string;
  column: string;
  label: string;
  count: number;
}

export interface AdminUser {
  username: string;
  name: string;
  role: Role;
  status: string;
  email: string;
  phone: string;
  created_at: string;
  relation_count: number;
  relations: UserRelation[];
  can_delete: boolean;
  can_suspend: boolean;
  block_reason: string;
}

export interface AdminUserUpdate {
  name?: string;
  role?: Role;
  status?: "active" | "suspended";
  phone?: string;
  email?: string;
}

export interface AdminActionResponse {
  success: true;
  message: string;
}

export type ReviewContentType =
  | "course"
  | "job"
  | "model_3d"
  | "success_case";

export type ReviewStatus = "pending" | "approved" | "rejected";

export interface AdminReviewDetail {
  id?: number;
  title?: string;
  name?: string;
  description?: string;
  company?: string;
  salary?: string;
  location?: string;
  region?: string;
  craft_type?: string;
  file_name?: string;
  file_path?: string;
  requirements?: string[] | string;
  [key: string]: unknown;
}

export interface AdminReview {
  id: number;
  content_type: ReviewContentType | string;
  content_id: number;
  submitter_id: string;
  status: ReviewStatus | string;
  review_comment: string;
  reviewed_by: string;
  reviewed_at: string | null;
  created_at: string;
  detail: AdminReviewDetail | null;
  is_self_reviewed: boolean;
}

export interface ReviewCounts {
  pending: number;
  approved: number;
  rejected: number;
}

export interface AdminAnnouncement {
  id: number;
  title: string;
  content: string;
  is_pinned: number;
  is_active: number;
  created_by: string;
  created_at: string;
}

export interface ModerationDiscussion {
  id: number;
  title: string;
  content: string;
  category: string;
  user_id: string;
  user_name: string;
  comment_count: number;
  is_pinned: number;
  created_at: string;
}

export interface ModerationComment {
  id: number;
  target_type: string;
  target_id: number;
  target_title: string;
  user_id: string;
  user_name: string;
  content: string;
  created_at: string;
}

export interface ModerationContent {
  discussions: ModerationDiscussion[];
  comments: ModerationComment[];
  total: number;
}

interface AdminOverviewResponse {
  success: true;
  overview: AdminOverview;
}

interface AdminUsersResponse {
  success: true;
  users: AdminUser[];
}

interface AdminReviewsResponse {
  success: true;
  reviews: AdminReview[];
  counts: ReviewCounts;
  status: string;
}

interface AdminAnnouncementsResponse {
  success: true;
  announcements: AdminAnnouncement[];
}

interface AdminAnnouncementMutationResponse extends AdminActionResponse {
  id?: number;
}

interface AdminModerationResponse {
  success: true;
  discussions: ModerationDiscussion[];
  comments: ModerationComment[];
  total: number;
}

export async function getAdminOverview(): Promise<AdminOverview> {
  const response = await get<AdminOverviewResponse>("/api/admin/dashboard");
  return response.overview;
}

export async function getAdminUsers(options?: {
  search?: string;
  role?: string;
}): Promise<AdminUser[]> {
  const params = new URLSearchParams();
  if (options?.search) params.set("search", options.search);
  if (options?.role) params.set("role", options.role);
  const query = params.size ? `?${params.toString()}` : "";
  const response = await get<AdminUsersResponse>(`/api/admin/users${query}`);
  return response.users;
}

export function updateAdminUser(
  username: string,
  update: AdminUserUpdate,
): Promise<AdminActionResponse> {
  return put<AdminActionResponse>(
    `/api/admin/users/${encodeURIComponent(username)}`,
    update,
  );
}

export function setAdminUserStatus(
  username: string,
  status: "active" | "suspended",
): Promise<AdminActionResponse> {
  return post<AdminActionResponse>(
    `/api/admin/users/${encodeURIComponent(username)}/status`,
    { status },
  );
}

export function deleteAdminUser(
  username: string,
): Promise<AdminActionResponse> {
  return del<AdminActionResponse>(
    `/api/admin/users/${encodeURIComponent(username)}`,
  );
}

export async function getAdminReviews(options?: {
  status?: ReviewStatus | "all";
  contentType?: ReviewContentType | "";
  sort?: "modified" | "created";
}): Promise<AdminReviewsResponse> {
  const params = new URLSearchParams();
  params.set("status", options?.status ?? "pending");
  params.set("sort", options?.sort ?? "modified");
  if (options?.contentType) params.set("content_type", options.contentType);
  return get<AdminReviewsResponse>(
    `/api/admin/reviews?${params.toString()}`,
  );
}

export function approveAdminReview(
  reviewId: number,
): Promise<AdminActionResponse> {
  return post<AdminActionResponse>(
    `/api/admin/reviews/${reviewId}/approve`,
    {},
  );
}

export function rejectAdminReview(
  reviewId: number,
  comment: string,
): Promise<AdminActionResponse> {
  return post<AdminActionResponse>(
    `/api/admin/reviews/${reviewId}/reject`,
    { comment },
  );
}

export function revokeAdminReview(
  reviewId: number,
): Promise<AdminActionResponse> {
  return post<AdminActionResponse>(
    `/api/admin/reviews/${reviewId}/revoke`,
    {},
  );
}

export async function getAdminAnnouncements(): Promise<AdminAnnouncement[]> {
  const response = await get<AdminAnnouncementsResponse>(
    "/api/admin/system-announcements",
  );
  return response.announcements;
}

export function createAdminAnnouncement(payload: {
  title: string;
  content: string;
  is_pinned: boolean;
}): Promise<AdminAnnouncementMutationResponse> {
  return post<AdminAnnouncementMutationResponse>(
    "/api/admin/system-announcements",
    {
      title: payload.title,
      content: payload.content,
      is_pinned: payload.is_pinned ? 1 : 0,
    },
  );
}

export function deleteAdminAnnouncement(
  announcementId: number,
): Promise<AdminActionResponse> {
  return del<AdminActionResponse>(
    `/api/admin/system-announcements/${announcementId}`,
  );
}

export async function getAdminModerationContent(): Promise<ModerationContent> {
  const response = await get<AdminModerationResponse>("/api/admin/content");
  return {
    discussions: response.discussions,
    comments: response.comments,
    total: response.total,
  };
}

export function deleteAdminComment(
  commentId: number,
): Promise<AdminActionResponse> {
  return del<AdminActionResponse>(`/api/admin/comments/${commentId}`);
}

export function deleteAdminDiscussion(
  discussionId: number,
): Promise<AdminActionResponse> {
  return del<AdminActionResponse>(`/api/admin/discussions/${discussionId}`);
}
