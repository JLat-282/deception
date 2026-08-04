import type {
  AttemptResponse,
  BootstrapResponse,
  ErrorResponse,
  GameMode,
  StartGameResponse,
  TimedOutResponse,
} from "./types";

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim();
const API_BASE = configuredBase ? configuredBase.replace(/\/$/, "") : "";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(
      "NETWORK_ERROR",
      "The game service is unavailable. Check that the local API is running.",
      0,
    );
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = isErrorResponse(payload)
      ? payload.error
      : {
          code: "SERVICE_UNAVAILABLE",
          message: "The game service returned an unexpected response.",
        };
    throw new ApiError(error.code, error.message, response.status);
  }
  return payload as T;
}

function isErrorResponse(payload: unknown): payload is ErrorResponse {
  if (!payload || typeof payload !== "object" || !("error" in payload)) {
    return false;
  }
  const error = (payload as { error?: unknown }).error;
  return (
    !!error &&
    typeof error === "object" &&
    "code" in error &&
    "message" in error &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

let bootstrapRequest: Promise<BootstrapResponse> | null = null;

function bootstrap(): Promise<BootstrapResponse> {
  if (!bootstrapRequest) {
    bootstrapRequest = request<BootstrapResponse>("/api/bootstrap").finally(
      () => {
        bootstrapRequest = null;
      },
    );
  }
  return bootstrapRequest;
}

export const api = {
  bootstrap,
  startGame: (mode: GameMode, presetKey?: string, continuationToken?: string) =>
    request<StartGameResponse>("/api/games", {
      method: "POST",
      body: JSON.stringify({
        mode,
        ...(presetKey ? { presetKey } : {}),
        ...(continuationToken ? { continuationToken } : {}),
      }),
    }),
  submitGuess: (gameId: string, guess: string, continuationToken?: string) =>
    request<AttemptResponse>(`/api/games/${gameId}/guesses`, {
      method: "POST",
      body: JSON.stringify({
        guess,
        ...(continuationToken ? { continuationToken } : {}),
      }),
    }),
  expireTimer: (gameId: string, continuationToken?: string) =>
    request<TimedOutResponse>(`/api/games/${gameId}/timer/expire`, {
      method: "POST",
      body: JSON.stringify(continuationToken ? { continuationToken } : {}),
    }),
};
