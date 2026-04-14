import { clearAuthSession, getAccessToken } from "@/lib/auth/session";
import { parseApiError } from "./errors";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RequestOptions {
  auth?: boolean;
  headers?: HeadersInit;
}

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private buildHeaders(
    headers?: HeadersInit,
    auth: boolean = true,
    isForm: boolean = false,
  ): Headers {
    const nextHeaders = new Headers(headers);

    if (!isForm && !nextHeaders.has("Content-Type")) {
      nextHeaders.set("Content-Type", "application/json");
    }

    if (auth) {
      const token = getAccessToken();
      if (token && !nextHeaders.has("Authorization")) {
        nextHeaders.set("Authorization", `Bearer ${token}`);
      }
    }

    return nextHeaders;
  }

  private async handleFailure(response: Response, auth: boolean): Promise<never> {
    if (auth && response.status === 401) {
      clearAuthSession();
    }
    throw new Error(await parseApiError(response));
  }

  async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    const auth = options?.auth ?? true;
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "GET",
      headers: this.buildHeaders(options?.headers, auth, false),
    });

    if (!response.ok) {
      return this.handleFailure(response, auth);
    }

    return response.json();
  }

  async post<T>(endpoint: string, data: unknown, options?: RequestOptions): Promise<T> {
    const auth = options?.auth ?? true;
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "POST",
      headers: this.buildHeaders(options?.headers, auth, false),
      body: data === undefined ? undefined : JSON.stringify(data),
    });

    if (!response.ok) {
      return this.handleFailure(response, auth);
    }

    return response.json();
  }

  async put<T>(endpoint: string, data: unknown, options?: RequestOptions): Promise<T> {
    const auth = options?.auth ?? true;
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "PUT",
      headers: this.buildHeaders(options?.headers, auth, false),
      body: data === undefined ? undefined : JSON.stringify(data),
    });

    if (!response.ok) {
      return this.handleFailure(response, auth);
    }

    return response.json();
  }

  async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    const auth = options?.auth ?? true;
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "DELETE",
      headers: this.buildHeaders(options?.headers, auth, false),
    });

    if (!response.ok) {
      return this.handleFailure(response, auth);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    return (text ? JSON.parse(text) : undefined) as T;
  }

  async postForm<T>(
    endpoint: string,
    formData: FormData,
    options?: RequestOptions,
  ): Promise<T> {
    const auth = options?.auth ?? true;
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "POST",
      headers: this.buildHeaders(options?.headers, auth, true),
      body: formData,
    });

    if (!response.ok) {
      return this.handleFailure(response, auth);
    }

    return response.json();
  }

  async postStream(
    endpoint: string,
    data: unknown,
    options?: RequestOptions,
  ): Promise<ReadableStream<Uint8Array>> {
    const auth = options?.auth ?? true;
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "POST",
      headers: this.buildHeaders(options?.headers, auth, false),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      return this.handleFailure(response, auth);
    }

    if (!response.body) {
      throw new Error("Empty response body");
    }

    return response.body;
  }
}

export const apiClient = new ApiClient();
