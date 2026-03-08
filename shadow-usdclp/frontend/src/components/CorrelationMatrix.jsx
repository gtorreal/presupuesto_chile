import { useEffect, useState } from "react";
import { api } from "../api/client";

const WINDOW_OPTIONS = [30, 60, 90, 180];

const PAIR_LABELS = {
  USDBRL: "USDBRL",
  USDMXN: "USDMXN",
  USDCOP: "USDCOP",
  DXY: "DXY",
  COPPER: "Cobre (inv.)",
  VIX: "VIX",
  US10Y: "US 10Y",
  ECH: "ECH ETF",
  SHADOW_USDCLP: "Shadow USDCLP",
};

function corrColor(value) {
  if (value == null) return "bg-gray-800 text-gray-600";
  const abs = Math.abs(value);
  if (abs >= 0.8) return value > 0 ? "bg-red-900 text-red-200" : "bg-emerald-900 text-emerald-200";
  if (abs >= 0.5) return value > 0 ? "bg-red-950 text-red-300" : "bg-emerald-950 text-emerald-300";
  if (abs >= 0.3) return "bg-gray-800 text-gray-300";
  return "bg-gray-900 text-gray-500";
}

export default function CorrelationMatrix() {
  const [window, setWindow] = useState(90);
  const [data, setData] = useState(null);

  useEffect(() => {
    api.getCorrelations(window).then(setData).catch(() => {});
  }, [window]);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-gray-200">Matriz de correlaciones</h2>
          <p className="text-xs text-gray-500 mt-0.5">Correlación de Pearson vs USDCLP (retornos diarios)</p>
        </div>
        <div className="flex gap-1">
          {WINDOW_OPTIONS.map((w) => (
            <button
              key={w}
              onClick={() => setWindow(w)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                window === w
                  ? "bg-amber-500 text-gray-900"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {w}d
            </button>
          ))}
        </div>
      </div>

      {!data || data.pairs.length === 0 ? (
        <div className="h-32 flex items-center justify-center text-gray-600 text-sm">
          Sin datos de correlación aún (se calculan diariamente a las 00:00 UTC)
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {data.pairs.map((pair) => {
            const label = PAIR_LABELS[pair.pair_b] || pair.pair_b;
            return (
              <div
                key={pair.pair_b}
                className={`rounded-lg p-3 text-center ${corrColor(pair.correlation)}`}
              >
                <p className="text-xs font-medium mb-1">{label}</p>
                <p className="text-xl font-bold tabular-nums">
                  {pair.correlation != null ? pair.correlation.toFixed(3) : "—"}
                </p>
                <p className="text-xs opacity-60 mt-0.5">
                  R²={pair.r_squared?.toFixed(3) ?? "—"} β={pair.beta?.toFixed(3) ?? "—"}
                </p>
                <p className="text-xs opacity-40">{pair.observations}obs</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
