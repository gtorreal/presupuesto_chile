import { useEffect, useState } from "react";
import { api } from "../api/client";

// All known sources with their metadata
const SOURCES = [
  { name: "buda",        label: "Buda.com",          loop: "fast", configKey: "collector_fast_interval",     marketHours: false },
  { name: "mindicador",  label: "Mindicador (BCCh)",  loop: "fast", configKey: "collector_fast_interval",     marketHours: true  },
  { name: "cmf",         label: "CMF Chile",          loop: "fast", configKey: "collector_fast_interval",     marketHours: true  },
  { name: "frankfurter", label: "Frankfurter (ECB)",  loop: "fast", configKey: "collector_fast_interval",     marketHours: false },
  { name: "ndf_stub",    label: "NDF USDCLP 1M",      loop: "fast", configKey: "collector_fast_interval",     marketHours: true  },
  { name: "bec_stub",    label: "BEC / Datatec",      loop: "fast", configKey: "collector_fast_interval",     marketHours: true  },
  { name: "yfinance",    label: "Yahoo Finance",       loop: "slow", configKey: "collector_yfinance_interval", marketHours: false },
];

const CONFIG_LABELS = {
  collector_fast_interval:     "Loop rápido (Buda, Frankfurter, CMF…)",
  collector_yfinance_interval: "Loop lento (Yahoo Finance)",
};

function getStatus(source, statusMap) {
  const s = statusMap[source.name];
  if (!s) {
    // Never seen — market hours sources may just need the market to open
    return source.marketHours ? "closed" : "error";
  }
  if (s.is_live) return "ok";
  if (source.marketHours) return "closed";
  return "error";
}

function StatusBadge({ status }) {
  if (status === "ok") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400">
        <span className="w-2 h-2 rounded-full bg-emerald-400" />
        Activo
      </span>
    );
  }
  if (status === "closed") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-red-400">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        Mercado cerrado
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-amber-400">
      <span className="w-2 h-2 rounded-full bg-amber-400" />
      Error / sin datos
    </span>
  );
}

function formatTime(isoString) {
  if (!isoString) return "—";
  const d = new Date(isoString);
  return d.toLocaleString("es-CL", { dateStyle: "short", timeStyle: "medium" });
}

function minutesAgoLabel(statusEntry) {
  if (!statusEntry) return "Nunca";
  const m = statusEntry.minutes_ago;
  if (m < 1) return "hace < 1 min";
  if (m < 60) return `hace ${Math.round(m)} min`;
  return `hace ${(m / 60).toFixed(1)} h`;
}

export default function SourcesConfigTable() {
  const [statusMap, setStatusMap] = useState({});
  const [config, setConfig] = useState({});
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState({});
  const [saved, setSaved] = useState({});

  const load = async () => {
    try {
      const [statusArr, cfg] = await Promise.all([api.getSourcesStatus(), api.getConfig()]);
      setStatusMap(Object.fromEntries(statusArr.map((s) => [s.source, s])));
      setConfig(cfg);
      setDrafts(Object.fromEntries(Object.entries(cfg).map(([k, v]) => [k, v.value])));
    } catch (_) {}
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const handleSave = async (key) => {
    const value = parseInt(drafts[key], 10);
    if (!value || value < 5) return;
    setSaving((p) => ({ ...p, [key]: true }));
    try {
      await api.patchConfig(key, value);
      setSaved((p) => ({ ...p, [key]: true }));
      setTimeout(() => setSaved((p) => ({ ...p, [key]: false })), 2000);
      await load();
    } catch (_) {}
    setSaving((p) => ({ ...p, [key]: false }));
  };

  // Group unique config keys in order
  const configKeys = [...new Set(SOURCES.map((s) => s.configKey))];

  return (
    <div className="space-y-4">
      {/* Interval editors */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {configKeys.map((key) => (
          <div key={key} className="bg-gray-800 rounded-lg p-3 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs text-gray-400 truncate">{CONFIG_LABELS[key] || key}</p>
              {config[key]?.updated_at && (
                <p className="text-xs text-gray-600 mt-0.5">
                  Actualizado: {formatTime(config[key].updated_at)}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <input
                type="number"
                min="5"
                className="w-20 bg-gray-700 text-gray-100 text-sm font-mono rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-amber-500 text-right"
                value={drafts[key] ?? ""}
                onChange={(e) => setDrafts((p) => ({ ...p, [key]: e.target.value }))}
              />
              <span className="text-xs text-gray-500">seg</span>
              <button
                disabled={saving[key]}
                onClick={() => handleSave(key)}
                className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                  saved[key]
                    ? "bg-emerald-700 text-white"
                    : "bg-amber-600 hover:bg-amber-500 text-gray-900"
                } disabled:opacity-50`}
              >
                {saved[key] ? "✓" : saving[key] ? "…" : "Guardar"}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Sources table */}
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-sm">
          <thead className="bg-gray-800">
            <tr>
              <th className="text-left text-gray-400 font-medium px-4 py-2.5">Fuente</th>
              <th className="text-left text-gray-400 font-medium px-4 py-2.5">Estado</th>
              <th className="text-left text-gray-400 font-medium px-4 py-2.5">Última extracción</th>
              <th className="text-right text-gray-400 font-medium px-4 py-2.5">Intervalo activo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {SOURCES.map((src) => {
              const s = statusMap[src.name];
              const status = getStatus(src, statusMap);
              const intervalSec = config[src.configKey]?.value ?? "—";
              return (
                <tr key={src.name} className="bg-gray-900 hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-3">
                    <p className="text-gray-100 font-medium">{src.label}</p>
                    <p className="text-xs text-gray-500">{src.name}</p>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={status} />
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-gray-300">{minutesAgoLabel(s)}</p>
                    {s?.last_tick && (
                      <p className="text-xs text-gray-600">{formatTime(s.last_tick)}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-gray-300">
                    {intervalSec}s
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
