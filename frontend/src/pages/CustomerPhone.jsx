import { useEffect, useState } from "react";
import { api, initial } from "../api/client.js";
import { IconRefresh } from "../icons.jsx";
import UpiApp from "./UpiApp.jsx";

// SIMULATED customer's phone, for demos: how the feature looks to the
// customer. Their chat with the shop, and tapping the payment link opens
// their UPI app, pre-filled. A demo view, not a customer app (out of scope).
export default function CustomerPhone({ token, startOnPay = false }) {
  const [phone, setPhone] = useState(null);
  const [error, setError] = useState("");
  const [paying, setPaying] = useState(startOnPay);

  const load = () => api.getPhone(token).then(setPhone).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, [token]);

  const clock = new Date().toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }).replace(/\s?[ap]m/i, "");

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
                {phone?.messages.map((m) => (
                  <Bubble key={m.id} m={m} onPay={() => setPaying(true)} />
                ))}
              </div>
              <div className="chat-compose">
                <div>Replying comes in a later version</div>
              </div>
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
