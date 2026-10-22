import { del, get, post, put } from "./client";

export interface PolicySource {
  title: string;
  url?: string;
}

export interface GovernmentPolicy {
  id: number;
  title: string;
  content: string;
  category: string;
  author_id: string;
  is_published: number;
  date: string;
  summary: string;
  sources: PolicySource[];
  created_at: string;
  updated_at: string;
}

export interface GovernmentPolicyInput {
  title: string;
  content: string;
  category: string;
  summary: string;
  date: string;
  source: string;
}

export interface PolicyStatusCount {
  total: number;
  published: number;
  unpublished: number;
}

export interface GovernmentOverview {
  policies: {
    own: PolicyStatusCount;
    preset: PolicyStatusCount;
    categories: Array<{ category: string; count: number }>;
  };
  cases: {
    total: number;
    approved: number;
    pending: number;
    rejected: number;
    regions: Array<{ region: string; count: number }>;
    source_total: number;
    avg_sources: number;
    items: Array<{
      id: number;
      title: string;
      region: string;
      sources: number;
    }>;
  };
}

export interface GovernmentActionResponse {
  success: true;
  id?: number;
  message: string;
}

interface GovernmentOverviewResponse {
  success: true;
  overview: GovernmentOverview;
}

interface GovernmentPoliciesResponse {
  success: true;
  policies: GovernmentPolicy[];
}

export async function getGovernmentOverview(): Promise<GovernmentOverview> {
  const response = await get<GovernmentOverviewResponse>(
    "/api/government/dashboard",
  );
  return response.overview;
}

export async function getGovernmentPolicies(): Promise<GovernmentPolicy[]> {
  const response = await get<GovernmentPoliciesResponse>(
    "/api/government/policies",
  );
  return response.policies;
}

export function createGovernmentPolicy(
  policy: GovernmentPolicyInput,
): Promise<GovernmentActionResponse> {
  return post<GovernmentActionResponse>(
    "/api/government/policies",
    policy,
  );
}

export function updateGovernmentPolicy(
  policyId: number,
  policy: Partial<GovernmentPolicyInput> & { is_published?: number },
): Promise<GovernmentActionResponse> {
  return put<GovernmentActionResponse>(
    `/api/government/policies/${policyId}`,
    policy,
  );
}

export function deleteGovernmentPolicy(
  policyId: number,
): Promise<GovernmentActionResponse> {
  return del<GovernmentActionResponse>(
    `/api/government/policies/${policyId}`,
  );
}
