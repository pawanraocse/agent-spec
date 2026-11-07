export type Provenance = "measured" | "estimated" | "demo_seed";

let cachedToken = "";

export function getToken(): string {
  if (cachedToken) return cachedToken;
  const meta = document.querySelector('meta[name="aspec-token"]');
  cachedToken = meta?.getAttribute("content") || "";
  return cachedToken;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    headers: { "X-Agent-Spec-Token": getToken() },
  });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Agent-Spec-Token": getToken(),
    },
    body: JSON.stringify(body),
  });
  return res.json() as Promise<T>;
}
