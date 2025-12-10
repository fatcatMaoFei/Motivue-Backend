type Tab = "today" | "baseline" | "train" | "report" | "settings";

const labels: Record<Tab, string> = {
  today: "Today",
  baseline: "Baseline",
  train: "Train",
  report: "Report",
  settings: "Settings",
};

type Props = {
  active: Tab;
  onChange: (tab: Tab) => void;
};

export function NavBar({ active, onChange }: Props) {
  return (
    <nav className="nav">
      <div className="nav-logo">Motivue</div>
      <div className="nav-items">
        {(Object.keys(labels) as Tab[]).map((key) => (
          <button
            key={key}
            className={`nav-btn ${active === key ? "is-active" : ""}`}
            onClick={() => onChange(key)}
          >
            {labels[key]}
          </button>
        ))}
      </div>
    </nav>
  );
}

// inline styles for nav (kept local to avoid extra CSS file)
const style = document.createElement("style");
style.innerHTML = `
.nav {
  background: #0f1621;
  border-right: 1px solid rgba(255,255,255,0.06);
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 24px 18px;
}
.nav-logo {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.4px;
}
.nav-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.nav-btn {
  text-align: left;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid transparent;
  background: rgba(255,255,255,0.04);
  color: #e8ecf2;
  cursor: pointer;
  transition: all 120ms ease;
}
.nav-btn:hover {
  border-color: rgba(255,255,255,0.12);
}
.nav-btn.is-active {
  background: linear-gradient(135deg, #1c2a3c, #162030);
  border-color: rgba(77,224,194,0.45);
  box-shadow: 0 10px 24px rgba(0,0,0,0.25);
}
`;
document.head.appendChild(style);
