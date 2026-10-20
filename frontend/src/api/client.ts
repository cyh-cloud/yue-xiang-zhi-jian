import axios, { AxiosError, type AxiosRequestConfig, type AxiosResponse } from "axios";

export interface ApiFailure {
  status: number;
  code: string | null;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(failure: ApiFailure) {
    super(failure.message);
    this.name = "ApiError";
    this.status = failure.status;
    this.code = failure.code;
  }
}

const http = axios.create({
  baseURL: "",
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

let sessionId = "";

export function setApiSessionId(nextSessionId: string | null): void {
  sessionId = nextSessionId ?? "";
}

http.interceptors.request.use((config) => {
  if (sessionId) {
    config.headers.set("X-Session-Id", sessionId);
  }
  return config;
});

export async function apiRequest<T>(
  config: AxiosRequestConfig,
): Promise<T> {
  try {
    const response = await http.request<T>(config);
    notifyConnectionState(false);
    return response.data;
  } catch (error) {
    const normalized = normalizeApiError(error);
    if (normalized.status === 0) notifyConnectionState(true);
    throw normalized;
  }
}

export function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return apiRequest<T>({ ...config, method: "GET", url });
}

export function post<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return apiRequest<T>({ ...config, method: "POST", url, data });
}

export function put<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return apiRequest<T>({ ...config, method: "PUT", url, data });
}

export function del<T>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  return apiRequest<T>({ ...config, method: "DELETE", url });
}

export function postForm<T>(
  url: string,
  form: FormData,
  config?: AxiosRequestConfig,
): Promise<T> {
  return apiRequest<T>({
    ...config,
    method: "POST",
    url,
    data: form,
    headers: {
      // Undo the instance-wide JSON default. Axios then lets the browser
      // generate multipart/form-data with its boundary.
      "Content-Type": null,
      ...config?.headers,
    },
  });
}

function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof AxiosError) {
    const response: AxiosResponse<unknown> | undefined = error.response;
    const body = isRecord(response?.data) ? response.data : null;
    const code = typeof body?.code === "string" ? body.code : null;
    const message =
      (typeof body?.message === "string" && body.message) ||
      error.message ||
      "请求失败";
    return new ApiError({
      status: response?.status ?? 0,
      code,
      message,
    });
  }
  return new ApiError({
    status: 0,
    code: null,
    message: error instanceof Error ? error.message : "请求失败",
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function notifyConnectionState(unavailable: boolean): void {
  window.dispatchEvent(
    new CustomEvent("yuexiang:connection", {
      detail: { unavailable },
    }),
  );
}
