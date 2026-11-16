import { useEffect, useState } from "react";
import { api, initial, rupees } from "../api/client.js";
import { IconBack, IconCheck } from "../icons.jsx";

// SIMULATED customer UPI app (stands in for GPay / PhonePe / Paytm).
// It opens pre-filled from the shop's UPI link: shop's UPI ID, amount, note.
// "Pay" sends only what a bank would report to the shop (payer UPI ID, name,
// amount, note), so matching has to work out who paid, as in real life.
//
// "Demo controls" recreate the tricky real-world cases: a customer deleting
// the note, changing the amount, or paying from a family member's UPI ID.
export default function UpiApp({ token, onClose }) {
  const [page, setPage] = useState(null);
  const [error, setError] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [payerVpa, setPayerVpa] = useState("");
  const [payerName, setPayerName] = useState("");
  const [showDemo, setShowDemo] = useState(false);
  const [paying, setPaying] = useState(false);
  const [done, setDone] = useState(null);

  useEffect(() => {
    api
      .getPayPage(token)
      .then((p) => {
        setPage(p);
        setAmount(p.balance_paise ? String(p.balance_paise / 100) : "");
        setNote(p.note);
        setPayerVpa(p.demo_payer_vpa);
        setPayerName(p.demo_payer_name);
      })
      .catch((e) => setError(e.message));
  }, [token]);

  async function pay(e) {
    e.preventDefault();
    setError("");
    setPaying(true);
    try {
      await api.bankNotification({ payer_vpa: payerVpa, payer_name: payerName, amount, note: note || null });
      setDone({ amount: Number(amount), ref: String(Math.floor(1e11 + Math.random() * 9e11)) });
    } catch (err) {
      setError(err.message);
    } finally {
      setPaying(false);
    }
  }

  const bar = (
    <div className="upi-bar">
      {onClose && (
        <button type="button" onClick={onClose} aria-label="Back to chat">
          <IconBack />
        </button>
      )}
      Your UPI app (simulated)
    </div>
  );

  if (!page)
    return (
      <div className="upi">
        {bar}
        <p className="upi-pending" style={{ marginTop: 40 }}>{error || "Opening…"}</p>
      </div>
    );

  if (!page.upi_link)
    return (
      <div className="upi">
        {bar}
        <p className="upi-pending" style={{ margin: "40px 24px" }}>
          {page.shop_name} hasn’t added a UPI ID yet. Please pay at the shop.
        </p>
      </div>
    );

  if (done)
    return (
      <div className="upi">
        <div className="upi-done">
          <div className="tick">
            <IconCheck size={36} />
          </div>
          <h2>₹{done.amount.toLocaleString("en-IN")} paid</h2>
          <p className="muted">to {page.shop_name}</p>
          <p className="hint">UPI reference {done.ref} (made up for the demo)</p>
        </div>
        <div className="upi-foot">
          {onClose && (
            <button className="btn btn-primary btn-block" onClick={onClose}>
              Back to chat
            </button>
          )}
        </div>
      </div>
    );

  return (
    <form className="upi" onSubmit={pay}>
      {bar}
      <div className="upi-payee">
        <span className="initial">{initial(page.shop_name)}</span>
        <div className="name">{page.shop_name}</div>
        <div className="vpa">{page.shop_upi_id}</div>
      </div>

      <label className="upi-amount" aria-label="Amount">
        <span>₹</span>
        <input inputMode="decimal" placeholder="0" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </label>
      <p className="upi-pending">
        {page.balance_paise > 0 ? `You owe ${rupees(page.balance_paise)}. You can pay part of it.` : "Nothing pending with this shop."}
      </p>

      <div className="upi-note">
        <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note" aria-label="Note" />
      </div>

      {showDemo ? (
        <div className="demo-controls">
          <label className="field">
            Paying from UPI ID
            <input className="input" value={payerVpa} onChange={(e) => setPayerVpa(e.target.value)} />
          </label>
          <label className="field">
            Name the bank shows
            <input className="input" value={payerName} onChange={(e) => setPayerName(e.target.value)} />
          </label>
          <p className="hint">
            The shop only sees these two fields, the amount and the note. Try deleting the note or paying from a family member’s UPI ID.
          </p>
        </div>
      ) : (
        <button type="button" className="btn-text" style={{ alignSelf: "center", marginTop: 14 }} onClick={() => setShowDemo(true)}>
          Demo: change who is paying
        </button>
      )}

      <div className="upi-foot">
        {error && <div className="notice error">{error}</div>}
        <button className="btn btn-primary btn-block" disabled={paying || !amount}>
          {paying ? "Paying…" : `Pay ₹${Number(amount || 0).toLocaleString("en-IN")}`}
        </button>
      </div>
    </form>
  );
}
