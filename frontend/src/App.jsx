import { useEffect, useState } from "react";
import { api } from "./api/client.js";
import QuickEntry from "./pages/QuickEntry.jsx";
import Customers from "./pages/Customers.jsx";
import Setup from "./pages/Setup.jsx";

// Simple tabs instead of a router library: three screens don't need URLs yet.
const TABS = [
  ["entry", "New entry"],
  ["customers", "Customers"],
  ["setup", "Setup"],
];

export default function App() {
  const [tab, setTab] = useState("entry");
  const [approved, setApproved] = useState(true);

  // Re-check approval whenever the tab changes, so the banner updates after Setup.
  useEffect(() => {
    api.getSettings().then((s) => setApproved(s.approved)).catch(() => {});
  }, [tab]);

  return (
    <div className="app">
      <header>
        <h1>Credit dues assistant</h1>
        <span className="badge">Concept prototype · messages &amp; payments simulated</span>
      </header>

      {!approved && tab !== "setup" && (
        <button className="banner" onClick={() => setTab("setup")}>
          Reminders are off until you approve the wording and schedule. Tap to set up →
        </button>
      )}

      <nav>
        {TABS.map(([key, label]) => (
          <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </nav>

      <main>
        {tab === "entry" && <QuickEntry />}
        {tab === "customers" && <Customers />}
        {tab === "setup" && <Setup onApprovedChange={setApproved} />}
      </main>
    </div>
  );
}
