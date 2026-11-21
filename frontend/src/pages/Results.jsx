import { useEffect, useState } from "react";
import { api, longWhen, rupees } from "../api/client.js";

// Is this getting more dues paid on time, without upsetting customers?
// Definitions live in backend/app/services/metrics.py and are repeated in
// plain words at the bottom of this screen.

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const pct = (r) => (r === null || r === undefined ? "–" : `${Math.round(r * 100)}%`);

export default function Results() {
  const [m, setM] = useState(null);
  useEffect(() => {
    api.getMetrics().then(setM);
  }, []);
  if (!m) return <p className="empty">Loading…</p>;

  const r = m.recovery;
  const g = m.guardrails;
  const maxBucket = Math.max(1, ...m.outstanding.buckets.map((b) => b.paise));

  return (
    <>
      <div className="page-head">
        <h1>Results</h1>
        <p>Is this getting more dues paid on time? As of {longWhen(m.as_of)}.</p>
      </div>

      {/* Primary metric: one headline number */}
      <section className="hero-metric" aria-labelledby="hero-h">
        <h2 id="hero-h">Recovered within 30 days</h2>
        {r.mature_bills === 0 ? (
          <p className="muted">
            No bills are 30 days old yet, so there’s nothing to judge.{" "}
            {r.too_new_bills > 0 && `${r.too_new_bills} newer ${r.too_new_bills === 1 ? "bill is" : "bills are"} still within their first 30 days.`}
          </p>
        ) : (
          <>
            <div className="hero-number">{pct(r.rate)}</div>
            <p>
              {r.recovered_bills} of {r.mature_bills} bills that are at least 30 days old were fully paid within 30 days.
            </p>
            <p className="muted small">
              By amount: {rupees(r.recovered_paise)} of {rupees(r.mature_paise)} ({pct(r.rate_by_amount)}).
              {r.written_off_bills > 0 && ` ${r.written_off_bills} written off.`}
              {r.too_new_bills > 0 && ` ${r.too_new_bills} newer ${r.too_new_bills === 1 ? "bill is" : "bills are"} too new to count.`}
            </p>
          </>
        )}
      </section>

      {/* Experiment */}
      <section className="section" aria-labelledby="exp-h">
        <div className="section-head">
          <h2 id="exp-h">Experiment: reading replies</h2>
        </div>
        <p className="muted small" style={{ marginBottom: 12 }}>
          Recovered within 30 days, split by whether reply reading was on when the bill was created.
        </p>
        <div className="bars">
          {m.experiment.arms.map((a) => (
            <div className="bar-row" key={a.label} title={`${a.label}: ${a.recovered_bills} of ${a.mature_bills} bills recovered within 30 days`}>
              <span className="bar-label">{a.label}</span>
              <span className="bar-track">
                {a.rate > 0 && <span className="bar-fill ink" style={{ width: `${a.rate * 100}%` }} />}
              </span>
              <span className="bar-value">
                {a.mature_bills === 0 ? (
                  <span className="muted small">No judged bills yet</span>
                ) : (
                  <>
                    <strong>{pct(a.rate)}</strong> <span className="muted small">{plural(a.mature_bills, "bill")}</span>
                  </>
                )}
              </span>
            </div>
          ))}
        </div>
        {m.experiment.arms.some((a) => a.small_sample) && (
          <p className="notice-plain">
            Fewer than {m.experiment.small_group} judged bills in a group, so any difference may just be chance. Keep both
            running longer before deciding.
          </p>
        )}
        {m.experiment.untracked_bills > 0 && (
          <p className="hint">{m.experiment.untracked_bills} older bills were created before groups were tracked and are left out of this comparison.</p>
        )}
      </section>

      {/* Guardrails */}
      <section className="section" aria-labelledby="guard-h">
        <div className="section-head">
          <h2 id="guard-h">Guardrails</h2>
        </div>
        <p className="muted small" style={{ marginBottom: 12 }}>
          These should stay low. If they rise, reminders may be annoying people.
        </p>
        <div className="tiles">
          <div className="tile">
            <div className="tile-number">{pct(g.opt_out_rate)}</div>
            <div className="tile-label">Opted out of messages</div>
            <div className="hint">
              {g.opted_out} of {g.messaged_customers} customers who got a message.
              {g.deleted_customers > 0 && ` ${g.deleted_customers} asked for their data to be deleted.`}
            </div>
          </div>
          <div className="tile">
            <div className="tile-number">{pct(g.stopped_rate)}</div>
            <div className="tile-label">Stopped buying on credit after a reminder</div>
            <div className="hint">
              {g.reminded_30_days_ago === 0
                ? "No one's first reminder is 30 days old yet."
                : `${g.stopped_buying_on_credit} of ${g.reminded_30_days_ago} customers first reminded 30+ days ago haven't bought on credit since.`}{" "}
              Cash purchases aren’t recorded, so some may still be shopping.
            </div>
          </div>
        </div>
      </section>

      {/* Promises and replies */}
      <section className="section" aria-labelledby="prom-h">
        <div className="section-head">
          <h2 id="prom-h">Promises</h2>
        </div>
        <ul className="rows">
          {[
            ["call", "Made on a call"],
            ["reply", "Read from a reply"],
          ].map(([k, label]) => {
            const p = m.promises[k];
            return (
              <li key={k}>
                <div className="row">
                  <span className="row-main">
                    <span className="row-title" style={{ display: "block" }}>
                      {label}
                    </span>
                    <span className="row-sub">
                      {p.total === 0 ? "None yet" : `${p.kept} kept, ${p.broken} not kept, ${p.pending} still waiting`}
                    </span>
                  </span>
                  <span className="row-end">
                    <strong>{pct(p.kept_rate)}</strong>
                    <div className="hint">kept</div>
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
        <p className="hint" style={{ marginTop: 10 }}>
          Replies received: {m.replies.received}.{" "}
          {m.replies.read > 0
            ? `Read ${m.replies.read}: ${plural(m.replies.promise, "promise")}, ${m.replies.already_paid} "already paid", ${m.replies.other} unclear (${m.replies.by_gemini} by Gemini, ${m.replies.by_rules} by the built-in reader).`
            : "None read yet (reply reading is off, or no replies)."}
        </p>
      </section>

      {/* Age of unpaid money */}
      <section className="section" aria-labelledby="age-h">
        <div className="section-head">
          <h2 id="age-h">Still owed, by age</h2>
          <span className="money due">{rupees(m.outstanding.paise)}</span>
        </div>
        <div className="bars">
          {m.outstanding.buckets.map((b) => (
            <div className="bar-row" key={b.label} title={`${b.label}: ${rupees(b.paise)} across ${b.bills} bills`}>
              <span className="bar-label">{b.label}</span>
              <span className="bar-track">
                {b.paise > 0 && <span className="bar-fill due" style={{ width: `${(b.paise / maxBucket) * 100}%` }} />}
              </span>
              <span className="bar-value">
                <strong>{rupees(b.paise)}</strong> <span className="muted small">{plural(b.bills, "bill")}</span>
              </span>
            </div>
          ))}
        </div>
      </section>

      <details className="definitions">
        <summary>How these are counted</summary>
        <ul>
          <li>
            <strong>Recovered within 30 days:</strong> only bills at least 30 days old are counted, because newer ones can’t be
            judged yet. A bill counts as recovered if it was fully paid within 30 days of the sale. Written-off bills count as
            not recovered.
          </li>
          <li>
            <strong>Experiment groups:</strong> each bill remembers whether reply reading was switched on when it was created,
            so switching it later doesn’t move old bills between groups.
          </li>
          <li>
            <strong>Opted out:</strong> customers who replied STOP or whose messages you stopped, out of customers who got at
            least one message. Deleted customers are counted separately.
          </li>
          <li>
            <strong>Stopped buying on credit:</strong> customers whose first reminder was at least 30 days ago and who haven’t
            had a credit sale since. A rough signal only: cash purchases aren’t recorded.
          </li>
          <li>
            <strong>Promises kept:</strong> out of promises whose date has passed. A promise is kept if the customer paid in
            full by the promised day.
          </li>
        </ul>
      </details>
    </>
  );
}
