import { useEffect, useRef, useState } from "react";
import { api, rupees, shortWhen } from "../api/client.js";
import { IconCall, IconCheck } from "../icons.jsx";

// The screen the shopkeeper lives on: add credit fast, and see anything
// that needs them. Nothing else.
export default function Today({ shop, onChange, go }) {
  const [summary, setSummary] = useState(null);
  const [toCheck, setToCheck] = useState([]);
  const [owing, setOwing] = useState([]);
  const [callList, setCallList] = useState(null);

  const load = async () => {
    const [customers, review, calls] = await Promise.all([api.searchCustomers(""), api.getIncoming("needs_review"), api.getCallList()]);
    setCallList(calls);
    const withDues = customers.filter((c) => c.balance_paise > 0);
    setOwing(withDues);
    setSummary({ total: withDues.reduce((s, c) => s + c.balance_paise, 0), count: withDues.length });
    setToCheck(review);
  };
  useEffect(() => {
    load();
  }, []);

  const changed = () => {
    load();
    onChange?.();
  };

  const setupLeft = shop && (!shop.upi_id || !shop.approved);

  return (
    <>
      <div className="page-head">
        <h1>Today</h1>
        {summary && (
          <p>
            {summary.count === 0 ? (
              "No one owes you anything right now."
            ) : (
              <>
                <span className="money due">{rupees(summary.total)}</span> pending with {summary.count}{" "}
                {summary.count === 1 ? "customer" : "customers"}
              </>
            )}
          </p>
        )}
      </div>

      {setupLeft && (
        <div className="attention" style={{ marginBottom: 20 }}>
          <strong>Finish setting up</strong>
          <div className="setup-steps">
            {!shop.upi_id && (
              <button className="btn" onClick={() => go("settings")}>
                Add your shop’s UPI ID so customers can pay from their message
              </button>
            )}
            {!shop.approved && (
              <button className="btn" onClick={() => go("settings")}>
                Approve the weekly reminder message
              </button>
            )}
          </div>
        </div>
      )}

      {callList && callList.to_call.length > 0 && <CallStrip people={callList.to_call} go={go} />}

      <AddCredit onSaved={changed} />

      <section className="section" aria-labelledby="check-h">
        <div className="section-head">
          <h2 id="check-h">Payments to check</h2>
          {toCheck.length > 0 && <span className="muted small">{toCheck.length} waiting</span>}
        </div>
        {toCheck.length === 0 ? (
          <p className="empty">
            Nothing to check. When a UPI payment clearly belongs to a customer, it’s marked paid automatically.
          </p>
        ) : (
          toCheck.map((p) => <CheckPayment key={p.id} p={p} owing={owing} onDone={changed} />)
        )}
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// Add credit. Target: under 5 seconds.
// Keyboard: phone, Enter, bill, Enter. Saved; cursor returns to phone.
function AddCredit({ onSaved }) {
  const [phone, setPhone] = useState("");
  const [bill, setBill] = useState("");
  const [paid, setPaid] = useState("");
  const [name, setName] = useState("");
  const [match, setMatch] = useState(null);
  const [showItems, setShowItems] = useState(false);
  const [items, setItems] = useState([{ description: "", qty: "", amount: "" }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(null);
  const phoneRef = useRef(null);
  const billRef = useRef(null);

  const digits = phone.replace(/\D/g, "").slice(-10);

  // Once 10 digits are typed, show who it is so the shopkeeper knows it's the right person.
  useEffect(() => {
    setMatch(null);
    if (digits.length !== 10) return;
    let live = true;
    api.searchCustomers(digits).then((rows) => live && setMatch(rows.find((r) => r.phone === digits) || "new"));
    return () => {
      live = false;
    };
  }, [digits]);

  const billNum = parseFloat(bill) || 0;
  const credit = billNum - (parseFloat(paid) || 0);
  const canSave = digits.length === 10 && credit > 0 && !saving;

  async function save(e) {
    e.preventDefault();
    if (!canSave) return;
    setError("");
    setSaving(true);
    try {
      const res = await api.createEntry({
        phone,
        bill_amount: bill,
        amount_paid: paid || "0",
        name: name || null,
        items: showItems
          ? items.filter((i) => i.description.trim()).map((i) => ({ description: i.description, qty: i.qty || null, amount: i.amount || null }))
          : [],
      });
      setSaved(res);
      setPhone("");
      setBill("");
      setPaid("");
      setName("");
      setItems([{ description: "", qty: "", amount: "" }]);
      setShowItems(false);
      phoneRef.current?.focus();
      onSaved?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const setItem = (i, key) => (e) => setItems(items.map((x, j) => (j === i ? { ...x, [key]: e.target.value } : x)));

  return (
    <form className="entry" onSubmit={save} aria-label="Add credit">
      <label className="field">
        Customer’s phone number
        <input
          ref={phoneRef}
          className="input"
          autoFocus
          inputMode="numeric"
          autoComplete="off"
          placeholder="98765 43210"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              billRef.current?.focus();
            }
          }}
        />
      </label>

      {match && match !== "new" && (
        <p className="who muted">
          <strong>{match.name || "Existing customer"}</strong>
          {match.balance_paise > 0 ? (
            <>
              , already owes <span className="money due">{rupees(match.balance_paise)}</span>
            </>
          ) : (
            ", nothing pending"
          )}
          {match.opted_out && ". Opted out of messages."}
        </p>
      )}
      {match === "new" && (
        <label className="field">
          New customer. Name (optional)
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ramesh" />
        </label>
      )}

      <div className="amount-row">
        <label className="amount-field">
          Bill
          <span className="amount-input">
            <span>₹</span>
            <input ref={billRef} inputMode="decimal" placeholder="0" value={bill} onChange={(e) => setBill(e.target.value)} />
          </span>
        </label>
        <label className="amount-field">
          Paid now
          <span className="amount-input small-amt">
            <span>₹</span>
            <input inputMode="decimal" placeholder="0" value={paid} onChange={(e) => setPaid(e.target.value)} />
          </span>
        </label>
      </div>

      <p className="credit-line" aria-live="polite">
        {billNum > 0 &&
          (credit > 0 ? (
            <>
              <span className="money due">₹{credit.toLocaleString("en-IN")}</span> goes on credit
            </>
          ) : (
            "Fully paid. Nothing to add to credit."
          ))}
      </p>

      {showItems && (
        <div className="field">
          What they bought (optional, helps if there’s a disagreement later)
          {items.map((it, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 8 }}>
              <input className="input" placeholder="Item" value={it.description} onChange={setItem(i, "description")} />
              <input className="input" placeholder="Qty" value={it.qty} onChange={setItem(i, "qty")} />
              <input className="input" placeholder="₹" inputMode="decimal" value={it.amount} onChange={setItem(i, "amount")} />
            </div>
          ))}
          <button type="button" className="btn-text" style={{ alignSelf: "flex-start" }} onClick={() => setItems([...items, { description: "", qty: "", amount: "" }])}>
            Add another item
          </button>
        </div>
      )}

      {error && <div className="notice error">{error}</div>}

      <button className="btn btn-primary btn-block" disabled={!canSave}>
        {saving ? "Saving…" : credit > 0 ? `Save ₹${credit.toLocaleString("en-IN")} on credit` : "Save on credit"}
      </button>

      {!showItems && (
        <button type="button" className="btn-text" style={{ alignSelf: "center" }} onClick={() => setShowItems(true)}>
          Add what they bought (optional)
        </button>
      )}

      {saved && (
        <div className="notice ok saved-line" role="status">
          <IconCheck size={18} />
          <div>
            Saved {rupees(saved.due.balance_paise)} for {saved.customer.name || saved.customer.phone}. They now owe{" "}
            {rupees(saved.customer.balance_paise)}.
            <div className="small">{messageLine(saved.message)}</div>
          </div>
        </div>
      )}
    </form>
  );
}

function messageLine(m) {
  if (m.status === "sent_sim") return "Payment message sent.";
  if (m.status === "scheduled") return `It’s quiet hours, so the payment message goes at ${new Date(m.scheduled_for).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}.`;
  if (m.status === "blocked_opt_out") return "No message sent: this customer opted out.";
  return "";
}

// ---------------------------------------------------------------------------
// One UPI payment the app isn't sure about. One tap to settle it.
function CheckPayment({ p, owing, onDone }) {
  const [choosing, setChoosing] = useState(!p.customer_id);
  const [pick, setPick] = useState("");
  const [error, setError] = useState("");

  const act = async (fn) => {
    setError("");
    try {
      await fn();
      onDone();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="attention">
      <div className="top">
        <div>
          <span className="money paid" style={{ fontSize: "var(--t-lg)" }}>
            {rupees(p.amount_paise)}
          </span>{" "}
          <span className="muted">from {p.payer_name || p.payer_vpa}</span>
        </div>
        <span className="hint">{shortWhen(p.received_at)}</span>
      </div>
      <p className="small muted">
        {p.match_reason}. {p.note ? `Their note: “${p.note}”.` : "No note."} UPI ID {p.payer_vpa}.
      </p>

      {!choosing ? (
        <div className="actions">
          <button className="btn btn-primary" onClick={() => act(() => api.confirmIncoming(p.id, p.customer_id))}>
            Yes, it’s {p.customer_name}
          </button>
          <button className="btn-text" onClick={() => setChoosing(true)}>
            Someone else
          </button>
          <button className="btn-text" onClick={() => act(() => api.dismissIncoming(p.id))}>
            It’s a regular sale
          </button>
        </div>
      ) : (
        <div className="actions">
          <select className="select" style={{ flex: "1 1 220px" }} value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Who paid?">
            <option value="">Who paid?</option>
            {owing.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name || c.phone}, owes {rupees(c.balance_paise)}
              </option>
            ))}
          </select>
          <button className="btn btn-primary" disabled={!pick} onClick={() => act(() => api.confirmIncoming(p.id, Number(pick)))}>
            Mark paid
          </button>
          <button className="btn-text" onClick={() => act(() => api.dismissIncoming(p.id))}>
            It’s a regular sale
          </button>
        </div>
      )}
      {error && <div className="notice error">{error}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Customers to call, in their own colour at the top of Today so they don't get
// lost. Tapping a number opens the phone's dialler; outcomes are recorded on
// the Calls screen.
function CallStrip({ people, go }) {
  return (
    <section className="call-strip" aria-labelledby="strip-h">
      <div className="call-strip-head">
        <IconCall size={20} />
        <h2 id="strip-h">
          Call {people.length} {people.length === 1 ? "customer" : "customers"}
        </h2>
        <button className="btn-text" onClick={() => go("calls")}>
          Open call list
        </button>
      </div>
      <div className="call-chips">
        {people.map((c) => (
          <a key={c.customer_id} className="call-chip" href={`tel:+91${c.phone}`}>
            <span className="who">{c.name || "Customer"}</span>
            <span className="num">{c.phone.replace(/^(\d{5})(\d{5})$/, "$1 $2")}</span>
            <span className="owes">{rupees(c.balance_paise)}</span>
          </a>
        ))}
      </div>
    </section>
  );
}
