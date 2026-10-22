import { get } from "./client";

export interface CraftSummary {
  id: string;
  name: string;
  origin: string;
  level: string;
}

export interface CraftStep {
  title: string;
  desc: string;
  tips: string;
}

export interface CraftVideo {
  id: number;
  bvid: string;
  title: string;
  author: string;
  duration: number;
  view: number;
  danmaku: number;
  like: number;
  pubdate: number;
  cover: string;
}

export interface CraftPurchaseItem {
  name: string;
  price: string;
  spec: string;
  tip: string;
  where: string;
}

export interface CraftPurchaseCategory {
  key: string;
  label: string;
  desc: string;
  items: CraftPurchaseItem[];
}

export interface CraftPurchaseGuide {
  budget: {
    starter: string;
    advanced: string;
  } | null;
  buying_tips: string;
  categories: CraftPurchaseCategory[];
}

export interface CraftDetail {
  name: string;
  origin: string;
  history: string;
  videos: CraftVideo[];
  steps: CraftStep[];
  purchase_guide: CraftPurchaseGuide | null;
}

export interface CraftListResponse {
  success: true;
  crafts: CraftSummary[];
}

export interface CraftDetailResponse {
  success: boolean;
  data?: CraftDetail;
  message?: string;
}

export interface PublicModel3D {
  id: number;
  title: string;
  description: string;
  craft_type: string;
  file_path: string;
  file_name: string;
  file_size: number;
  thumbnail_url: string;
  review_status: string;
  is_published: number;
  created_at: string;
}

export interface PublicModels3DResponse {
  success: true;
  models: PublicModel3D[];
}

export function getCrafts(): Promise<CraftListResponse> {
  return get<CraftListResponse>("/api/crafts/list");
}

export function getCraftDetail(craftId: string): Promise<CraftDetailResponse> {
  return get<CraftDetailResponse>(
    `/api/crafts/${encodeURIComponent(craftId)}`,
  );
}

export function getPublicModels3D(
  craftType: string,
): Promise<PublicModels3DResponse> {
  return get<PublicModels3DResponse>(
    `/api/teacher/public-models-3d?craft_type=${encodeURIComponent(craftType)}`,
  );
}
