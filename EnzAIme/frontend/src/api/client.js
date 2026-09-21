/**
 * frontend/src/api/client.js
 * ============================
 * Thin fetch wrapper for the ENZAIme FastAPI backend (Section 48).
 * Every function throws an ApiError with a user-presentable `.message`
 * so pages can show meaningful error states when the backend is
 * unreachable or rejects a request (Section 48: "frontend must show
 * meaningful error messages if the backend is unavailable").
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    throw new ApiError(
      `Can't reach the ENZAIme API at ${API_BASE_URL}. Is the backend running? (uvicorn backend.app.main:app)`,
      0,
      String(err)
    );
  }

  let body = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }

  if (!res.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
      : detail || `Request failed (${res.status})`;
    throw new ApiError(message, res.status, detail);
  }
  return body;
}

export const api = {
  health: () => request("/health"),
  metadata: () => request("/metadata"),
  listEnzymes: (pollutant) =>
    request(`/enzymes${pollutant ? `?pollutant=${encodeURIComponent(pollutant)}` : ""}`),
  getEnzyme: (enzymeId) => request(`/enzyme/${encodeURIComponent(enzymeId)}`),
  recommend: (payload) =>
    request("/recommend", { method: "POST", body: JSON.stringify(payload) }),
  mutations: (payload) =>
    request("/mutations", { method: "POST", body: JSON.stringify(payload) }),
  reloadModel: () => request("/reload-model", { method: "POST" }),
  simulate: (payload) =>
    request("/simulate", { method: "POST", body: JSON.stringify(payload) }),
  simulateSweep: (payload) =>
    request("/simulate/sweep", { method: "POST", body: JSON.stringify(payload) }),
};

export { API_BASE_URL };
