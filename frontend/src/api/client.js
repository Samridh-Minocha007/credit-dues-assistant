// Tiny wrapper around fetch. Turns FastAPI error responses into readable text.
async function request(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // FastAPI sends {detail: "text"} for our own errors and
    // {detail: [{msg: ...}, ...]} for automatic validation errors.
    const d = data?.detail;
    const msg = Array.isArray(d) ? d.map((e) => e.msg.replace(/^Value error, /, "")).join("; ") : d;
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  getSettings: () => request("GET", "/api/settings"),
  updateSettings: (changes) => request("PUT", "/api/settings", changes),
  approveSettings: () => request("POST", "/api/settings/approve"),
  createEntry: (entry) => request("POST", "/api/entries", entry),
  searchCustomers: (q) => request("GET", `/api/customers${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getCustomer: (id) => request("GET", `/api/customers/${id}`),
};

// Amounts come back from the API as integer paise. 12050 -> "₹120.50", 50000 -> "₹500".
export function rupees(paise) {
  const whole = Math.floor(paise / 100);
  const rem = paise % 100;
  return `₹${whole.toLocaleString("en-IN")}${rem ? "." + String(rem).padStart(2, "0") : ""}`;
}

export function daysAgo(isoDate) {
  if (!isoDate) return "";
  const days = Math.floor((Date.now() - new Date(isoDate).getTime()) / 86_400_000);
  return days <= 0 ? "today" : days === 1 ? "1 day ago" : `${days} days ago`;
}
