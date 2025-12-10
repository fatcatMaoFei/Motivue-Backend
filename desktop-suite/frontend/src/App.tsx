import { useState } from "react";
import { NavBar } from "./app/components/NavBar";
import { Today } from "./app/pages/Today";
import { Baseline } from "./app/pages/Baseline";
import { Train } from "./app/pages/Train";
import { Report } from "./app/pages/Report";
import { Settings } from "./app/pages/Settings";

type Tab = "today" | "baseline" | "train" | "report" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("today");

  const render = () => {
    switch (tab) {
      case "today":
        return <Today />;
      case "baseline":
        return <Baseline />;
      case "train":
        return <Train />;
      case "report":
        return <Report />;
      case "settings":
        return <Settings />;
      default:
        return null;
    }
  };

  return (
    <div className="app-shell">
      <NavBar active={tab} onChange={setTab} />
      <main className="app-content">{render()}</main>
    </div>
  );
}
