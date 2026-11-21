import { useEffect, useState } from "react";
import { MESSAGE_KIND, api, daysAgo, initial, messageStatus, replyReading, rupees, shortWhen } from "../api/client.js";
import { IconBack, IconPhone } from "../icons.jsx";
import { t } from "../i18n.jsx";

// After a delete the phone number is gone (replaced by a placeholder), so
// never show it as a name.
const displayName = (c) => c.name || (c.deleted ? "Deleted customer" : c.phone);

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
        <h1>{t("Customers")}</h1>
        <p>{t("Biggest balance first.")}</p>
      </div>
      <input
        className="input"
        type="search"
        placeholder={t("Search by name or phone")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ marginBottom: 16 }}
        aria-label="Search customers"
      />
      {rows === null ? (
        <p className="empty">{t("Loading…")}</p>
      ) : rows.length === 0 ? (
        <p className="empty">{q ? `No customer matches “${q}”.` : "No customers yet. Add credit on the Today screen to create one."}</p>
      ) : (
        <ul className="rows">
          {rows.map((r) => (
            <li key={r.id}>
              <button className="row" onClick={() => onOpen(r.id)}>
                <span className="initial" aria-hidden>
                  {initial(displayName(r))}
                </span>
                <span className="row-main">
                  <span className="row-title" style={{ display: "block" }}>
                    {displayName(r)}
                  </span>
                  <span className="row-sub">
                    {r.deleted ? "Personal data deleted" : r.name ? r.phone : "No name saved"}
                    {r.oldest_open_due_at ? `, oldest bill ${daysAgo(r.oldest_open_due_at)}` : ""}
                    {r.opted_out && !r.deleted ? ", messages stopped" : ""}
                  </span>
                </span>
                <span className="row-end">
                  {r.balance_paise > 0 ? <span className="money due">{rupees(r.balance_paise)}</span> : <span className="hint">{t("Settled")}</span>}
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

  if (!c) return <p className="empty">{t("Loading…")}</p>;

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
    ...c.call_outcomes.map((o) => ({ at: o.created_at, kind: "call", o, promise: c.promises.find((p) => p.id === o.promise_id) })),
    // Promises from replies (slice 5) have no call; show them on their own.
    ...c.promises.filter((p) => p.source !== "call").map((p) => ({ at: p.created_at, kind: "promise", p })),
  ].sort(newestFirst);

  return (
    <>
      <button className="btn-text back" onClick={onBack}>
        <IconBack /> {t("All customers")}
      </button>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <h1>{displayName(c)}</h1>
        <p>
          {c.deleted ? "Personal data deleted on request. " : c.name ? `${c.phone}. ` : ""}
          Customer since {new Date(c.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}.
          {c.opted_out && !c.deleted && " Messages stopped."}
        </p>
        {c.collection_state && c.collection_state !== "reminders" && (
          <p className={`state-line ${c.collection_state}`}>{STATE_LINE[c.collection_state](c)}</p>
        )}
      </div>

      <div className="balance-block">
        <div>
          <div className="muted small">{t("Owes you")}</div>
          <div className={`money ${c.balance_paise ? "due" : "paid"}`}>{rupees(c.balance_paise)}</div>
        </div>
        {c.balance_paise > 0 && !c.deleted && (
          <form className="pay-inline" onSubmit={recordCash}>
            <input className="input" inputMode="decimal" placeholder={t("Amount ₹")} value={cash} onChange={(e) => setCash(e.target.value)} aria-label="Amount paid at the counter" />
            <button className="btn btn-primary" disabled={!cash}>
              {t("Record payment")}
            </button>
          </form>
        )}
      </div>
      {error && <div className="notice error" style={{ marginBottom: 12 }}>{error}</div>}
      {note && <div className="notice ok" style={{ marginBottom: 12 }}>{note}</div>}

      {c.pay_link && (
        <div className="controls-row" style={{ marginBottom: 8 }}>
          <a className="btn" href={c.pay_link.replace("/pay/", "/phone/")} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
            <IconPhone /> Open {c.name ? `${c.name.split(" ")[0]}’s` : "the customer’s"} phone (demo)
          </a>
          <a className="btn" href={c.pay_link.replace("/pay/", "/statement/")} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
            {t("View statement")}
          </a>
          {c.balance_paise > 0 && !c.opted_out && (
            <button
              className="btn wa-btn"
              onClick={async () => {
                setError("");
                const r = await api.whatsappReminder(c.id);
                if (r.allowed) {
                  window.open(r.url, "_blank", "noopener");
                  load();
                } else setError(r.reason);
              }}
            >
              {t("Send reminder on WhatsApp")}
            </button>
          )}
          <button
            className="btn-text"
            onClick={async () => {
              await api.sendStatement(c.id);
              setNote(t("Statement link sent (simulated)."));
              load();
            }}
          >
            {t("Send statement to customer")}
          </button>
        </div>
      )}

      {!c.deleted && <CustomerControls c={c} onChange={setC} />}

      <section className="section" aria-labelledby="hist-h">
        <div className="section-head">
          <h2 id="hist-h">{t("History")}</h2>
        </div>
        <ul className="timeline">
          {history.map((h, i) => (
            <HistoryRow key={i} h={h} />
          ))}
        </ul>
        {!c.deleted && (
          <p className="hint" style={{ marginTop: 14 }}>
            Phone number given to the shop on {new Date(c.consent_at).toLocaleDateString("en-IN")}, which counts as consent to payment messages.
          </p>
        )}
      </section>
    </>
  );
}

// Newest first. Events in the same second (a reply and the promise read from
// it) are ordered by message id, with promises/calls shown above the reply.
function newestFirst(a, b) {
  if (a.at !== b.at) return a.at < b.at ? 1 : -1;
  const rank = (e) => (e.kind === "message" ? e.m.id : Number.MAX_SAFE_INTEGER);
  return rank(b) - rank(a);
}

const STATE_LINE = {
  to_call: (c) => `On your call list: ${c.collection_reason.toLowerCase()}. Automatic reminders have stopped.`,
  promised: (c) => `${c.collection_reason}. Reminders are paused until then.`,
  disputed: () => "Disputed the amount. No messages go out until you sort it out on the Today screen.",
};

const OUTCOME_TEXT = {
  promised_date: "Called: promised to pay",
  disputed: "Called: disputed the amount",
  written_off: "Written off",
  dispute_resolved: "Dispute sorted out",
};

const PROMISE_STATUS = { pending: "waiting", kept: "kept", broken: "not kept", replaced: "replaced by a newer promise" };

function promiseDate(iso) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

function HistoryRow({ h }) {
  if (h.kind === "call") {
    const { o, promise } = h;
    return (
      <li>
        <span className="when">{shortWhen(h.at)}</span>
        <div>
          <div className="what">
            <strong>{OUTCOME_TEXT[o.outcome] || o.outcome}</strong>
            {promise && ` by ${promiseDate(promise.promised_date)}`}
            {promise && <span className="tag">{PROMISE_STATUS[promise.status]}</span>}
          </div>
          {o.note && <div className="msg">“{o.note}”</div>}
        </div>
        {o.outcome === "written_off" ? <span className="money muted">{rupees(o.balance_paise)}</span> : <span />}
      </li>
    );
  }
  if (h.kind === "promise") {
    return (
      <li>
        <span className="when">{shortWhen(h.at)}</span>
        <div>
          <div className="what">
            <strong>Promised by reply</strong> to pay by {promiseDate(h.p.promised_date)}
            <span className="tag">{PROMISE_STATUS[h.p.status]}</span>
          </div>
          <div className="msg">From “{h.p.raw_text}”</div>
        </div>
        <span />
      </li>
    );
  }
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
            {d.status === "written_off" && <span className="tag">written off</span>}
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
  const inbound = m.direction === "in";
  const reading = inbound ? replyReading(m) : null;
  return (
    <li className="is-message">
      <span className="when">{shortWhen(h.at)}</span>
      <div>
        <div className="what">
          {inbound ? "They replied" : MESSAGE_KIND[m.kind] || "Message"}
          {!inbound && <span className={`tag ${m.status === "scheduled" ? "held" : ""}`}>{messageStatus(m)}</span>}
        </div>
        <div className="msg">{inbound ? `“${m.body}”` : m.body}</div>
        {reading && <ReadingNote r={reading} />}
      </div>
      <span />
    </li>
  );
}

// Stop/resume messages, and delete personal data on the customer's request.
function LimitEditor({ c, onChange }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(c.own_credit_limit_paise != null ? String(c.own_credit_limit_paise / 100) : "");
  const [error, setError] = useState("");
  const own = c.own_credit_limit_paise != null;

  async function save(e) {
    e.preventDefault();
    setError("");
    try {
      onChange(await api.updateCustomer(c.id, { credit_limit: value || "0" }));
      setEditing(false);
    } catch (err) {
      setError(err.message);
    }
  }

  if (!editing)
    return (
      <p className="small muted">
        {c.credit_limit_paise != null
          ? t(own ? "Credit limit: {limit}" : "Credit limit: {limit} (shop default)", { limit: rupees(c.credit_limit_paise) })
          : t("No credit limit")}{" "}
        <button className="btn-text" onClick={() => setEditing(true)}>
          {t("Change")}
        </button>
      </p>
    );
  return (
    <form className="pay-inline" onSubmit={save}>
      <input className="input" inputMode="decimal" placeholder={t("Limit ₹ (empty = shop default)")} value={value} onChange={(e) => setValue(e.target.value)} />
      <button className="btn">{t("Save")}</button>
      <button type="button" className="btn-text" onClick={() => setEditing(false)}>
        {t("Back")}
      </button>
      {error && <span className="notice error">{error}</span>}
    </form>
  );
}

function CustomerControls({ c, onChange }) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const first = c.name ? c.name.split(" ")[0] : "this customer";

  const act = async (fn) => {
    setError("");
    try {
      onChange(await fn());
      setConfirming(false);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="controls">
      <LimitEditor c={c} onChange={onChange} />
      <div className="controls-row">
        {c.opted_out ? (
          <button className="btn" onClick={() => act(() => api.optIn(c.id))}>
            {t("Resume messages")}
          </button>
        ) : (
          <button className="btn" onClick={() => act(() => api.optOut(c.id))}>
            {t("Stop messages")}
          </button>
        )}
        {!confirming && (
          <button className="btn-text danger" onClick={() => setConfirming(true)}>
            Delete {first}’s data
          </button>
        )}
      </div>
      {confirming && (
        <div className="confirm">
          <p>
            <strong>Delete {first}’s personal data?</strong> Their phone number, item lists, messages and saved UPI IDs are
            erased and they won’t be contacted again. Their name, amounts and dates stay, so you can check old payments.
            {c.balance_paise > 0 && ` They still owe ${rupees(c.balance_paise)}.`} This can’t be undone.
          </p>
          <div className="controls-row">
            <button className="btn btn-danger" onClick={() => act(() => api.deleteCustomer(c.id))}>
              Delete data
            </button>
            <button className="btn-text" onClick={() => setConfirming(false)}>
              Keep it
            </button>
          </div>
        </div>
      )}
      {error && <div className="notice error">{error}</div>}
    </div>
  );
}

// Shown under a customer's reply when the experiment read it.
export function ReadingNote({ r }) {
  return (
    <div className={`reading ${r.kind}`}>
      {r.text} <span className="hint">({r.by})</span>
    </div>
  );
}
