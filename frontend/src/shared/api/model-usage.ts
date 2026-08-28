import { request } from "@/shared/api/http";

export type ModelUsageGranularity = "day" | "week" | "month";

export interface ModelUsageModelDetail {
  name: string;
  share: number;
  tone: "blue" | "green" | "purple" | "slate";
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: string;
}

export interface ModelUsageRow {
  id: string;
  team_id: number | null;
  team: string;
  application: string;
  product_id: number | null;
  product_name: string | null;
  project_id: number | null;
  project_name: string | null;
  project_app_id: number | null;
  project_app_name: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  chat_tokens: number;
  evaluation_tokens: number;
  estimated_cost: number;
  models: ModelUsageModelDetail[];
  coverage: number;
  coverage_status: "complete" | "partial";
}

export interface ModelUsageSummary {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  chat_tokens: number;
  evaluation_tokens: number;
}

export interface ModelUsageTrendPoint {
  label: string;
  date: string;
  total_tokens: number;
  estimated_cost: number;
  chat_tokens: number;
  evaluation_tokens: number;
}

export interface ModelUsageSummaryResponse {
  summary: ModelUsageSummary;
  rows: ModelUsageRow[];
  trend: ModelUsageTrendPoint[];
  start_date: string;
  end_date: string;
  granularity: ModelUsageGranularity;
  updated_at: string;
}

export function getModelUsageSummary(params: {
  start_date: string;
  end_date: string;
  team_id?: number | null;
  granularity: ModelUsageGranularity;
}) {
  return request<ModelUsageSummaryResponse>({
    url: "/admin/qa/cost-summary",
    method: "GET",
    params: {
      start_date: params.start_date,
      end_date: params.end_date,
      granularity: params.granularity,
      ...(params.team_id ? { team_id: params.team_id } : {}),
    },
  });
}
