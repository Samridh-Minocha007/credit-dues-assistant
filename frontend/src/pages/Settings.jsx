import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { IconCheck } from "../icons.jsx";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// Set up once. The shopkeeper approves the reminder wording and schedule here;
// after that, reminders go out on their own without asking each time.
export default function Settings({ onSaved }) {
  const [s, setS] = useState(null);
  const [d, setD] = useState({});
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    api.getSettings().then(load);
  }, []);

  function load(settings) {
    setS(settings);
    setD({
      name: settings.name,
      upi_id: settings.upi_id || "",
      reminder_day: settings.reminder_day,
      reminder_time: settings.reminder_time,
      message_template: settings.message_template,
      escalation_days: settings.escalation_days,
      escalation_amount: String(settings.escalation_amount_paise / 100),
      escalation_min_days: settings.escalation_min_days,
      quiet_start: settings.quiet_start,
      quiet_end: settings.quiet_end,
      max_reminders_per_month: settings.max_reminders_per_month,
      reply_parsing_enabled: settings.reply_parsing_enabled,
    });
  }

  const set = (k) => (e) => {
    setStatus("");
    setD({ ...d, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  };

  const payload = () => ({
    ...d,
    upi_id: d.upi_id || null,
    reminder_day: Number(d.reminder_day),
    escalation_days: Number(d.escalation_days),
    escalation_min_days: Number(d.escalation_min_days),
    max_reminders_per_month: Number(d.max_reminders_per_month),
  });

  async function save(e) {
    e?.preventDefault();
    setError("");
    try {
      load(await api.updateSettings(payload()));
      setStatus("Changes saved.");
      onSaved?.();
    } catch (err) {
      setError(err.message);
    }
  }

  // Save first, so the approval always covers exactly the text on screen.
  async function approve() {
    setError("");
    try {
      await api.updateSettings(payload());
      load(await api.approveSettings());
      setStatus("Reminder approved. It will go out every week on its own.");
      onSaved?.();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!s) return <p className="empty">Loading…</p>;

  return (
    <form onSubmit={save}>
      <div className="page-head">
        <h1>Settings</h1>
        <p>Set these once. You can change them any time.</p>
      </div>

      <section className="settings-group">
        <h2>Your shop</h2>
        <label className="field">
          Shop name, as customers see it
          <input className="input" value={d.name} onChange={set("name")} />
        </label>
        <label className="field">
          Shop’s UPI ID, the one behind your QR code
          <input className="input" value={d.upi_id} onChange={set("upi_id")} placeholder="sharmastore@okaxis" autoCapitalize="none" spellCheck={false} />
        </label>
        <p className="hint">Customers pay straight to this UPI ID from their message. This app never holds money.</p>
      </section>

      <section className="settings-group">
        <h2>Weekly reminder</h2>
        <p>Goes to every customer who owes money, once a week, without asking you each time.</p>

        {s.approved ? (
          <div className="approval on">
            <IconCheck />
            <p>Approved on {new Date(s.settings_approved_at).toLocaleDateString("en-IN", { day: "numeric", month: "long" })}. Changing the wording, day or time will need approval again.</p>
          </div>
        ) : (
          <div className="approval off">
            <p>
              <strong>Not approved yet.</strong> No reminders go out until you approve the message below.
            </p>
            <button type="button" className="btn btn-primary" onClick={approve}>
              Approve this reminder
            </button>
          </div>
        )}

        <div className="grid-2">
          <label className="field">
            Day
            <select className="select" value={d.reminder_day} onChange={set("reminder_day")}>
              {DAYS.map((day, i) => (
                <option key={day} value={i}>
                  {day}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Time
            <input className="input" type="time" value={d.reminder_time} onChange={set("reminder_time")} />
          </label>
        </div>
        <label className="field">
          Message
          <textarea className="textarea" rows={4} value={d.message_template} onChange={set("message_template")} />
        </label>
        <p className="hint">
          Keep {"{amount}"} and {"{link}"} in the message. You can also use {"{name}"} and {"{shop}"}.
        </p>
        <div className="field">
          How the customer sees it
          <div className="preview-bubble">{s.preview}</div>
        </div>
      </section>

      <section className="settings-group">
        <h2>When to suggest a call</h2>
        <p>Automatic reminders stop and the customer appears on your call list.</p>
        <label className="field">
          When their oldest bill is this many days old
          <input className="input" inputMode="numeric" value={d.escalation_days} onChange={set("escalation_days")} style={{ maxWidth: 160 }} />
        </label>
        <div className="grid-2">
          <label className="field">
            Or sooner, if they owe more than ₹
            <input className="input" inputMode="decimal" value={d.escalation_amount} onChange={set("escalation_amount")} />
          </label>
          <label className="field">
            and the bill is this many days old
            <input className="input" inputMode="numeric" value={d.escalation_min_days} onChange={set("escalation_min_days")} />
          </label>
        </div>
      </section>

      <section className="settings-group">
        <h2>Being polite</h2>
        <div className="grid-2">
          <label className="field">
            No messages after
            <input className="input" type="time" value={d.quiet_start} onChange={set("quiet_start")} />
          </label>
          <label className="field">
            or before
            <input className="input" type="time" value={d.quiet_end} onChange={set("quiet_end")} />
          </label>
        </div>
        <label className="field">
          Most reminders a customer gets in a month
          <input className="input" inputMode="numeric" value={d.max_reminders_per_month} onChange={set("max_reminders_per_month")} style={{ maxWidth: 160 }} />
        </label>
      </section>

      <section className="settings-group">
        <h2>Experiment</h2>
        <label className="toggle">
          <input type="checkbox" checked={d.reply_parsing_enabled} onChange={set("reply_parsing_enabled")} />
          <span>
            Read customer replies like “kal dunga” and note the promised date
            <span className="hint" style={{ display: "block" }}>
              Turn on for some shops and off for others to compare recovery against plain weekly reminders.
            </span>
          </span>
        </label>
      </section>

      <div className="save-bar">
        <button className="btn btn-primary">Save changes</button>
        {status && <span className="muted small">{status}</span>}
        {error && <span className="notice error" style={{ flex: 1 }}>{error}</span>}
      </div>
    </form>
  );
}
