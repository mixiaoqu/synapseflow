import { apiClient } from "./client";

export interface AdminUserItem {
  id: number;
  username: string;
  email: string;
  full_name?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export async function listUsers(): Promise<AdminUserItem[]> {
  return apiClient.get("/api/v1/users");
}

export async function createUser(payload: {
  username: string;
  email: string;
  password: string;
  full_name?: string | null;
  role: string;
  is_active?: boolean;
}): Promise<AdminUserItem> {
  return apiClient.post("/api/v1/users", payload);
}

export async function updateUser(
  userId: number,
  payload: {
    username?: string;
    email?: string;
    password?: string;
    full_name?: string | null;
    role?: string;
    is_active?: boolean;
  },
): Promise<AdminUserItem> {
  return apiClient.put(`/api/v1/users/${userId}`, payload);
}
