import { useCallback, useEffect, useState } from "react";
import { AUTH_EVENT, SERVER_EVENT, api, setClockOffset } from "./api/client.js";
import { t } from "./i18n.jsx";
import { IconActivity, IconCall, IconCustomers, IconResults, IconSettings, IconToday } from "./icons.jsx";
import Today from "./pages/Today.jsx";
import Customers from "./pages/Customers.jsx";
import Activity from "./pages/Activity.jsx";
import Settings from "./pages/Settings.jsx";
import CallsPage from "./pages/Calls.jsx";
import Results from "./pages/Results.jsx";
import CustomerPhone from "./pages/CustomerPhone.jsx";
import Statement from "./pages/Statement.jsx";
import Login from "./pages/Login.jsx";

// Four places for daily work, plus settings (used once, so it sits apart).
const PLACES = [
  { key: "today", label: "Today", Icon: IconToday },
  { key: "calls", label: "Calls", Icon: IconCall },
  { key: "customers", label: "Customers", Icon: IconCustomers },
  { key: "activity", label: "Activity", Icon: IconActivity },
];

export default function App() {
  // Customer-facing demo pages, separate from the shopkeeper's app:
  //   /pay/<token>    the link inside the message: opens the (simulated) UPI app
  //   /phone/<token>  the customer's (simulated) phone with their chat
  //   /statement/<token>  the customer's statement (printable)
  const m = window.location.pathname.match(/^\/(pay|phone|statement)\/([\w-]+)/);
  if (m && m[1] === "statement") return <Statement token={m[2]} />;
  if (m) return <CustomerPhone token={m[2]} startOnPay={m[1] === "pay"} />;
  return <LoginGate />;
}

// In pilot mode the shop must log in first; locally this shows the app straight away.
function LoginGate() {
  const [state, setState] = useState("checking"); // checking | login | app
  const check = () =>
    api
      .me()
      .then((r) => setState(r.auth_required && !r.logged_in ? "login" : "app"))
      .catch(() => setState("app")); // server down: the app shows its own banner
  useEffect(() => {
    check();
    const onAuth = () => setState("login");
    window.addEventListener(AUTH_EVENT, onAuth);
    return () => window.removeEventListener(AUTH_EVENT, onAuth);
  }, []);
  if (state === "checking") return null;
  if (state === "login") return <Login onDone={() => setState("app")} />;
  return <ShopApp />;
}

function ShopApp() {
  // Remembered for this browser tab, so switching language (which re-mounts
  // the app) keeps you on the same screen.
  const [view, setViewState] = useState(() => sessionStorage.getItem("view") || "today");
  const setView = (v) => {
    sessionStorage.setItem("view", v);
    setViewState(v);
  };
  // Tapping the tab you're already on starts that screen fresh (e.g. back to
  // the customer list from a customer's page), like most phone apps.
  const [visit, setVisit] = useState(0);
  const go = (key) => {
    if (key === view) setVisit((n) => n + 1);
    setView(key);
  };
  const [shop, setShop] = useState(null);
  const [toCheck, setToCheck] = useState(0); // UPI payments waiting for the shopkeeper
  const [toCall, setToCall] = useState(0); // customers on the call list

  // Shop settings and the "payments to check" count are shown in the shell,
  // so refresh them whenever the screen changes or something is saved.
  // False when the backend can't be reached (see api/client.js).
  const [serverUp, setServerUp] = useState(true);
  useEffect(() => {
    const onStatus = (e) => setServerUp(e.detail.up);
    window.addEventListener(SERVER_EVENT, onStatus);
    return () => window.removeEventListener(SERVER_EVENT, onStatus);
  }, []);

  const refresh = useCallback(() => {
    api.getClock().then((c) => setClockOffset(c.offset_seconds)).catch(() => {});
    api.getSettings().then(setShop).catch(() => {});
    Promise.all([api.getIncoming("needs_review"), api.getCallList()])
      .then(([review, calls]) => {
        setToCheck(review.length);
        setToCall(calls.to_call.length);
      })
      .catch(() => {});
  }, []);
  useEffect(refresh, [view, refresh]);

  const tabs = PLACES.map(({ key, label, Icon }) => (
    <button key={key} className="tab" aria-current={view === key ? "page" : undefined} onClick={() => go(key)}>
      <Icon />
      {t(label)}
      {key === "today" && toCheck > 0 && (
        <span className="dot" aria-label={`${toCheck} payments to check`}>
          {toCheck}
        </span>
      )}
      {key === "calls" && toCall > 0 && (
        <span className="dot call" aria-label={`${toCall} customers to call`}>
          {toCall}
        </span>
      )}
    </button>
  ));
  const brand = (
    <div className="brand">
      <strong>{shop?.name || t("Your shop")}</strong>
      <span>{shop?.demo_mode ? t("Demo shop with generated data") : t("Concept prototype, all simulated")}</span>
    </div>
  );

  return (
    <div className="shell">
      {/* Wide screens: left rail with settings at the bottom. */}
      <aside className="side">
        {brand}
        <nav className="tabbar" aria-label="Main">
          {tabs}
        </nav>
        {/* Results and Settings are for the owner, not daily work, so they sit apart at the bottom. */}
        <button className="tab settings-link" aria-current={view === "results" ? "page" : undefined} onClick={() => go("results")}>
          <IconResults />
          {t("Results")}
        </button>
        <button className="tab" aria-current={view === "settings" ? "page" : undefined} onClick={() => go("settings")}>
          <IconSettings />
          {t("Settings")}
        </button>
      </aside>

      <div className="main">
        {/* Phones: top bar with settings, tabs along the bottom. */}
        <header className="topbar">
          {brand}
          <button
            className="icon-btn"
            aria-label="Results"
            aria-pressed={view === "results"}
            onClick={() => setView(view === "results" ? "today" : "results")}
          >
            <IconResults />
          </button>
          <button
            className="icon-btn"
            style={{ marginLeft: 0 }}
            aria-label="Settings"
            aria-pressed={view === "settings"}
            onClick={() => setView(view === "settings" ? "today" : "settings")}
          >
            <IconSettings />
          </button>
        </header>

        <main className="content" key={`${view}-${visit}`}>
          {!serverUp && (
            <div className="server-down" role="alert">
              <strong>{t("Can’t reach the app server.")}</strong> The backend isn’t running, so nothing can load. Start it from the{" "}
              <code>backend</code> folder with <code>.venv/Scripts/python -m uvicorn app.main:app</code>, then{" "}
              <button className="btn-text" onClick={() => window.location.reload()}>
                reload this page
              </button>
              .
            </div>
          )}
          {view === "today" && <Today shop={shop} onChange={refresh} go={go} />}
          {view === "calls" && <CallsPage onChange={refresh} />}
          {view === "customers" && <Customers />}
          {view === "activity" && <Activity />}
          {view === "results" && <Results />}
          {view === "settings" && <Settings onSaved={refresh} />}
        </main>

        <nav className="tabbar mobile-tabs" aria-label="Main">
          {tabs}
        </nav>
      </div>
    </div>
  );
}
