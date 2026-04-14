import { apiClient } from "./client";

export interface SensitiveWordSettings {
  id?: number | null;
  team_id?: number | null;
  enabled: boolean;
  block_query: boolean;
  block_document_publish: boolean;
  created_by_user_id?: number | null;
  updated_by_user_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SensitiveWordItem {
  id: number;
  team_id?: number | null;
  word: string;
  normalized_word: string;
  category?: string | null;
  match_mode: string;
  enabled: boolean;
  remark?: string | null;
  created_by_user_id?: number | null;
  updated_by_user_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface SensitiveWordListResponse {
  items: SensitiveWordItem[];
  total: number;
  enabled_count: number;
  disabled_count: number;
  page: number;
  page_size: number;
}

export interface SensitiveWordCheckResult {
  blocked: boolean;
  matched_words: string[];
  scene: string;
  reason?: string | null;
}

function buildScopeQuery(teamId?: number | null): string {
  return teamId == null ? "" : `?team_id=${teamId}`;
}

function buildWordListQuery(params: {
  teamId?: number | null;
  keyword?: string;
  enabled?: boolean | null;
  page?: number;
  pageSize?: number;
}): string {
  const search = new URLSearchParams();
  if (params.teamId != null) {
    search.set("team_id", String(params.teamId));
  }
  if (params.keyword?.trim()) {
    search.set("keyword", params.keyword.trim());
  }
  if (typeof params.enabled === "boolean") {
    search.set("enabled", String(params.enabled));
  }
  if (typeof params.page === "number") {
    search.set("page", String(params.page));
  }
  if (typeof params.pageSize === "number") {
    search.set("page_size", String(params.pageSize));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export async function getSensitiveWordSettings(
  teamId?: number | null,
): Promise<SensitiveWordSettings> {
  return apiClient.get(`/api/v1/sensitive-words/settings${buildScopeQuery(teamId)}`);
}

export async function updateSensitiveWordSettings(
  payload: Pick<SensitiveWordSettings, "enabled" | "block_query" | "block_document_publish">,
  teamId?: number | null,
): Promise<SensitiveWordSettings> {
  return apiClient.put(
    `/api/v1/sensitive-words/settings${buildScopeQuery(teamId)}`,
    payload,
  );
}

export async function listSensitiveWords(params: {
  teamId?: number | null;
  keyword?: string;
  enabled?: boolean | null;
  page?: number;
  pageSize?: number;
}): Promise<SensitiveWordListResponse> {
  return apiClient.get(`/api/v1/sensitive-words${buildWordListQuery(params)}`);
}

export async function createSensitiveWord(payload: {
  team_id?: number | null;
  word: string;
  category?: string | null;
  enabled?: boolean;
  remark?: string | null;
}): Promise<SensitiveWordItem> {
  return apiClient.post("/api/v1/sensitive-words", payload);
}

export async function updateSensitiveWord(
  wordId: number,
  payload: {
    word: string;
    category?: string | null;
    enabled?: boolean;
    remark?: string | null;
  },
): Promise<SensitiveWordItem> {
  return apiClient.put(`/api/v1/sensitive-words/${wordId}`, payload);
}

export async function deleteSensitiveWord(wordId: number): Promise<{ message: string }> {
  return apiClient.delete(`/api/v1/sensitive-words/${wordId}`);
}

export async function importSensitiveWords(payload: {
  team_id?: number | null;
  words_text: string;
  category?: string | null;
  enabled?: boolean;
}): Promise<{
  created_count: number;
  skipped_count: number;
  items: SensitiveWordItem[];
}> {
  return apiClient.post("/api/v1/sensitive-words/import", payload);
}

export async function checkSensitiveWords(payload: {
  text: string;
  team_id?: number | null;
  scene?: string;
}): Promise<SensitiveWordCheckResult> {
  return apiClient.post("/api/v1/sensitive-words/check", payload);
}
