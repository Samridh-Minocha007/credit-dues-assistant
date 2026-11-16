import { useEffect, useRef, useState } from "react";
import { api, rupees } from "../api/client.js";

// The speed-critical screen. Target: under 5 seconds per entry.
// Flow: type phone -> Enter -> type bill -> Enter (paid defaults to 0) -> saved,
// and the cursor jumps back to the phone box for the next customer.
// Name and items are optional and never block saving.
export default function QuickEntry() {
  const [phone, setPhone] = useState("");
  const [bill, setBill] = useState("");
  const [paid, setPaid] = useState("");
  const [name, setName] = useState("");
  const [match, setMatch] = useState(null); // existing customer for this phone, if any
  const [showItems, setShowItems] = useState(false);
  const [items, setItems] = useState([{ description: "", qty: "", amount: "" }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [lastSaved, setLastSaved] = useState(null);

  const phoneRef = useRef(null);
  const billRef = useRef(null);

  const digits = phone.replace(/\D/g, "").slice(-10);

  // Look up the customer once 10 digits are typed, so the shopkeeper can see
  // "Ramesh · owes ₹840" and know they've got the right person.
  useEffect(() => {
    setMatch(null);
    if (digits.length !== 10) return;
    let cancelled = false;
    api.searchCustomers(digits).then((rows) => {
      if (!cancelled) setMatch(rows.find((r) => r.phone === digits) || null);
    });
    return () => {
      cancelled = true;
    };
  }, [digits]);

  function reset() {
    setPhone("");
    setBill("");
    setPaid("");
    setName("");
    setItems([{ description: "", qty: "", amount: "" }]);
    setShowItems(false);
    phoneRef.current?.focus();
  }

  async function save(e) {
    e?.preventDefault();
    if (saving) return;
    setError("");
    setSaving(true);
    try {
      const filledItems = showItems
        ? items
            .filter((i) => i.description.trim())
            .map((i) => ({ description: i.description, qty: i.qty || null, amount: i.amount || null }))
        : [];
      const res = await api.createEntry({
        phone,
        bill_amount: bill,
        amount_paid: paid || "0",
        name: name || null,
        items: filledItems,
      });
      setLastSaved(res);
      reset();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const billNum = parseFloat(bill) || 0;
  const paidNum = parseFloat(paid) || 0;
  const credit = billNum - paidNum;

  return (
    <form className="card entry" onSubmit={save}>
      <label>
        Customer phone
        <input
          ref={phoneRef}
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

      {digits.length === 10 &&
        (match ? (
          <div className="match">
            <strong>{match.name || "Unnamed customer"}</strong>
            {match.balance_paise > 0 ? ` · already owes ${rupees(match.balance_paise)}` : " · nothing pending"}
            {match.opted_out && <span className="warn"> · opted out of messages</span>}
          </div>
        ) : (
          <label className="soft">
            New customer: name (optional)
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ramesh" />
          </label>
        ))}

      <div className="row">
        <label>
          Bill ₹
          <input ref={billRef} inputMode="decimal" value={bill} onChange={(e) => setBill(e.target.value)} placeholder="500" />
        </label>
        <label>
          Paid now ₹
          <input inputMode="decimal" value={paid} onChange={(e) => setPaid(e.target.value)} placeholder="0" />
        </label>
      </div>

      {billNum > 0 && (
        <div className={credit > 0 ? "credit" : "credit none"}>
          {credit > 0 ? `On credit: ₹${credit.toLocaleString("en-IN")}` : "Nothing owed on this bill"}
        </div>
      )}

      <button type="button" className="link" onClick={() => setShowItems((s) => !s)}>
        {showItems ? "− Hide items" : "+ Add items (optional)"}
      </button>
      {showItems && (
        <div className="items">
          {items.map((it, i) => (
            <div className="row" key={i}>
              <input
                placeholder="Item"
                value={it.description}
                onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))}
              />
              <input
                className="narrow"
                placeholder="Qty"
                value={it.qty}
                onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, qty: e.target.value } : x)))}
              />
              <input
                className="narrow"
                placeholder="₹"
                inputMode="decimal"
                value={it.amount}
                onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))}
              />
            </div>
          ))}
          <button type="button" className="link" onClick={() => setItems([...items, { description: "", qty: "", amount: "" }])}>
            + another item
          </button>
        </div>
      )}

      {error && <div className="error">{error}</div>}
      <button className="primary" disabled={saving || digits.length < 10 || credit <= 0}>
        {saving ? "Saving…" : "Save credit"}
      </button>

      {lastSaved && (
        <div className="saved">
          ✓ Saved {rupees(lastSaved.due.balance_paise)} for {lastSaved.customer.name || lastSaved.customer.phone}
          {lastSaved.is_new_customer && " (new customer)"}. Total pending: {rupees(lastSaved.customer.balance_paise)}
        </div>
      )}
    </form>
  );
}
