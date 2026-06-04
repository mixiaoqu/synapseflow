import { request } from "@/shared/api/http";
import type { CurrentUser, LoginPayload, LoginResponse } from "@/shared/types/auth";

export function login(payload: LoginPayload) {
  return request<
    LoginResponse,
    {
      username_or_email: string;
      password: string;
    }
  >({
    url: "/auth/login",
    method: "POST",
    data: {
      username_or_email: payload.usernameOrEmail,
      password: payload.password,
    },
  });
}

export function getCurrentUser() {
  return request<CurrentUser>({
    url: "/auth/me",
    method: "GET",
  });
}
