const BASE = import.meta.env.VITE_API_URL || "";

function getToken() {
  return localStorage.getItem("shadow_token");
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...options.headers },
  });

  if (res.status === 401) {
    localStorage.removeItem("shadow_token");
    window.dispatchEvent(new Event("shadow:logout"));
    throw new Error("Session expired");
  }

  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

function get(path) {
  return request(path);
}

function post(path, body, method = "POST") {
  return request(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  getShadowPrice: () => get("/api/v1/shadow-price"),
  getShadowHistory: (hours = 24) => get(`/api/v1/shadow-price/history?hours=${hours}`),
  getSourcesStatus: () => get("/api/v1/sources/status"),
  getCorrelations: (window = 90) => get(`/api/v1/correlations?window=${window}`),
  getModelParams: () => get("/api/v1/model/params"),
  recalibrate: (windowStart, windowEnd) =>
    post("/api/v1/model/recalibrate", { window_start: windowStart, window_end: windowEnd }),
  activateModel: (paramId) => post("/api/v1/model/activate", { param_id: paramId }),
  saveParams: (name, params, notes) =>
    post("/api/v1/model/params", { name, params, notes }),
  getConfig: () => get("/api/v1/config"),
  patchConfig: (key, value) => post("/api/v1/config", { key, value }, "PATCH"),
};
