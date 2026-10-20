import { get } from "./client";

export interface HomeStats {
  farmers: number;
  courses: number;
  jobs: number;
}

export interface HomeStatsResponse {
  success: true;
  stats: HomeStats;
}

export function getHomeStats(): Promise<HomeStatsResponse> {
  return get<HomeStatsResponse>("/api/home/stats");
}
