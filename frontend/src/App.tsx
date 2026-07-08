import { useState } from "react";
import ClientDetail from "./pages/ClientDetail";
import Portfolio from "./pages/Portfolio";
import Simulation from "./pages/Simulation";

type View = { page: "portfolio" } | { page: "client"; id: string } | { page: "simulation" };

export default function App() {
  const [view, setView] = useState<View>({ page: "portfolio" });

  const tab = (page: "portfolio" | "simulation", label: string) => (
    <button
      onClick={() => setView({ page })}
      className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
        view.page === page || (page === "portfolio" && view.page === "client")
          ? "bg-sky-700 text-white"
          : "text-slate-600 hover:bg-slate-200"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">FinHealth Platform</h1>
          <p className="text-xs text-slate-500">
            Risk-informed financial health & insurance — loan-officer decision support (synthetic
            demo data)
          </p>
        </div>
        <nav className="flex gap-2">
          {tab("portfolio", "Portfolio")}
          {tab("simulation", "Simulation")}
        </nav>
      </header>

      {view.page === "portfolio" && (
        <Portfolio onOpenClient={(id) => setView({ page: "client", id })} />
      )}
      {view.page === "client" && (
        <ClientDetail clientId={view.id} onBack={() => setView({ page: "portfolio" })} />
      )}
      {view.page === "simulation" && <Simulation />}
    </div>
  );
}
