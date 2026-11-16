import { useEffect, useState } from "react";
import { MESSAGE_KIND, api, initial, rupees, shortWhen } from "../api/client.js";
import { IconRefresh } from "../icons.jsx";

// Everything that went out to customers or came in from them, newest first.
const FILTERS = [
  ["all", "All"],
  ["messages", "Messages sent"],
  ["payments", "UPI payments"],
];

const PAYMENT_STATUS = {
  matched_auto: "Marked paid automatically",
  matched_confirmed: "You confirmed",
  needs_review: "Waiting for you on Today",
  not_dues: "Regular sale",
};

export default function Activity() {
  const [filter, setFilter] = useState("all");
  const [items, setItems] = useState(null);

  const load = async () => {
    const [messages, payments] = await Promise.all([api.getMessages(), api.getIncoming()]);
    setItems(
      [
        ...messages.map((m) => ({ at: m.created_at, type: "messages", m })),
        ...payments.map((p) => ({ at: p.received_at, type: "payments", p })),
      ].sort((a, b) => (a.at < b.at ? 1 : -1))
    );
  };
  useEffect(() => {
    load();
  }, []);

  const shown = (items || []).filter((i) => filter === "all" || i.type === filter);

  return (
    <>
      <div className="page-head" style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
        <div>
          <h1>Activity</h1>
          <p>Messages sent to customers and UPI payments received. All simulated.</p>
        </div>
        <button className="icon-btn" style={{ marginLeft: 0, flexShrink: 0 }} onClick={load} aria-label="Refresh">
          <IconRefresh />
        </button>
      </div>

      <div className="chips" role="group" aria-label="Show">
        {FILTERS.map(([key, label]) => (
          <button key={key} className="chip" aria-pressed={filter === key} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      {items === null ? (
        <p className="empty">Loading…</p>
      ) : shown.length === 0 ? (
        <p className="empty">Nothing here yet. Add credit on the Today screen and the customer’s payment message will show up here.</p>
      ) : (
        <ul className="rows">
          {shown.map((i) => (i.type === "messages" ? <MessageRow key={`m${i.m.id}`} m={i.m} /> : <PaymentRow key={`p${i.p.id}`} p={i.p} />))}
        </ul>
      )}
    </>
  );
}

function MessageRow({ m }) {
  const who = m.customer_name || m.customer_phone;
  const status =
    m.status === "scheduled"
      ? `Waiting for morning, goes at ${new Date(m.scheduled_for).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}`
      : m.status === "blocked_opt_out"
        ? "Not sent: they opted out"
        : "Sent";
  return (
    <li>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <span className="initial" aria-hidden>
          {initial(who)}
        </span>
        <span className="row-main">
          <span className="row-title" style={{ display: "block" }}>
            {MESSAGE_KIND[m.kind] || "Message"} to {who}
          </span>
          <span className="row-sub" style={{ display: "block" }}>
            {status}
          </span>
          <span className="hint" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", marginTop: 2 }}>
            {m.body}
          </span>
        </span>
        <span className="hint">{shortWhen(m.created_at)}</span>
      </div>
    </li>
  );
}

function PaymentRow({ p }) {
  const who = p.customer_name && p.status !== "not_dues" && p.status !== "needs_review" ? p.customer_name : p.payer_name || p.payer_vpa;
  return (
    <li>
      <div className="row">
        <span className="initial" aria-hidden>
          ₹
        </span>
        <span className="row-main">
          <span className="row-title" style={{ display: "block" }}>
            {who}
          </span>
          <span className="row-sub">{PAYMENT_STATUS[p.status]}</span>
        </span>
        <span className="row-end">
          <span className={`money ${p.status === "not_dues" ? "" : "paid"}`}>{rupees(p.amount_paise)}</span>
          <div className="hint">{shortWhen(p.received_at)}</div>
        </span>
      </div>
    </li>
  );
}
