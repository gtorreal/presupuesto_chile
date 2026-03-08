import { useEffect, useState } from "react";
import { api } from "../api/client";

const BETA_LABELS = {
  beta_ndf: "NDF USDCLP 1M",
  beta_usdbrl: "USDBRL",
  beta_dxy: "DXY (Dollar Index)",
  beta_copper_inv: "Cobre (inverso)",
  beta_usdmxn: "USDMXN",
  beta_vix: "VIX",
  beta_us10y: "US 10Y Yield",
  beta_usdcop: "USDCOP",
  beta_ech: "ECH ETF",
};

function DeltaCell({ value }) {
  if (value == null) return <span className="text-gray-600">—</span>;
  const isPos = value >= 0;
  // Positive delta (USD strengthens) = red; negative (CLP strengthens) = green
  return (
    <span className={`font-mono font-medium ${isPos ? "text-red-400" : "text-emerald-400"}`}>
      {isPos ? "+" : ""}
      {(value * 100).toFixed(3)}%
    </span>
  );
}

export default function FactorsTable() {
  const [data, setData] = useState(null);

  const load = async () => {
    try {
      const d = await api.getShadowPrice();
      setData(d);
    } catch (_) {}
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, []);

  if (!data) {
    return <div className="bg-gray-900 rounded-xl p-6 h-64 animate-pulse" />;
  }

  const { factors, factor_deltas } = data;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-800">
        <h2 className="font-semibold text-gray-200">Factores en tiempo real</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Contribución de cada variable al Shadow USDCLP
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 uppercase tracking-wider border-b border-gray-800">
              <th className="text-left px-6 py-3">Factor</th>
              <th className="text-right px-4 py-3">Precio actual</th>
              <th className="text-right px-4 py-3">Al cierre BEC</th>
              <th className="text-right px-4 py-3">Δ% desde cierre</th>
              <th className="text-right px-4 py-3">Beta (β)</th>
              <th className="text-right px-6 py-3">Contribución</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {Object.entries(BETA_LABELS).map(([betaKey, label]) => {
              const factor = factors[betaKey];
              const delta = factor_deltas[betaKey];
              const beta = 0; // We'd need active betas from model/params
              const contribution = delta != null ? delta * beta : null;
              const available = factor != null;

              return (
                <tr
                  key={betaKey}
                  className={`hover:bg-gray-800/50 transition-colors ${
                    !available ? "opacity-40" : ""
                  }`}
                >
                  <td className="px-6 py-3 font-medium text-gray-200">
                    <span
                      className={`inline-block w-2 h-2 rounded-full mr-2 ${
                        available ? "bg-emerald-400" : "bg-gray-600"
                      }`}
                    />
                    {label}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-gray-300">
                    {factor?.now?.toFixed(4) ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-gray-500">
                    {factor?.at_close?.toFixed(4) ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <DeltaCell value={delta} />
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-gray-400">
                    {beta !== 0 ? beta.toFixed(2) : "—"}
                  </td>
                  <td className="px-6 py-3 text-right">
                    <DeltaCell value={contribution} />
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
