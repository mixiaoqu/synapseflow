import axios, {
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";

import { apiConfig } from "@/shared/api/config";
import { clearAuthSession, getAccessToken } from "@/shared/auth/session";
import { normalizeError } from "@/shared/utils/error";

// Axios 1.x 的 headers 在不同运行态下可能是对象或带 set 方法的实例，这里统一兼容。
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

  // 统一在请求层注入后台 access token，业务代码不再重复处理鉴权头。
  if (token) {
    setRequestHeader(config, "Authorization", `Bearer ${token}`);
  }

  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const normalizedError = normalizeError(error);

    // 401 统一视为会话失效，前端立即清空本地凭证，后续由路由守卫引导回登录页。
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
