import { useState, useEffect } from "react";
import AcercaDePanel from "./components/AcercaDePanel";
import ShadowPricePanel from "./components/ShadowPricePanel";
import FactorsTable from "./components/FactorsTable";
import HistoricalChart from "./components/HistoricalChart";
import CorrelationMatrix from "./components/CorrelationMatrix";
import CalibrationPanel from "./components/CalibrationPanel";
import SettingsPanel from "./components/SettingsPanel";
import ApiDocsPanel from "./components/ApiDocsPanel";
import LogsPanel from "./components/LogsPanel";
import LoginPage from "./components/LoginPage";
import BudaLogo from "./components/BudaLogo";

const TABS = [
  { id: "acerca", label: "Acerca de" },
  { id: "dashboard", label: "Dashboard" },
  { id: "factors", label: "Factores" },
  { id: "historical", label: "Histórico" },
  { id: "correlations", label: "Correlaciones" },
  { id: "calibration", label: "Calibración" },
  { id: "logs", label: "Logs" },
  { id: "settings", label: "Configuración" },
];

function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return null;
  }
}

// NOTE: JWT stored in localStorage (not httpOnly cookie). Acceptable risk for
// internal app with few users behind VPN. XSS would require CSP bypass first.
export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("shadow_token"));
  const [activeTab, setActiveTab] = useState("dashboard");
  const [showApiDocs, setShowApiDocs] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);

  // Listen for session expiry triggered by the API client
  useEffect(() => {
    const onLogout = () => setToken(null);
    window.addEventListener("shadow:logout", onLogout);
    return () => window.removeEventListener("shadow:logout", onLogout);
  }, []);

  // Fetch current user info after login
  useEffect(() => {
    if (!token) {
      setCurrentUser(null);
      return;
    }
    const payload = parseJwt(token);
    if (!payload) return;

    fetch("/api/v1/users/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) setCurrentUser(data);
        else setCurrentUser({ username: payload.sub, role: payload.role || "admin", otp_enabled: false });
      })
      .catch(() => {
        setCurrentUser({ username: payload.sub, role: payload.role || "admin", otp_enabled: false });
      });
  }, [token]);

  function handleLogin(newToken) {
    setToken(newToken);
  }

  function handleLogout() {
    localStorage.removeItem("shadow_token");
    setToken(null);
  }

  if (!token) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BudaLogo size={32} />
            <div>
              <h1 className="font-bold text-gray-100 leading-none">Shadow USDCLP</h1>
              <p className="text-xs text-gray-500">Buda.com — Índice sintético</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
              Live
            </span>
            {currentUser && (
              <span className="text-xs text-gray-600">{currentUser.username}</span>
            )}
            <button
              onClick={handleLogout}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Cerrar sesión
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="max-w-7xl mx-auto px-4">
          <nav className="flex gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id); setShowApiDocs(false); }}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-amber-500 text-amber-400"
                    : "border-transparent text-gray-500 hover:text-gray-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {activeTab === "acerca" && <AcercaDePanel />}
        {activeTab === "dashboard" && (
          <div className="space-y-4">
            <ShadowPricePanel />
            <FactorsTable />
          </div>
        )}
        {activeTab === "factors" && <FactorsTable />}
        {activeTab === "historical" && <HistoricalChart />}
        {activeTab === "correlations" && <CorrelationMatrix />}
        {activeTab === "calibration" && <CalibrationPanel />}
        {activeTab === "logs" && <LogsPanel />}
        {activeTab === "settings" && currentUser && !showApiDocs && (
          <SettingsPanel currentUser={currentUser} onShowDocs={() => setShowApiDocs(true)} />
        )}
        {activeTab === "settings" && showApiDocs && (
          <ApiDocsPanel onBack={() => setShowApiDocs(false)} />
        )}
      </main>
    </div>
  );
}
