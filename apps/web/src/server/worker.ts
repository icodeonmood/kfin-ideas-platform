/** Calls from the web app to the worker's internal API, with the shared token (BLD-048). */
export class WorkerError extends Error {
  constructor(public status: number) {
    super(`worker answered ${status}`);
  }
}

export async function workerFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const base = process.env.WORKER_URL ?? "http://localhost:8000";
  const token = process.env.INTERNAL_API_TOKEN;
  if (!token) throw new Error("INTERNAL_API_TOKEN is not set");
  const headers = new Headers(init.headers);
  headers.set("X-Internal-Token", token);
  return fetch(`${base}${path}`, { ...init, headers, signal: init.signal ?? AbortSignal.timeout(10_000) });
}

export async function workerJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await workerFetch(path, init);
  if (!res.ok) throw new WorkerError(res.status);
  return (await res.json()) as T;
}
