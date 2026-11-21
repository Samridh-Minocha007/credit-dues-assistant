// Entries made without internet are kept on the phone and sent later.
//
// Each queued entry gets a unique id (client_ref). If a send is retried
// after a flaky connection, the server sees the same id and doesn't create
// the bill twice. The real time of the sale is kept too (recorded_at).
import { api } from "./api/client.js";

const KEY = "offline-entries";

export function queued() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

function save(list) {
  localStorage.setItem(KEY, JSON.stringify(list));
  window.dispatchEvent(new Event("offline-queue"));
}

// Local time on the phone (India time) without a timezone, as the server expects.
function localNow() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function queueEntry(entry) {
  const ref = (crypto.randomUUID && crypto.randomUUID()) || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  save([...queued(), { ...entry, client_ref: ref, recorded_at: localNow() }]);
}

let flushing = false;
export async function flushQueue() {
  if (flushing) return 0;
  flushing = true;
  let sent = 0;
  try {
    for (const entry of queued().filter((x) => !x.error)) {
      try {
        const { error, ...body } = entry;
        await api.createEntry(body);
        save(queued().filter((x) => x.client_ref !== entry.client_ref));
        sent += 1;
      } catch (e) {
        if (e.message === "Can't reach the app server.") break; // still offline: try later
        // The server rejected it (e.g. a mistyped phone number). Never drop it
        // silently: keep it with the reason so the shopkeeper can fix it.
        save(queued().map((x) => (x.client_ref === entry.client_ref ? { ...x, error: e.message } : x)));
      }
    }
  } finally {
    flushing = false;
  }
  return sent;
}

export function startAutoSync() {
  window.addEventListener("online", flushQueue);
  setInterval(() => queued().length && flushQueue(), 30_000);
  flushQueue();
}

export function removeQueued(ref) {
  save(queued().filter((x) => x.client_ref !== ref));
}
