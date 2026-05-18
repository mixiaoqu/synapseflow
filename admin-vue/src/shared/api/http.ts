import axios, {
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";

import { apiConfig } from "@/shared/api/config";
import { normalizeError } from "@/shared/utils/error";
import { clearAuthSession, getAccessToken } from "@/shared/utils/session";

function setRequestHeader(config: InternalAxiosRequestConfig, key: string, value: string) {
  if (typeof config.headers.set === "function") {
    config.headers.set(key, value);
    return;
  }

  config.headers[key] = value;
}

export const http = axios.create({
  baseURL: apiConfig.baseURL,
  timeout: apiConfig.timeout,
});

http.interceptors.request.use((config) => {
  const token = getAccessToken();

  if (token) {
    setRequestHeader(config, "Authorization", `Bearer ${token}`);
  }

  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const normalizedError = normalizeError(error);

    if (normalizedError.status === 401) {
      clearAuthSession();
    }

    return Promise.reject(normalizedError);
  },
);

export async function request<TResponse, TData = unknown>(config: AxiosRequestConfig<TData>) {
  const response = await http.request<TResponse, AxiosResponse<TResponse>, TData>(config);
  return response.data;
}
