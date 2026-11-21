import { useState } from "react";
import { api, setToken } from "../api/client.js";
import { t } from "../i18n.jsx";

// Pilot mode only: each shop logs in with its phone number and a PIN.
export default function Login({ onDone }) {
  const [mode, setMode] = useState("login"); // login | signup
  const [shopName, setShopName] = useState("");
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const r = mode === "login" ? await api.login(phone, pin) : await api.signup(shopName, phone, pin);
      setToken(r.token);
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form className="entry login-card" onSubmit={submit}>
        <div>
          <h1>{mode === "login" ? t("Log in to your shop") : t("Create your shop")}</h1>
          <p className="muted small">{t("Concept prototype, all simulated")}</p>
        </div>
        {mode === "signup" && (
          <label className="field">
            {t("Shop name")}
            <input className="input" value={shopName} onChange={(e) => setShopName(e.target.value)} autoFocus />
          </label>
        )}
        <label className="field">
          {t("Your phone number")}
          <input className="input" inputMode="numeric" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} autoFocus={mode === "login"} />
        </label>
        <label className="field">
          {mode === "login" ? t("PIN") : t("Choose a 4–6 digit PIN")}
          <input className="input" type="password" inputMode="numeric" autoComplete={mode === "login" ? "current-password" : "new-password"} value={pin} onChange={(e) => setPin(e.target.value)} />
        </label>
        {error && <div className="notice error">{error}</div>}
        <button className="btn btn-primary btn-block" disabled={busy}>
          {mode === "login" ? t("Log in") : t("Create shop")}
        </button>
        <button type="button" className="btn-text" style={{ alignSelf: "center" }} onClick={() => setMode(mode === "login" ? "signup" : "login")}>
          {mode === "login" ? t("New here? Create your shop") : t("Already have a shop? Log in")}
        </button>
      </form>
    </div>
  );
}
