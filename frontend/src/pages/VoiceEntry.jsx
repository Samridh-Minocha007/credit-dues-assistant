import { useState } from "react";
import { api } from "../api/client.js";
import { t } from "../i18n.jsx";

// Voice entry: tap the mic, say "Ramesh paanch sau, do sau diye", and the form
// fills in. Uses the browser's own speech recognition (Chrome on Android
// supports it), so nothing is recorded or sent anywhere except the text.
// It never saves: the shopkeeper sees what was heard and presses Save.
const SpeechRecognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

export default function VoiceEntry({ onFill }) {
  const [listening, setListening] = useState(false);
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState("");
  const [heard, setHeard] = useState(null);
  const [error, setError] = useState("");

  async function understand(text) {
    setError("");
    try {
      const r = await api.parseVoice(text);
      setHeard(r);
      onFill(r);
    } catch (e) {
      setError(e.message);
    }
  }

  function listen() {
    if (!SpeechRecognition) {
      setTyping(true);
      return;
    }
    const rec = new SpeechRecognition();
    // Indian English copes well with names and spoken digits ("Ramesh 500").
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.onresult = (e) => understand(e.results[0][0].transcript);
    rec.onerror = () => setError(t("Couldn’t hear that. Try again, or type it."));
    rec.onend = () => setListening(false);
    setListening(true);
    rec.start();
  }

  return (
    <div className="voice">
      <div className="voice-row">
        <button type="button" className={`btn voice-btn ${listening ? "on" : ""}`} onClick={listen} aria-label={t("Say it instead")}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <rect x="9" y="3" width="6" height="11" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
          </svg>
          {listening ? t("Listening…") : t("Say it instead")}
        </button>
        {!typing && (
          <button type="button" className="btn-text" onClick={() => setTyping(true)}>
            {t("or type it")}
          </button>
        )}
      </div>
      {typing && (
        <div className="voice-row">
          <input
            className="input"
            placeholder={t("e.g. Ramesh 500, 200 diye")}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (typed.trim()) understand(typed);
              }
            }}
          />
          <button type="button" className="btn" disabled={!typed.trim()} onClick={() => understand(typed)}>
            {t("Fill form")}
          </button>
        </div>
      )}
      {heard && (
        <p className="hint" role="status">
          {t("Heard “{text}”. Check the form, then save.", { text: heard.heard })}
        </p>
      )}
      {heard && heard.candidates.length > 1 && (
        <div className="chips" style={{ margin: 0 }}>
          <span className="small muted">{t("Which one?")}</span>
          {heard.candidates.map((c) => (
            <button key={c.id} type="button" className="chip" onClick={() => onFill({ ...heard, phone: c.phone, name: c.name, customer_id: c.id })}>
              {c.name}
            </button>
          ))}
        </div>
      )}
      {error && <div className="notice error">{error}</div>}
    </div>
  );
}
