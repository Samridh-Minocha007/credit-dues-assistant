import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// One-time setup. The shopkeeper approves the wording and schedule here ONCE;
// after that, reminders go out automatically without asking per message.
export default function Setup({ onApprovedChange }) {
  const [s, setS] = useState(null);
  const [draft, setDraft] = useState({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api.getSettings().then(load);
  }, []);

  function load(settings) {
    setS(settings);
    setDraft({
      name: settings.name,
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
    onApprovedChange?.(settings.approved);
  }

  const set = (k) => (e) => setDraft({ ...draft, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function save() {
    setError("");
    setSaved("");
    try {
      load(
        await api.updateSettings({
          ...draft,
          reminder_day: Number(draft.reminder_day),
          escalation_days: Number(draft.escalation_days),
          escalation_min_days: Number(draft.escalation_min_days),
          max_reminders_per_month: Number(draft.max_reminders_per_month),
        })
      );
      setSaved("Saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  async function approve() {
    setError("");
    load(await api.approveSettings());
    setSaved("Approved. Weekly reminders will use this wording and schedule.");
  }

  if (!s) return <div className="card">Loading…</div>;

  return (
    <div className="card setup">
      <div className={s.approved ? "status ok" : "status pending"}>
        {s.approved
          ? `✓ Approved on ${new Date(s.settings_approved_at).toLocaleDateString("en-IN")}`
          : "Not approved yet: no automatic reminders will be sent"}
      </div>

      <h3>Shop</h3>
      <label>
        Shop name (shown in messages)
        <input value={draft.name} onChange={set("name")} />
      </label>

      <h3>Weekly reminder</h3>
      <div className="row">
        <label>
          Day
          <select value={draft.reminder_day} onChange={set("reminder_day")}>
            {DAYS.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label>
          Time
          <input type="time" value={draft.reminder_time} onChange={set("reminder_time")} />
        </label>
      </div>
      <label>
        Wording (must include {"{amount}"} and {"{link}"}; can use {"{name}"}, {"{shop}"})
        <textarea rows={4} value={draft.message_template} onChange={set("message_template")} />
      </label>
      <div className="preview">
        <div className="muted small">Customer will see (last saved version):</div>
        {s.preview}
      </div>

      <h3>When to ask you to call</h3>
      <div className="row">
        <label>
          Oldest due older than (days)
          <input inputMode="numeric" value={draft.escalation_days} onChange={set("escalation_days")} />
        </label>
      </div>
      <div className="row">
        <label>
          …or balance above ₹
          <input inputMode="decimal" value={draft.escalation_amount} onChange={set("escalation_amount")} />
        </label>
        <label>
          and older than (days)
          <input inputMode="numeric" value={draft.escalation_min_days} onChange={set("escalation_min_days")} />
        </label>
      </div>

      <h3>Guardrails</h3>
      <div className="row">
        <label>
          No messages from
          <input type="time" value={draft.quiet_start} onChange={set("quiet_start")} />
        </label>
        <label>
          until
          <input type="time" value={draft.quiet_end} onChange={set("quiet_end")} />
        </label>
      </div>
      <label>
        Max reminders per customer per month
        <input inputMode="numeric" value={draft.max_reminders_per_month} onChange={set("max_reminders_per_month")} />
      </label>

      <h3>Experiment</h3>
      <label className="check">
        <input type="checkbox" checked={draft.reply_parsing_enabled} onChange={set("reply_parsing_enabled")} />
        Read customer replies and record promises (variant)
      </label>

      {error && <div className="error">{error}</div>}
      {saved && <div className="saved">{saved}</div>}
      <div className="row buttons">
        <button onClick={save}>Save changes</button>
        <button className="primary" onClick={approve} disabled={s.approved}>
          Approve wording &amp; schedule
        </button>
      </div>
      <p className="muted small">Changing the wording, day or time needs approval again.</p>
    </div>
  );
}
