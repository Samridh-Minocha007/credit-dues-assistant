import { useEffect, useState } from "react";
import { api, daysAgo, rupees } from "../api/client.js";

export default function Customers() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState(null); // null = still loading (don't flash "no customers")
  const [selected, setSelected] = useState(null);

  // Search as you type. Small delay so we don't call the API on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => api.searchCustomers(q).then(setRows), 200);
    return () => clearTimeout(t);
  }, [q]);

  if (selected) return <CustomerDetail id={selected} onBack={() => setSelected(null)} />;
  if (rows === null) return <div className="card">Loading…</div>;

  const total = rows.reduce((s, r) => s + r.balance_paise, 0);

  return (
    <div className="card">
      <input placeholder="Search name or phone" value={q} onChange={(e) => setQ(e.target.value)} />
      <p className="muted">
        {rows.length} customers · {rupees(total)} pending in total
      </p>
      {rows.length === 0 && <p className="muted">No customers yet. Add one from “New entry”.</p>}
      <ul className="list">
        {rows.map((r) => (
          <li key={r.id} onClick={() => setSelected(r.id)}>
            <div>
              <strong>{r.name || "Unnamed"}</strong>
              <div className="muted">
                {r.phone}
                {r.oldest_open_due_at && ` · oldest due ${daysAgo(r.oldest_open_due_at)}`}
                {r.opted_out && " · opted out"}
              </div>
            </div>
            <div className={r.balance_paise ? "amount" : "amount zero"}>{rupees(r.balance_paise)}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CustomerDetail({ id, onBack }) {
  const [c, setC] = useState(null);
  useEffect(() => {
    api.getCustomer(id).then(setC);
  }, [id]);
  if (!c) return <div className="card">Loading…</div>;

  return (
    <div className="card">
      <button className="link" onClick={onBack}>
        ← All customers
      </button>
      <h2>{c.name || "Unnamed customer"}</h2>
      <p className="muted">
        {c.phone} · customer since {new Date(c.created_at).toLocaleDateString("en-IN")}
      </p>
      <p className="big">Pending: {rupees(c.balance_paise)}</p>
      <h3>Bills on credit</h3>
      <ul className="list">
        {c.dues.map((d) => (
          <li key={d.id} className="due">
            <div>
              <div>
                {new Date(d.created_at).toLocaleDateString("en-IN")} · bill {rupees(d.bill_paise)}
                {d.paid_at_entry_paise > 0 && `, paid ${rupees(d.paid_at_entry_paise)}`}
              </div>
              {d.items.length > 0 && (
                <div className="muted">
                  {d.items.map((i) => [i.description, i.qty, i.amount_paise != null && rupees(i.amount_paise)].filter(Boolean).join(" ")).join(", ")}
                </div>
              )}
            </div>
            <div className="amount">
              {rupees(d.balance_paise)} <span className="muted">{d.status}</span>
            </div>
          </li>
        ))}
      </ul>
      <p className="muted small">
        Consent: number given to shopkeeper on {new Date(c.consent_at).toLocaleDateString("en-IN")}
      </p>
    </div>
  );
}
