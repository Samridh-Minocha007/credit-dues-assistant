import { useEffect, useState } from "react";
import { api, rupees } from "../api/client.js";

// The customer's statement, opened from the link in their message: every bill
// (with items) and payment, and the running balance. Printable / save as PDF
// with the browser's print. Shows the shop, a name and amounts: no phone number.
const KIND = { bill: "Bought on credit", payment: "Paid", written_off: "Written off by the shop" };

export default function Statement({ token }) {
  const [s, setS] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.getStatement(token).then(setS).catch((e) => setError(e.message));
  }, [token]);

  if (error) return <div className="statement"><p className="notice error">{error}</p></div>;
  if (!s) return <div className="statement"><p className="empty">Loading…</p></div>;

  const day = (iso) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

  return (
    <div className="statement">
      <header className="statement-head">
        <div>
          <h1>{s.shop_name}</h1>
          <p className="muted">
            Account statement{s.customer_name ? ` for ${s.customer_name}` : ""}, as of {day(s.generated_at)}
          </p>
        </div>
        <button className="btn no-print" onClick={() => window.print()}>
          Print or save as PDF
        </button>
      </header>

      <div className="statement-total">
        <span className="muted">Pending</span>
        <span className={`money ${s.balance_paise ? "due" : "paid"}`}>{rupees(s.balance_paise)}</span>
      </div>

      <table className="statement-table">
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Details</th>
            <th scope="col" className="num">Amount</th>
            <th scope="col" className="num">Balance</th>
          </tr>
        </thead>
        <tbody>
          {s.lines.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">No entries yet.</td>
            </tr>
          )}
          {s.lines.map((l, i) => (
            <tr key={i}>
              <td>{day(l.at)}</td>
              <td>
                {KIND[l.kind]}
                {l.text && <div className="muted small">{l.kind === "payment" ? `by ${l.text}` : l.text}</div>}
              </td>
              <td className={`num money ${l.amount_paise > 0 ? "due" : "paid"}`}>
                {l.amount_paise > 0 ? "+" : "−"}
                {rupees(Math.abs(l.amount_paise))}
              </td>
              <td className="num">{rupees(l.balance_paise)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">If something looks wrong, please speak to the shop. Concept prototype: simulated data.</p>
    </div>
  );
}
