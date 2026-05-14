/**
 * Thin fetch wrapper for Q-Silicon API (queue 26c): base URL + silicon headers.
 * Hooks should keep React Query wiring in `useApi.js`; this module is transport-only.
 */

import { mergeSiliconHeaders } from "./siliconApiHeaders";

const BASE = import.meta.env.VITE_API_URL ?? "";

function buildUrl(path) {
  const p = String(path ?? "");
  if (p.startsWith("http://") || p.startsWith("https://")) return p;
  return `${BASE}${p.startsWith("/") ? p : `/${p}`}`;
}

/**
 * @param {string} path
 * @param {RequestInit & { parseJson?: boolean }} [init]
 * @returns {Promise<Response>}
 */
export async function siliconFetchRaw(path, init = {}) {
  const { parseJson: _p, ...rest } = init;
  const url = buildUrl(path);
  return fetch(url, {
    ...rest,
    headers: mergeSiliconHeaders(rest.headers),
  });
}

/**
 * @param {string} path
 * @param {(status: number, text: string) => void} [onUnauthorized]
 * @returns {Promise<unknown>}
 */
export async function siliconGetJson(path, onUnauthorized) {
  let res;
  try {
    res = await siliconFetchRaw(path, { method: "GET" });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(`Network error (${msg})`);
  }
  if (!res.ok) {
    if (res.status === 401 && typeof onUnauthorized === "function") onUnauthorized();
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  try {
    return await res.json();
  } catch {
    throw new Error("Invalid JSON from API");
  }
}

/**
 * @param {string} path
 * @param {unknown} [body]
 * @param {Record<string, string>} [extraHeaders]
 * @param {(status: number, text: string) => void} [onUnauthorized]
 */
export async function siliconSendJson(path, method, body, extraHeaders, onUnauthorized) {
  let res;
  const headers = { ...(extraHeaders || {}) };
  if (body !== undefined && body !== null) {
    headers["Content-Type"] = "application/json";
  }
  try {
    res = await siliconFetchRaw(path, {
      method,
      headers,
      body: body === undefined || body === null ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(`Network error (${msg})`);
  }
  if (!res.ok) {
    if (res.status === 401 && typeof onUnauthorized === "function") onUnauthorized();
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    const text = await res.text().catch(() => "");
    if (!text.trim()) return null;
    try {
      return JSON.parse(text);
    } catch {
      return { raw: text };
    }
  }
  return res.json();
}
