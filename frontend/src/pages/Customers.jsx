import { useEffect, useState } from "react";
import { MESSAGE_KIND, api, daysAgo, initial, rupees, shortWhen } from "../api/client.js";
import { IconBack, IconPhone } from "../icons.jsx";

export default function Customers() {
  const [selected, setSelected] = useState(null);
  if (selected) return <CustomerDetail id={selected} onBack={() => setSelected(null)} />;
  return <CustomerList onOpen={setSelected} />;
}

function CustomerList({ onOpen }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState(null); // null while loading, so "no customers" never flashes

  // Search as you type, with a short pause so we don't call the server on every key.
  useEffect(() => {
    const t = setTimeout(() => api.searchCustomers(q).then(setRows), 200);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <>
      <div className="page-head">
        <h1>Customers</h1>
        <p>Biggest balance first.</p>
      </div>
      <input
        className="input"
        type="search"
        placeholder="Search by name or phone"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ marginBottom: 16 }}
        aria-label="Search customers"
      />
      {rows === null ? (
        <p className="empty">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="empty">{q ? `No customer matches “${q}”.` : "No customers yet. Add credit on the Today screen to create one."}</p>
      ) : (
        <ul className="rows">
          {rows.map((r) => (
            <li key={r.id}>
              <button className="row" onClick={() => onOpen(r.id)}>
                <span className="initial" aria-hidden>
                  {initial(r.name || r.phone)}
                </span>
                <span className="row-main">
                  <span className="row-title" style={{ display: "block" }}>
                    {r.name || r.phone}
                  </span>
                  <span className="row-sub">
                    {r.name ? r.phone : "No name saved"}
                    {r.oldest_open_due_at ? `, oldest bill ${daysAgo(r.oldest_open_due_at)}` : ""}
                    {r.opted_out ? ", opted out of messages" : ""}
                  </span>
                </span>
                <span className="row-end">
                  {r.balance_paise > 0 ? <span className="money due">{rupees(r.balance_paise)}</span> : <span className="hint">Settled</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

// One customer: balance, take a payment, and their full history as a single
// ledger, newest first: bills, payments and messages together.
function CustomerDetail({ id, onBack }) {
  const [c, setC] = useState(null);
  const [cash, setCash] = useState("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const load = () => api.getCustomer(id).then(setC);
  useEffect(() => {
    load();
  }, [id]);

  if (!c) return <p className="empty">Loading…</p>;

  async function recordCash(e) {
    e.preventDefault();
    setError("");
    setNote("");
    try {
      const r = await api.recordCashPayment(c.id, cash);
      setCash("");
      setNote(`Recorded ${rupees(r.payment.amount_paise)}. A receipt message was sent.`);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  const history = [
    ...c.dues.map((d) => ({ at: d.created_at, kind: "bill", d })),
    ...c.payments.map((p) => ({ at: p.paid_at, kind: "payment", p })),
    ...c.messages.map((m) => ({ at: m.created_at, kind: "message", m })),
  ].sort((a, b) => (a.at < b.at ? 1 : -1));

  return (
    <>
      <button className="btn-text back" onClick={onBack}>
        <IconBack /> All customers
      </button>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <h1>{c.name || c.phone}</h1>
        <p>
          {c.name && `${c.phone}. `}Customer since {new Date(c.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}.
        </p>
      </div>

      <div className="balance-block">
        <div>
          <div className="muted small">Owes you</div>
          <div className={`money ${c.balance_paise ? "due" : "paid"}`}>{rupees(c.balance_paise)}</div>
        </div>
        {c.balance_paise > 0 && (
          <form className="pay-inline" onSubmit={recordCash}>
            <input className="input" inputMode="decimal" placeholder="Amount ₹" value={cash} onChange={(e) => setCash(e.target.value)} aria-label="Amount paid at the counter" />
            <button className="btn btn-primary" disabled={!cash}>
              Record payment
            </button>
          </form>
        )}
      </div>
      {error && <div className="notice error" style={{ marginBottom: 12 }}>{error}</div>}
      {note && <div className="notice ok" style={{ marginBottom: 12 }}>{note}</div>}

      {c.pay_link && (
        <a className="btn" href={c.pay_link.replace("/pay/", "/phone/")} target="_blank" rel="noreferrer" style={{ textDecoration: "none", marginBottom: 8 }}>
          <IconPhone /> Open {c.name ? `${c.name.split(" ")[0]}’s` : "the customer’s"} phone (demo)
        </a>
      )}

      <section className="section" aria-labelledby="hist-h">
        <div className="section-head">
          <h2 id="hist-h">History</h2>
        </div>
        <ul className="timeline">
          {history.map((h, i) => (
            <HistoryRow key={i} h={h} />
          ))}
        </ul>
        <p className="hint" style={{ marginTop: 14 }}>
          Phone number given to the shop on {new Date(c.consent_at).toLocaleDateString("en-IN")}, which counts as consent to payment messages.
        </p>
      </section>
    </>
  );
}

function HistoryRow({ h }) {
  if (h.kind === "bill") {
    const d = h.d;
    return (
      <li>
        <span className="when">{shortWhen(h.at)}</span>
        <div>
          <div className="what">
            Bill of {rupees(d.bill_paise)}
            {d.paid_at_entry_paise > 0 && `, paid ${rupees(d.paid_at_entry_paise)} then`}
            {d.status === "paid" && <span className="tag">cleared</span>}
          </div>
          {d.items.length > 0 && (
            <div className="msg">{d.items.map((i) => [i.description, i.qty].filter(Boolean).join(" ")).join(", ")}</div>
          )}
        </div>
        <span className="money due">+{rupees(d.bill_paise - d.paid_at_entry_paise)}</span>
      </li>
    );
  }
  if (h.kind === "payment") {
    const p = h.p;
    return (
      <li>
        <span className="when">{shortWhen(h.at)}</span>
        <div className="what">Paid {p.source === "cash" ? "at the counter" : "by UPI"}</div>
        <span className="money paid">−{rupees(p.amount_paise)}</span>
      </li>
    );
  }
  const m = h.m;
  return (
    <li className="is-message">
      <span className="when">{shortWhen(h.at)}</span>
      <div>
        <div className="what">
          {MESSAGE_KIND[m.kind] || "Message"} {m.status === "scheduled" ? <span className="tag held">waiting for morning</span> : m.status === "blocked_opt_out" ? <span className="tag">not sent, opted out</span> : <span className="tag">sent</span>}
        </div>
        <div className="msg">{m.body}</div>
      </div>
      <span />
    </li>
  );
}
