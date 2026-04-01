import { apiClient } from "../client";
import type { AuthUser } from "@/lib/auth/session";

export interface LoginRequest {
  username_or_email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
}

export const authApi = {
  login: (request: LoginRequest) =>
    apiClient.post<LoginResponse>("/api/v1/auth/login", request, { auth: false }),

  me: () => apiClient.get<AuthUser>("/api/v1/auth/me"),
};
