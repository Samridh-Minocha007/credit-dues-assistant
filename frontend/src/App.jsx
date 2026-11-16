import { useCallback, useEffect, useState } from "react";
import { api, setClockOffset } from "./api/client.js";
import { IconActivity, IconCustomers, IconSettings, IconToday } from "./icons.jsx";
import Today from "./pages/Today.jsx";
import Customers from "./pages/Customers.jsx";
import Activity from "./pages/Activity.jsx";
import Settings from "./pages/Settings.jsx";
import CustomerPhone from "./pages/CustomerPhone.jsx";

// Three places for daily work, plus settings (used once, so it sits apart).
const PLACES = [
  { key: "today", label: "Today", Icon: IconToday },
  { key: "customers", label: "Customers", Icon: IconCustomers },
  { key: "activity", label: "Activity", Icon: IconActivity },
];

export default function App() {
  // Customer-facing demo pages, separate from the shopkeeper's app:
  //   /pay/<token>    the link inside the message: opens the (simulated) UPI app
  //   /phone/<token>  the customer's (simulated) phone with their chat
  const m = window.location.pathname.match(/^\/(pay|phone)\/([\w-]+)/);
  if (m) return <CustomerPhone token={m[2]} startOnPay={m[1] === "pay"} />;
  return <ShopApp />;
}

function ShopApp() {
  const [view, setView] = useState("today");
  const [shop, setShop] = useState(null);
  const [toCheck, setToCheck] = useState(0);

  // Shop settings and the "payments to check" count are shown in the shell,
  // so refresh them whenever the screen changes or something is saved.
  const refresh = useCallback(() => {
    api.getClock().then((c) => setClockOffset(c.offset_seconds)).catch(() => {});
    api.getSettings().then(setShop).catch(() => {});
    api.getIncoming("needs_review").then((r) => setToCheck(r.length)).catch(() => {});
  }, []);
  useEffect(refresh, [view, refresh]);

  const tabs = PLACES.map(({ key, label, Icon }) => (
    <button key={key} className="tab" aria-current={view === key ? "page" : undefined} onClick={() => setView(key)}>
      <Icon />
      {label}
      {key === "today" && toCheck > 0 && (
        <span className="dot" aria-label={`${toCheck} to check`}>
          {toCheck}
        </span>
      )}
    </button>
  ));
  const brand = (
    <div className="brand">
      <strong>{shop?.name || "Your shop"}</strong>
      <span>Concept prototype, all simulated</span>
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
        <button className="tab settings-link" aria-current={view === "settings" ? "page" : undefined} onClick={() => setView("settings")}>
          <IconSettings />
          Settings
        </button>
      </aside>

      <div className="main">
        {/* Phones: top bar with settings, tabs along the bottom. */}
        <header className="topbar">
          {brand}
          <button
            className="icon-btn"
            aria-label="Settings"
            aria-pressed={view === "settings"}
            onClick={() => setView(view === "settings" ? "today" : "settings")}
          >
            <IconSettings />
          </button>
        </header>

        <main className="content">
          {view === "today" && <Today shop={shop} onChange={refresh} go={setView} />}
          {view === "customers" && <Customers />}
          {view === "activity" && <Activity />}
          {view === "settings" && <Settings onSaved={refresh} />}
        </main>

        <nav className="tabbar mobile-tabs" aria-label="Main">
          {tabs}
        </nav>
      </div>
    </div>
  );
}
