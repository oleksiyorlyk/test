export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: string,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options?.headers },
    });
  } catch {
    throw new ApiError(
      0,
      "OFFLINE",
      "Backend nie je dostupný. Skontrolujte stav servera alebo kontajnera.",
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      response.status,
      body?.error?.code || "ERROR",
      body?.error?.message || "Požiadavka zlyhala.",
      body?.error?.details,
    );
  return body;
}
export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
