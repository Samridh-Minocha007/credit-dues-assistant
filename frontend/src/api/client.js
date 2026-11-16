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
  recordCashPayment: (id, amount) => request("POST", `/api/customers/${id}/payments`, { amount }),
  getMessages: (customerId) => request("GET", `/api/messages${customerId ? `?customer_id=${customerId}` : ""}`),
  getPayPage: (token) => request("GET", `/api/pay/${token}`),
  getIncoming: (status) => request("GET", `/api/incoming-payments${status ? `?status=${status}` : ""}`),
  confirmIncoming: (id, customerId) => request("POST", `/api/incoming-payments/${id}/confirm`, { customer_id: customerId }),
  dismissIncoming: (id) => request("POST", `/api/incoming-payments/${id}/dismiss`),
  // Simulation only:
  bankNotification: (payment) => request("POST", "/api/sim/bank-notification", payment),
  getPhone: (token) => request("GET", `/api/sim/phone/${token}`),
};

// Plain-language label for a message's status (see the messages table).
export function messageStatus(m) {
  switch (m.status) {
    case "sent_sim":
      return "Sent (simulated)";
    case "scheduled":
      return `Held for quiet hours, goes at ${new Date(m.scheduled_for).toLocaleString("en-IN", { weekday: "short", hour: "2-digit", minute: "2-digit" })}`;
    case "blocked_opt_out":
      return "Not sent: customer opted out";
    case "received":
      return "Received";
    default:
      return m.status;
  }
}

export const MESSAGE_KIND = {
  bill_notice: "Bill notice",
  payment_receipt: "Payment receipt",
  weekly_reminder: "Weekly reminder",
  promise_followup: "Promise follow-up",
  reply: "Customer reply",
};

// "10:59 pm" for today, "Yesterday", or "16 Nov" for older.
export function shortWhen(iso) {
  const d = new Date(iso);
  const now = new Date();
  const days = Math.round((new Date(now.toDateString()) - new Date(d.toDateString())) / 86_400_000);
  if (days === 0) return d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
  if (days === 1) return "Yesterday";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function initial(name) {
  return (name || "?").trim().slice(0, 1).toUpperCase();
}

export function formatTime(iso) {
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

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
