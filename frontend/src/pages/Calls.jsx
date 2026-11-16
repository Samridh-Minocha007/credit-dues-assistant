import { useEffect, useState } from "react";
import { api, appNow, rupees, shortWhen } from "../api/client.js";
import { IconCall } from "../icons.jsx";

// Step 4-5 of the core loop, on its own Calls screen (kept apart from
// payments on Today so calls never get lost among other things):
//   "Call these customers": reminders have stopped; a call works better now.
//   After the call, one tap: promised a date / disputed / write off.
//   Also: who promised to pay (waiting), and open disputes.

export default function CallsPage({ onChange }) {
  const [list, setList] = useState(null);
  const load = () => api.getCallList().then(setList);
  useEffect(() => {
    load();
  }, []);
  const done = () => {
    load();
    onChange?.();
  };

  return (
    <>
      <div className="page-head">
        <h1>Calls</h1>
        <p>Customers whose dues are old enough that a call works better than another message.</p>
      </div>
      {list === null ? <p className="empty">Loading…</p> : <CallSection list={list} onDone={done} />}
    </>
  );
}

function CallSection({ list, onDone }) {
  const { to_call, promised, disputed } = list;
  return (
    <>
      <section aria-labelledby="call-h">
        <div className="section-head">
          <h2 id="call-h">To call</h2>
          {to_call.length > 0 && <span className="muted small">{to_call.length} waiting</span>}
        </div>
        {to_call.length === 0 ? (
          <p className="empty">
            No one to call right now. Customers appear here when their oldest bill passes the limit in Settings (30 days by
            default), and their automatic reminders stop.
          </p>
        ) : (
          to_call.map((c) => <CallCard key={c.customer_id} c={c} onDone={onDone} />)
        )}
      </section>

      {promised.length > 0 && (
        <section className="section" aria-labelledby="promised-h">
          <div className="section-head">
            <h2 id="promised-h">Promised to pay</h2>
          </div>
          <ul className="rows">
            {promised.map((c) => (
              <li key={c.customer_id}>
                <div className="row">
                  <span className="row-main">
                    <span className="row-title" style={{ display: "block" }}>
                      {c.name || c.phone}
                    </span>
                    <span className="row-sub">
                      By {formatDate(c.latest_promise.promised_date)}. Reminders are paused until then.
                    </span>
                  </span>
                  <span className="money due">{rupees(c.balance_paise)}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {disputed.length > 0 && (
        <section className="section" aria-labelledby="disputed-h">
          <div className="section-head">
            <h2 id="disputed-h">Disputed</h2>
          </div>
          <p className="muted small" style={{ marginBottom: 8 }}>
            No messages go to these customers until you sort it out.
          </p>
          <ul className="rows">
            {disputed.map((c) => (
              <DisputedRow key={c.customer_id} c={c} onDone={onDone} />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function formatDate(isoDate) {
  return new Date(isoDate + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

function isoDaysFromToday(n) {
  const d = appNow();
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function CallCard({ c, onDone }) {
  const [mode, setMode] = useState(null); // null | promised | disputed | written_off
  const [date, setDate] = useState(isoDaysFromToday(3));
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const p = c.latest_promise;

  async function save(outcome) {
    setError("");
    setSaving(true);
    try {
      await api.callOutcome(c.customer_id, { outcome, promised_date: outcome === "promised_date" ? date : null, note: note || null });
      onDone();
    } catch (e) {
      setError(e.message);
      setSaving(false);
    }
  }

  const pretty = c.phone.replace(/^(\d{5})(\d{5})$/, "$1 $2");

  return (
    <div className="call-card">
      <div className="top">
        <div>
          <strong style={{ fontSize: "var(--t-md)" }}>{c.name || pretty}</strong>
          {c.name && <span className="muted"> {pretty}</span>}
        </div>
        <span className="money due" style={{ fontSize: "var(--t-lg)" }}>
          {rupees(c.balance_paise)}
        </span>
      </div>
      <p className="small muted">
        {c.reason}.{c.last_reminder_at ? ` Last reminder ${shortWhen(c.last_reminder_at)}.` : " No reminder sent yet."}
        {p && p.status === "kept" && ` Kept their promise for ${formatDate(p.promised_date)}.`}
      </p>

      <div className="actions">
        <a className="btn call-btn" href={`tel:+91${c.phone}`}>
          <IconCall size={18} /> Call {pretty}
        </a>
      </div>

      {mode === null && (
        <div className="outcomes">
          <span className="small muted">After the call:</span>
          <div className="actions">
            <button className="btn" onClick={() => setMode("promised")}>
              Promised a date
            </button>
            <button className="btn" onClick={() => setMode("disputed")}>
              Disputed
            </button>
            <button className="btn-text" onClick={() => setMode("written_off")}>
              Write off
            </button>
          </div>
        </div>
      )}

      {mode === "promised" && (
        <div className="outcome-form">
          <span className="small">When did they say they’ll pay?</span>
          <div className="chips" style={{ margin: 0 }}>
            {[
              [1, "Tomorrow"],
              [3, "In 3 days"],
              [7, "In a week"],
            ].map(([n, label]) => (
              <button key={n} type="button" className="chip" aria-pressed={date === isoDaysFromToday(n)} onClick={() => setDate(isoDaysFromToday(n))}>
                {label}
              </button>
            ))}
            <input className="input date-input" type="date" value={date} min={isoDaysFromToday(0)} onChange={(e) => setDate(e.target.value)} aria-label="Promised date" />
          </div>
          <input className="input" placeholder="Note (optional), e.g. after salary" value={note} onChange={(e) => setNote(e.target.value)} />
          <p className="hint">Reminders pause until {date ? formatDate(date) : "then"}. That morning they get one gentle reminder.</p>
          <div className="actions">
            <button className="btn btn-primary" disabled={saving || !date} onClick={() => save("promised_date")}>
              Save promise
            </button>
            <button className="btn-text" onClick={() => setMode(null)}>
              Back
            </button>
          </div>
        </div>
      )}

      {mode === "disputed" && (
        <div className="outcome-form">
          <input className="input" placeholder="What do they disagree with? (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <p className="hint">All messages to them stop until you mark it resolved.</p>
          <div className="actions">
            <button className="btn btn-primary" disabled={saving} onClick={() => save("disputed")}>
              Mark as disputed
            </button>
            <button className="btn-text" onClick={() => setMode(null)}>
              Back
            </button>
          </div>
        </div>
      )}

      {mode === "written_off" && (
        <div className="outcome-form">
          <p className="small">
            Write off {rupees(c.balance_paise)}? Their bills are closed as unpaid and they won’t get any more reminders. The record
            stays in their history.
          </p>
          <div className="actions">
            <button className="btn btn-danger" disabled={saving} onClick={() => save("written_off")}>
              Write off {rupees(c.balance_paise)}
            </button>
            <button className="btn-text" onClick={() => setMode(null)}>
              Back
            </button>
          </div>
        </div>
      )}

      {error && <div className="notice error">{error}</div>}
    </div>
  );
}

function DisputedRow({ c, onDone }) {
  const [confirm, setConfirm] = useState(false);
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
    <li>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <span className="row-main">
          <span className="row-title" style={{ display: "block" }}>
            {c.name || c.phone}
          </span>
          <span className="row-sub">Oldest bill {c.oldest_age_days} days old</span>
        </span>
        <span className="money due">{rupees(c.balance_paise)}</span>
        <div className="actions" style={{ width: "100%", gap: "8px 16px", display: "flex", flexWrap: "wrap" }}>
          {!confirm ? (
            <>
              <button className="btn" onClick={() => act(() => api.resolveDispute(c.customer_id))}>
                Sorted out, resume
              </button>
              <button className="btn-text" onClick={() => setConfirm(true)}>
                Write off
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-danger" onClick={() => act(() => api.callOutcome(c.customer_id, { outcome: "written_off" }))}>
                Write off {rupees(c.balance_paise)}
              </button>
              <button className="btn-text" onClick={() => setConfirm(false)}>
                Back
              </button>
            </>
          )}
        </div>
        {error && <div className="notice error" style={{ width: "100%" }}>{error}</div>}
      </div>
    </li>
  );
}
