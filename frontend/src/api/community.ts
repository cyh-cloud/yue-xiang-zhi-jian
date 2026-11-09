import { get, post } from "./client";

export const DISCUSSION_TITLE_MAX_LEN = 80;
export const DISCUSSION_CONTENT_MAX_LEN = 5000;
export const COMMENT_CONTENT_MAX_LEN = 1000;
export const DISCUSSION_PAGE_SIZE = 20;

export type DiscussionCategory =
  | "general"
  | "agriculture"
  | "ecommerce"
  | "crafts";

export interface Discussion {
  id: number;
  title: string;
  content: string;
  category: string;
  user_id: string;
  user_name: string;
  is_pinned: number;
  is_deleted: number;
  view_count: number;
  comment_count: number;
  created_at: string;
  /** 1 = 平台预置的演示帖，界面上要打「演示」标。 */
  is_demo?: number;
}

export interface DiscussionComment {
  id: number;
  target_type: string;
  target_id: number;
  user_id: string;
  user_name: string;
  content: string;
  created_at: string;
}

export interface DiscussionListResponse {
  success: true;
  discussions: Discussion[];
  total: number;
}

export interface DiscussionDetailResponse {
  success: true;
  discussion: Discussion;
  comments: DiscussionComment[];
}

export interface CommunityMutationResponse {
  success: true;
  id: number;
  message: string;
  /** true = 命中敏感词，已转人工审核，不会立即出现在公开列表。 */
  pending?: boolean;
  /** 命中的词，仅用于提示用户改哪几句。 */
  matched?: string[];
}

export function getDiscussions(
  category = "",
  page = 1,
): Promise<DiscussionListResponse> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return get<DiscussionListResponse>(
    `/api/discussions${query ? `?${query}` : ""}`,
  );
}

export function getDiscussion(
  discussionId: number,
): Promise<DiscussionDetailResponse> {
  return get<DiscussionDetailResponse>(`/api/discussions/${discussionId}`);
}

export function createDiscussion(payload: {
  title: string;
  content: string;
  category: DiscussionCategory;
}): Promise<CommunityMutationResponse> {
  return post<CommunityMutationResponse>("/api/discussions", payload);
}

export function createComment(payload: {
  target_type: "discussion";
  target_id: number;
  content: string;
}): Promise<CommunityMutationResponse> {
  return post<CommunityMutationResponse>("/api/comments", payload);
}
