import { get, post, postForm, apiRequest } from "./client";

export interface QualificationRecord {
  id: number;
  company_name: string;
  credit_code_masked: string;
  legal_person: string;
  contact_phone: string;
  address: string;
  industry: string;
  company_size: string;
  status: "pending" | "approved" | "rejected";
  status_label: string;
  review_comment: string;
  submitted_at: string;
  reviewed_at: string;
  expires_at: string;
  has_license: boolean;
  license_name: string;
}

export type QualificationState =
  | "none"
  | "pending"
  | "approved"
  | "rejected"
  | "withdrawn"
  | "expired";

export interface QualificationStatus {
  status: QualificationState;
  status_label: string;
  verified: boolean;
  record: QualificationRecord | null;
  limits: { unverified_active_jobs: number };
}

export interface QualificationSubmission {
  company_name: string;
  credit_code: string;
  legal_person: string;
  contact_phone: string;
  address: string;
  industry: string;
  company_size: string;
  license: File | null;
}

export interface QualificationMutationResponse {
  success: boolean;
  id?: number;
  message: string;
}

interface QualificationStatusResponse extends QualificationStatus {
  success: true;
}

export interface AdminQualification extends QualificationRecord {
  user_id: string;
  applicant_name: string;
  applicant_phone: string;
  account_company_name: string;
  reviewed_by: string;
  name_matches_account: boolean;
}

export interface AdminQualificationList {
  status: string;
  pending_count: number;
  items: AdminQualification[];
  reject_reasons: string[];
}

interface AdminQualificationListResponse extends AdminQualificationList {
  success: true;
}

export async function getQualification(): Promise<QualificationStatus> {
  const response = await get<QualificationStatusResponse>(
    "/api/enterprise/qualification",
  );
  return response;
}

export function submitQualification(
  payload: QualificationSubmission,
): Promise<QualificationMutationResponse> {
  const form = new FormData();
  form.append("company_name", payload.company_name.trim());
  form.append("credit_code", payload.credit_code.trim());
  form.append("legal_person", payload.legal_person.trim());
  form.append("contact_phone", payload.contact_phone.trim());
  form.append("address", payload.address.trim());
  form.append("industry", payload.industry.trim());
  form.append("company_size", payload.company_size.trim());
  if (payload.license) form.append("license", payload.license);
  return postForm<QualificationMutationResponse>(
    "/api/enterprise/qualification",
    form,
  );
}

export function withdrawQualification(): Promise<QualificationMutationResponse> {
  return post<QualificationMutationResponse>(
    "/api/enterprise/qualification/withdraw",
  );
}

export async function getAdminQualifications(
  status: "pending" | "approved" | "rejected" | "all",
): Promise<AdminQualificationList> {
  const response = await get<AdminQualificationListResponse>(
    `/api/admin/qualifications?status=${status}`,
  );
  return response;
}

export function reviewQualification(
  id: number,
  status: "approved" | "rejected",
  comment: string,
): Promise<QualificationMutationResponse> {
  return post<QualificationMutationResponse>(
    `/api/admin/qualifications/${id}/review`,
    { status, comment },
  );
}

/**
 * 证件照走鉴权接口，不能直接塞进 <img src>（<img> 不会带 X-Session-Id）。
 * 取回 blob 再转 object URL，用完记得 revoke，否则每打开一次泄一个内存对象。
 */
export async function fetchLicenseObjectUrl(url: string): Promise<string> {
  const blob = await apiRequest<Blob>({
    url,
    method: "GET",
    responseType: "blob",
  });
  return URL.createObjectURL(blob);
}

export const enterpriseLicenseUrl = "/api/enterprise/qualification/license";

export function adminLicenseUrl(id: number): string {
  return `/api/admin/qualifications/${id}/license`;
}
