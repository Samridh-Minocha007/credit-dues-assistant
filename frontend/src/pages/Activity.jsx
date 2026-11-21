import { useEffect, useState } from "react";
import { MESSAGE_KIND, api, initial, longWhen, messageStatus, replyReading, rupees, setClockOffset, shortWhen } from "../api/client.js";
import { ReadingNote } from "./Customers.jsx";
import { IconRefresh } from "../icons.jsx";
import { t } from "../i18n.jsx";

// Everything that went out to customers or came in from them, grouped by
// customer so one person's story reads together. The customer with the most
// recent activity is on top; open a row to see their full timeline.
const FILTERS = [
  ["all", "All"],
  ["messages", "Messages"],
  ["payments", "UPI payments"],
];

const PAYMENT_STATUS = {
  matched_auto: "marked paid automatically",
  matched_confirmed: "you confirmed it",
  needs_review: "waiting for you on Today",
  not_dues: "regular sale",
};

const UNLINKED = "unlinked";

export default function Activity() {
  const [filter, setFilter] = useState("all");
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(() => new Set());

  const load = async () => {
    const [messages, payments, customers, clock] = await Promise.all([
      api.getMessages(),
      api.getIncoming(),
      api.searchCustomers(""),
      api.getClock(),
    ]);
    setClockOffset(clock.offset_seconds); // before rendering, so "today" / "16 Nov" use demo time
    setData({ messages, payments, customers });
  };
  useEffect(() => {
    load();
  }, []);

  const toggle = (key) =>
    setOpen((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const groups = data ? groupByCustomer(data, filter) : null;

  return (
    <>
      <div className="page-head" style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
        <div>
          <h1>{t("Activity")}</h1>
          <p>{t("Messages and UPI payments, grouped by customer. All simulated.")}</p>
        </div>
        <button className="icon-btn" style={{ marginLeft: 0, flexShrink: 0 }} onClick={load} aria-label="Refresh">
          <IconRefresh />
        </button>
      </div>

      <DemoClock onJump={load} />

      <div className="chips" role="group" aria-label="Show">
        {FILTERS.map(([key, label]) => (
          <button key={key} className="chip" aria-pressed={filter === key} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      {groups === null ? (
        <p className="empty">{t("Loading…")}</p>
      ) : groups.length === 0 ? (
        <p className="empty">Nothing here yet. Add credit on the Today screen and the customer’s payment message will show up here.</p>
      ) : (
        <ul className="rows">
          {groups.map((g) => (
            <CustomerGroup key={g.key} g={g} open={open.has(g.key)} onToggle={() => toggle(g.key)} />
          ))}
        </ul>
      )}
    </>
  );
}

// Build one group per customer: { key, name, phone, events (newest first), counts }.
function groupByCustomer({ messages, payments, customers }, filter) {
  const byId = new Map(customers.map((c) => [c.id, c]));
  const groups = new Map();
  const groupFor = (key, fallbackName) => {
    if (!groups.has(key)) {
      const c = byId.get(key);
      groups.set(key, {
        key,
        name: key === UNLINKED ? t("Not linked to a customer") : c?.name || (c?.deleted ? "Deleted customer" : c?.phone || fallbackName),
        phone: key === UNLINKED ? null : c?.deleted ? (c.name ? "data deleted" : null) : c?.name ? c.phone : null,
        unlinked: key === UNLINKED,
        events: [],
        messages: 0,
        payments: 0,
      });
    }
    return groups.get(key);
  };

  if (filter !== "payments")
    for (const m of messages) {
      const g = groupFor(m.customer_id, m.customer_name || m.customer_phone);
      g.events.push({ at: m.created_at, type: "message", m });
      g.messages += 1;
    }
  if (filter !== "messages")
    for (const p of payments) {
      // Suggested-but-unconfirmed and regular-sale payments aren't the customer's yet.
      const linked = p.customer_id && (p.status === "matched_auto" || p.status === "matched_confirmed");
      const g = groupFor(linked ? p.customer_id : UNLINKED, p.customer_name);
      g.events.push({ at: p.received_at, type: "payment", p });
      g.payments += 1;
    }

  const list = [...groups.values()];
  // Newest first; events in the same second are ordered by id (the order they happened).
  const seq = (e) => (e.type === "message" ? e.m.id : e.p.id);
  for (const g of list) g.events.sort((a, b) => (a.at !== b.at ? (a.at < b.at ? 1 : -1) : seq(b) - seq(a)));
  // Most recent activity first; the "not linked" group always goes last.
  return list.sort((a, b) => (a.unlinked - b.unlinked) || (a.events[0].at < b.events[0].at ? 1 : -1));
}

function CustomerGroup({ g, open, onToggle }) {
  const latest = g.events[0];
  const counts = [g.messages && `${g.messages} message${g.messages > 1 ? "s" : ""}`, g.payments && `${g.payments} payment${g.payments > 1 ? "s" : ""}`]
    .filter(Boolean)
    .join(", ");
  return (
    <li className={`group ${open ? "is-open" : ""}`}>
      <button className="row" onClick={onToggle} aria-expanded={open}>
        <span className="initial" aria-hidden>
          {g.unlinked ? "₹" : initial(g.name)}
        </span>
        <span className="row-main">
          <span className="row-title" style={{ display: "block" }}>
            {g.name}
            {g.phone && <span className="row-phone">{g.phone}</span>}
          </span>
          <span className="row-sub" style={{ display: "block" }}>
            {open ? counts : summary(latest)}
          </span>
        </span>
        <span className="row-end">
          <span className="hint">{shortWhen(latest.at)}</span>
          <svg className="chev" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="m6 9 6 6 6-6" />
          </svg>
        </span>
      </button>
      {open && (
        <ul className="timeline group-body">
          {g.events.map((e) => (e.type === "message" ? <MessageEvent key={`m${e.m.id}`} m={e.m} /> : <PaymentEvent key={`p${e.p.id}`} p={e.p} unlinked={g.unlinked} />))}
        </ul>
      )}
    </li>
  );
}

// One line describing the latest event, shown while the group is closed.
function summary(e) {
  if (e.type === "payment") return `${rupees(e.p.amount_paise)} UPI payment, ${PAYMENT_STATUS[e.p.status]}`;
  const m = e.m;
  if (m.direction === "in") {
    const r = replyReading(m);
    return r && r.kind !== "other" ? `They replied “${m.body}”. ${r.text}` : `They replied “${m.body}”`;
  }
  return `${MESSAGE_KIND[m.kind] || "Message"}: ${messageStatus(m).toLowerCase()}`;
}

function MessageEvent({ m }) {
  const inbound = m.direction === "in";
  return (
    <li className="is-message">
      <span className="when">{shortWhen(m.created_at)}</span>
      <div>
        <div className="what">
          {inbound ? "They replied" : MESSAGE_KIND[m.kind] || "Message"}
          {!inbound && <span className={`tag ${m.status === "scheduled" ? "held" : ""}`}>{messageStatus(m)}</span>}
        </div>
        <div className="msg">{inbound ? `“${m.body}”` : m.body}</div>
        {inbound && replyReading(m) && <ReadingNote r={replyReading(m)} />}
      </div>
      <span />
    </li>
  );
}

function PaymentEvent({ p, unlinked }) {
  return (
    <li>
      <span className="when">{shortWhen(p.received_at)}</span>
      <div>
        <div className="what">
          UPI payment{unlinked && p.payer_name ? ` from ${p.payer_name}` : ""}
          <span className="tag">{PAYMENT_STATUS[p.status]}</span>
        </div>
        {unlinked && p.payer_vpa !== "deleted" && <div className="msg">{p.payer_vpa}</div>}
      </div>
      <span className={`money ${p.status === "not_dues" || p.status === "needs_review" ? "" : "paid"}`}>{rupees(p.amount_paise)}</span>
    </li>
  );
}

// DEMO ONLY: move the app's clock forward to see weeks of reminders in seconds.
function DemoClock({ onJump }) {
  const [clock, setClock] = useState(null);
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);

  const show = (c) => {
    setClock(c);
    setClockOffset(c.offset_seconds);
  };
  useEffect(() => {
    api.getClock().then(show);
  }, []);

  async function jump(days) {
    setBusy(true);
    const r = await api.advanceClock(days);
    const c = await api.getClock();
    show(c);
    const parts = [];
    if (r.reminders_sent) parts.push(`${r.reminders_sent} weekly reminder${r.reminders_sent > 1 ? "s" : ""} sent`);
    if (r.delivered) parts.push(`${r.delivered} held message${r.delivered > 1 ? "s" : ""} delivered`);
    if (r.blocked_cap) parts.push(`${r.blocked_cap} stopped by the monthly limit`);
    if (r.cancelled_paid) parts.push(`${r.cancelled_paid} cancelled because they paid`);
    setResult(parts.length ? `${parts.join(", ")}.` : "Nothing was due in that time.");
    setBusy(false);
    onJump();
  }

  async function reset() {
    setBusy(true);
    show(await api.resetClock());
    setResult("Back to real time.");
    setBusy(false);
    onJump();
  }

  if (!clock) return null;
  return (
    <div className="demo-clock">
      <div className="now">
        <span className="muted">{t("Demo time")}{clock.offset_seconds > 0 ? " (moved ahead)" : ""}</span>
        <strong>{longWhen(clock.now)}</strong>
        {result && <span className="small muted">{result}</span>}
      </div>
      <button className="btn" disabled={busy} onClick={() => jump(1)}>
        {t("+1 day")}
      </button>
      <button className="btn" disabled={busy} onClick={() => jump(7)}>
        {t("+1 week")}
      </button>
      {clock.offset_seconds > 0 && (
        <button className="btn-text" disabled={busy} onClick={reset}>
          {t("Back to real time")}
        </button>
      )}
    </div>
  );
}
