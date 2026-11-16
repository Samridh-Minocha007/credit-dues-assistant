import { useEffect, useState } from "react";
import { api, appNow, initial, setClockOffset, timeOf } from "../api/client.js";
import { IconRefresh } from "../icons.jsx";
import UpiApp from "./UpiApp.jsx";

// SIMULATED customer's phone, for demos: how the feature looks to the
// customer. Their chat with the shop, and tapping the payment link opens
// their UPI app, pre-filled. A demo view, not a customer app (out of scope).
export default function CustomerPhone({ token, startOnPay = false }) {
  const [phone, setPhone] = useState(null);
  const [error, setError] = useState("");
  const [paying, setPaying] = useState(startOnPay);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  async function send(text) {
    if (!text.trim()) return;
    setSending(true);
    try {
      setPhone(await api.sendReply(token, text));
      setDraft("");
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  const load = () => api.getPhone(token).then(setPhone).catch((e) => setError(e.message));
  const [, setTick] = useState(0);
  useEffect(() => {
    load();
    // Use the demo clock, so the phone shows the same time as the shop's app.
    api.getClock().then((c) => {
      setClockOffset(c.offset_seconds);
      setTick((t) => t + 1);
    });
  }, [token]);

  const clock = appNow().toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }).replace(/\s?[ap]m/i, "");

  return (
    <div className="demo-stage">
      <p className="demo-caption">
        Demo: what {phone?.customer_name || "the customer"} sees on their phone. No real messages are sent and no money moves.
      </p>
      <div className="device">
        <div className="device-screen">
          <div className="island" />
          <div className="statusbar">
            <span>{clock}</span>
            <span>5G</span>
          </div>

          {paying ? (
            <UpiApp
              token={token}
              onClose={() => {
                setPaying(false);
                load();
              }}
            />
          ) : (
            <>
              <div className="chat-top">
                <span className="initial">{initial(phone?.shop_name)}</span>
                <div>
                  <div className="name">{phone?.shop_name || " "}</div>
                  <div className="sub">Business account</div>
                </div>
                <button className="icon-btn" onClick={load} aria-label="Refresh chat">
                  <IconRefresh />
                </button>
              </div>
              <div className="chat-body">
                {error && <div className="notice error">{error}</div>}
                {phone && phone.messages.length === 0 && <span className="day-pill">No messages yet</span>}
                {phone && phone.messages.length > 0 && <span className="day-pill">Messages from {phone.shop_name}</span>}
                {phone?.messages.map((m) =>
                  m.direction === "in" ? (
                    <div key={m.id} className="bubble-out">
                      {m.body}
                      <div className="meta">{timeOf(m.created_at)}</div>
                    </div>
                  ) : (
                    <Bubble key={m.id} m={m} onPay={() => setPaying(true)} />
                  )
                )}
              </div>
              <form
                className="chat-compose"
                onSubmit={(e) => {
                  e.preventDefault();
                  send(draft);
                }}
              >
                <div className="quick" aria-label="Try a reply">
                  {["STOP", "START", "kal dunga"].map((t) => (
                    <button type="button" key={t} onClick={() => send(t)} disabled={sending}>
                      {t}
                    </button>
                  ))}
                </div>
                <div className="compose-row">
                  <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Message the shop" aria-label="Message the shop" />
                  <button disabled={sending || !draft.trim()}>Send</button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Bubble({ m, onPay }) {
  const held = m.status === "scheduled";
  const when = new Date(m.sent_at || m.scheduled_for || m.created_at);
  // Pull the link out of the text and show it as a tappable payment card.
  const [before, link, after] = m.body.split(/(https?:\/\/\S+)/);
  return (
    <div className={`bubble-in ${held ? "held" : ""}`}>
      <span>{before}</span>
      {link && (
        <button className="pay-card" onClick={onPay}>
          <span>
            <strong>Pay on UPI</strong>
            <span>Opens your UPI app</span>
          </span>
          <span className="go">Pay</span>
        </button>
      )}
      {after && <span>{after.trim()}</span>}
      <div className="meta">
        {held
          ? `Arrives ${when.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })} (no messages at night)`
          : when.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}
      </div>
    </div>
  );
}
