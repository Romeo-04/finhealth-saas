import { useState } from "react";
import ClientDetail from "./pages/ClientDetail";
import Portfolio from "./pages/Portfolio";
import Simulation from "./pages/Simulation";
import { Logo } from "./components/ui";

type View = { page: "portfolio" } | { page: "client"; id: string } | { page: "simulation" };

export default function App() {
  const [view, setView] = useState<View>({ page: "portfolio" });
  const portfolioActive = view.page === "portfolio" || view.page === "client";

  const tab = (page: "portfolio" | "simulation", label: string, active: boolean) => (
    <button
      onClick={() => setView({ page })}
      aria-current={active ? "page" : undefined}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-white text-slate-900 shadow-sm"
          : "text-slate-500 hover:text-slate-800"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <Logo className="h-5 w-5" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-[15px] font-bold tracking-tight text-slate-900">
                  FinHealth Platform
                </h1>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  Demo
                </span>
              </div>
              <p className="text-[11px] leading-tight text-slate-500">
                Risk-informed financial health &amp; bancassurance — loan-officer decision support
              </p>
            </div>
          </div>
          <nav className="flex gap-1 rounded-lg bg-slate-100 p-1">
            {tab("portfolio", "Portfolio", portfolioActive)}
            {tab("simulation", "Simulation", view.page === "simulation")}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        {view.page === "portfolio" && (
          <Portfolio onOpenClient={(id) => setView({ page: "client", id })} />
        )}
        {view.page === "client" && (
          <ClientDetail clientId={view.id} onBack={() => setView({ page: "portfolio" })} />
        )}
        {view.page === "simulation" && <Simulation />}
      </main>

      <footer className="mx-auto max-w-6xl px-4 pb-8 pt-2 text-center text-[11px] text-slate-400 sm:px-6">
        Synthetic demo data · no real client PII · decision support, not automated underwriting
      </footer>
    </div>
  );
}
