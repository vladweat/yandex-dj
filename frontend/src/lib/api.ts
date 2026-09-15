import type {
  AuthMeResponse,
  DeviceFlowPollRequest,
  DeviceFlowPollResponse,
  DeviceFlowStartResponse,
} from "@/types/auth";
import type { HealthResponse } from "@/types/health";
import type {
  PlaylistGenerateRequest,
  PlaylistGenerateResponse,
  PlaylistHistoryResponse,
} from "@/types/playlist";
import type { YandexStatusResponse } from "@/types/yandex";

const CONFIGURED_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const API_V1 = "/api/v1";
export const SESSION_STORAGE_KEY = "prompt_dj_session_id";

export function apiUrl(): string {
  return CONFIGURED_API_URL;
}

function v1Path(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${API_V1}${suffix}`;
}

function v1Url(path: string): string {
  return `${apiUrl()}${v1Path(path)}`;
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((item: { msg: string }) => item.msg).join(", ");
    }
  } catch {
    // ignore parse errors
  }
  return `API error: ${response.status}`;
}

export function getSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SESSION_STORAGE_KEY);
}

export function setSessionId(sessionId: string): void {
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

export function clearSessionId(): void {
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

async function authorizedFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  const isFormData = options.body instanceof FormData;
  if (!headers.has("Content-Type") && options.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  const sessionId = getSessionId();
  if (sessionId) {
    headers.set("Authorization", `Bearer ${sessionId}`);
  }
  headers.set("X-Requested-With", "PromptDJ");
  const init: RequestInit = {
    ...options,
    headers,
    cache: "no-store",
  };
  return fetch(v1Url(path), init);
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await authorizedFetch(path, options);
  } catch {
    throw new ApiRequestError("API недоступен", 0);
  }

  if (!response.ok) {
    const message = await parseError(response);
    throw new ApiRequestError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(v1Url("/health"), {
    cache: "no-store",
    headers: { "X-Requested-With": "PromptDJ" },
  });
  if (!response.ok) {
    throw new ApiRequestError(await parseError(response), response.status);
  }
  return response.json();
}

export async function startDeviceFlow(): Promise<DeviceFlowStartResponse> {
  const response = await fetch(v1Url("/auth/device-flow/start"), {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "PromptDJ",
    },
  });
  if (!response.ok) {
    throw new ApiRequestError(await parseError(response), response.status);
  }
  return response.json();
}

export async function pollDeviceFlow(
  body: DeviceFlowPollRequest,
): Promise<DeviceFlowPollResponse> {
  const response = await fetch(v1Url("/auth/device-flow/poll"), {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "PromptDJ",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiRequestError(await parseError(response), response.status);
  }
  return response.json();
}

export async function fetchMe(): Promise<AuthMeResponse> {
  return apiFetch<AuthMeResponse>("/auth/me");
}

export async function fetchYandexAccount(): Promise<YandexStatusResponse> {
  return apiFetch<YandexStatusResponse>("/yandex/account");
}

export async function generatePlaylist(
  body: PlaylistGenerateRequest,
): Promise<PlaylistGenerateResponse> {
  return apiFetch<PlaylistGenerateResponse>("/playlists/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listPlaylists(
  limit = 20,
  offset = 0,
): Promise<PlaylistHistoryResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return apiFetch<PlaylistHistoryResponse>(`/playlists?${params.toString()}`);
}

export async function getPlaylist(id: string): Promise<PlaylistGenerateResponse> {
  return apiFetch<PlaylistGenerateResponse>(`/playlists/${id}`);
}
