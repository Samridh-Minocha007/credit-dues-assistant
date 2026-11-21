// Tiny wrapper around fetch. Turns FastAPI error responses into readable text.
//
// It also tells the app whether the backend is reachable. If the backend
// isn't running, the dev server answers with an error and no JSON; without
// this, every screen would just sit on "Loading…" with no explanation.
export const SERVER_EVENT = "server-status";
const announce = (up) => window.dispatchEvent(new CustomEvent(SERVER_EVENT, { detail: { up } }));

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    announce(false);
    throw new Error("Can't reach the app server.");
  }
  const data = await res.json().catch(() => null);
  if (res.status >= 500 && data === null) {
    announce(false); // the proxy couldn't reach FastAPI
    throw new Error("Can't reach the app server.");
  }
  announce(true);
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
  updateCustomer: (id, changes) => request("PATCH", `/api/customers/${id}`, changes),
  optOut: (id) => request("POST", `/api/customers/${id}/opt-out`),
  optIn: (id) => request("POST", `/api/customers/${id}/opt-in`),
  deleteCustomer: (id) => request("DELETE", `/api/customers/${id}`),
  getCallList: () => request("GET", "/api/call-list"),
  getMetrics: () => request("GET", "/api/metrics"),
  callOutcome: (id, body) => request("POST", `/api/customers/${id}/call-outcome`, body),
  resolveDispute: (id, note) => request("POST", `/api/customers/${id}/resolve-dispute`, { note: note || null }),
  getMessages: (customerId) => request("GET", `/api/messages${customerId ? `?customer_id=${customerId}` : ""}`),
  getPayPage: (token) => request("GET", `/api/pay/${token}`),
  getIncoming: (status) => request("GET", `/api/incoming-payments${status ? `?status=${status}` : ""}`),
  confirmIncoming: (id, customerId) => request("POST", `/api/incoming-payments/${id}/confirm`, { customer_id: customerId }),
  dismissIncoming: (id) => request("POST", `/api/incoming-payments/${id}/dismiss`),
  // Simulation only:
  bankNotification: (payment) => request("POST", "/api/sim/bank-notification", payment),
  getPhone: (token) => request("GET", `/api/sim/phone/${token}`),
  sendReply: (token, text) => request("POST", `/api/sim/phone/${token}/reply`, { text }),
  // Demo clock:
  getClock: () => request("GET", "/api/dev/clock"),
  advanceClock: (days, hours = 0) => request("POST", "/api/dev/advance", { days, hours }),
  resetClock: () => request("POST", "/api/dev/reset-clock"),
};

// ---- demo clock ----
// The server's clock can be moved forward for demos. The screen needs the
// same "now", or "today" and "3 days ago" would be wrong after a jump.
let clockOffsetMs = 0;
export function setClockOffset(seconds) {
  clockOffsetMs = (seconds || 0) * 1000;
}
export function appNow() {
  return new Date(Date.now() + clockOffsetMs);
}

// ---- wording ----
export const MESSAGE_KIND = {
  bill_notice: "Bill notice",
  payment_receipt: "Payment receipt",
  weekly_reminder: "Weekly reminder",
  payday_reminder: "Payday reminder",
  promise_followup: "Promise follow-up",
  opt_out_confirm: "Opt-out confirmation",
  opt_in_confirm: "Messages back on",
  promise_ack: "Promise noted",
  reply: "Reply from customer",
};

// Plain-language status of a message (see the messages table in the backend).
export function messageStatus(m) {
  switch (m.status) {
    case "sent_sim":
      return "Sent";
    case "scheduled":
      return `Waiting for morning, goes at ${timeOf(m.scheduled_for)}`;
    case "blocked_opt_out":
      return "Not sent: they opted out";
    case "blocked_cap":
      return "Not sent: monthly limit reached";
    case "cancelled_paid":
      return "Not sent: they paid first";
    case "received":
      return "Received";
    default:
      return m.status;
  }
}

export function timeOf(iso) {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

// "10:59 pm" for today, "Yesterday", or "16 Nov" for older.
export function shortWhen(iso) {
  const d = new Date(iso);
  const now = appNow();
  const days = Math.round((new Date(now.toDateString()) - new Date(d.toDateString())) / 86_400_000);
  if (days === 0) return timeOf(iso);
  if (days === 1) return "Yesterday";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function longWhen(iso) {
  return new Date(iso).toLocaleString("en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function initial(name) {
  return (name || "?").trim().slice(0, 1).toUpperCase();
}

// Amounts come back from the API as integer paise. 12050 -> "₹120.50", 50000 -> "₹500".
export function rupees(paise) {
  const whole = Math.floor(paise / 100);
  const rem = paise % 100;
  return `₹${whole.toLocaleString("en-IN")}${rem ? "." + String(rem).padStart(2, "0") : ""}`;
}

export function daysAgo(isoDate) {
  if (!isoDate) return "";
  const days = Math.floor((appNow().getTime() - new Date(isoDate).getTime()) / 86_400_000);
  return days <= 0 ? "today" : days === 1 ? "1 day ago" : `${days} days ago`;
}

// What the reply reader (the experiment) understood from a customer's reply.
// Returns null if the reply wasn't read (experiment off, or STOP/START).
export function replyReading(m) {
  if (!m.parsed) return null;
  const p = JSON.parse(m.parsed);
  const by = p.parsed_by === "gemini" ? "Gemini" : "built-in reader";
  if (p.intent === "promise" && p.promised_date && p.confidence >= 0.6) {
    const d = new Date(p.promised_date + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
    return { kind: "promise", text: `Read as a promise to pay by ${d}`, by };
  }
  if (p.intent === "already_paid") return { kind: "paid", text: "Says they already paid. Please check.", by };
  return { kind: "other", text: "Not a clear promise. Nothing done automatically.", by };
}
