import { useEffect, useState } from "react";
import { api } from "./api";
import AgentPage from "./pages/Agent";
import CaseStudyPage from "./pages/CaseStudy";
import EvaluationPage from "./pages/Evaluation";
import ResearchPage from "./pages/Research";

const PAGES = [
  { path: "agent", label: "Agent" },
  { path: "case-study", label: "Case study" },
  { path: "evaluation", label: "Evaluation" },
  { path: "research", label: "Research" },
] as const;
type Path = (typeof PAGES)[number]["path"];
type Theme = "light" | "dark" | null;

function currentPath(): Path {
  const h = location.hash.replace(/^#\/?/, "");
  const p = PAGES.find((x) => h.startsWith(x.path));
  return p ? p.path : "agent"; // "#scenario=N" deep links land on the agent page
}

function storedTheme(): Theme {
  try {
    const t = localStorage.getItem("why-theme");
    return t === "light" || t === "dark" ? t : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [path, setPath] = useState<Path>(currentPath());
  const [health, setHealth] = useState<{ ok: boolean; records?: number } | null>(null);
  const [theme, setTheme] = useState<Theme>(storedTheme);

  useEffect(() => {
    const on = () => { setPath(currentPath()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", on);
    api.health().then((h) => setHealth({ ok: h.hindsight, records: h.records })).catch(() => setHealth({ ok: false }));
    return () => window.removeEventListener("hashchange", on);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme) root.dataset.theme = theme; else delete root.dataset.theme;
    try { if (theme) localStorage.setItem("why-theme", theme); else localStorage.removeItem("why-theme"); } catch { /* private window */ }
  }, [theme]);

  const dark = theme ? theme === "dark" : window.matchMedia?.("(prefers-color-scheme: dark)").matches;

  return (
    <>
      <header className="top">
        <a className="brand" href="#/agent">
          <span className="logo">WH<i>Y</i></span>
          <span className="tag">remembers why each decision was made, and notices when the reasons stop being true</span>
        </a>
        <nav className="tabs">
          {PAGES.map((p) => (
            <a key={p.path} href={`#/${p.path}`} className={path === p.path ? "on" : ""}>{p.label}</a>
          ))}
        </nav>
        <div className="org">
          <span className="ws">Keelwright Freight</span>
          <span className="conn" title={health?.ok ? "Hindsight memory bank connected" : "Hindsight unreachable"}>
            <span className={`dot ${health == null ? "" : health.ok ? "ok" : "bad"}`} />
            Hindsight{health?.records != null && ` · ${health.records} memories`}
          </span>
          <button type="button" className="themebtn" onClick={() => setTheme(dark ? "light" : "dark")}
            title={dark ? "Switch to light theme" : "Switch to dark theme"} aria-label="Toggle theme">{dark ? "☀" : "☾"}</button>
        </div>
      </header>
      {/* the agent page stays mounted so a running question survives a quick look at another page */}
      <div hidden={path !== "agent"}><AgentPage /></div>
      {path === "case-study" && <CaseStudyPage />}
      {path === "evaluation" && <EvaluationPage />}
      {path === "research" && <ResearchPage />}
    </>
  );
}
