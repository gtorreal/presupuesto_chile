import { useEffect, useState } from "react";
import { api } from "../api/client";
import SourcesConfigTable from "./SourcesConfigTable";

const BETA_LABELS = {
  beta_ndf: "NDF USDCLP 1M",
  beta_usdbrl: "USDBRL",
  beta_dxy: "DXY",
  beta_copper_inv: "Cobre (inv.)",
  beta_usdmxn: "USDMXN",
  beta_vix: "VIX",
  beta_us10y: "US 10Y",
  beta_usdcop: "USDCOP",
  beta_ech: "ECH ETF",
};

export default function CalibrationPanel() {
  const [modelData, setModelData] = useState(null);
  const [editedParams, setEditedParams] = useState({});
  const [windowStart, setWindowStart] = useState("2024-07-01");
  const [windowEnd, setWindowEnd] = useState(new Date().toISOString().slice(0, 10));
  const [proposed, setProposed] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);

  const loadModel = async () => {
    try {
      const d = await api.getModelParams();
      setModelData(d);
      if (d.active) setEditedParams({ ...d.active.params });
    } catch (_) {}
  };

  useEffect(() => { loadModel(); }, []);

  const handleRecalibrate = async () => {
    setLoading(true);
    setStatus(null);
    try {
      const result = await api.recalibrate(windowStart, windowEnd);
      setProposed(result);
    } catch (e) {
      setStatus({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAndActivate = async (params, name) => {
    setLoading(true);
    try {
      const saved = await api.saveParams(name, params, `Calibrado ${windowStart} a ${windowEnd}`);
      await api.activateModel(saved.id);
      setStatus({ ok: `Modelo "${name}" activado (id=${saved.id})` });
      await loadModel();
      setProposed(null);
    } catch (e) {
      setStatus({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">

    {/* Sources & Intervals */}
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <h2 className="font-semibold text-gray-200 mb-1">Fuentes de datos</h2>
      <p className="text-xs text-gray-500 mb-4">
        Estado de cada fuente y frecuencia de extracción. Los cambios de intervalo se aplican en el próximo ciclo.
      </p>
      <SourcesConfigTable />
    </div>

    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <h2 className="font-semibold text-gray-200 mb-1">Calibración del modelo</h2>
      <p className="text-xs text-gray-500 mb-5">
        Edita betas manualmente o recalibra con regresión OLS.
      </p>

      {status?.ok && (
        <div className="mb-4 bg-emerald-900/50 border border-emerald-700 text-emerald-300 rounded p-3 text-sm">
          {status.ok}
        </div>
      )}
      {status?.error && (
        <div className="mb-4 bg-red-900/50 border border-red-700 text-red-300 rounded p-3 text-sm">
          {status.error}
        </div>
      )}

      {/* Current active params */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-300">
            Betas activos{modelData?.active ? ` — ${modelData.active.name}` : ""}
          </h3>
          <span className="text-xs text-gray-500">
            {modelData?.active?.r_squared != null
              ? `R²=${modelData.active.r_squared}`
              : ""}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {Object.entries(BETA_LABELS).map(([key, label]) => (
            <div key={key} className="bg-gray-800 rounded p-2">
              <p className="text-xs text-gray-500 mb-1">{label}</p>
              <input
                type="number"
                step="0.01"
                className="w-full bg-gray-700 text-gray-100 text-sm font-mono rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-amber-500"
                value={editedParams[key] ?? ""}
                onChange={(e) =>
                  setEditedParams((prev) => ({ ...prev, [key]: parseFloat(e.target.value) }))
                }
              />
            </div>
          ))}
        </div>
        <button
          className="mt-3 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-gray-900 font-medium text-sm rounded transition-colors disabled:opacity-50"
          disabled={loading}
          onClick={() => handleSaveAndActivate(editedParams, `manual_${Date.now()}`)}
        >
          Guardar y activar betas editados
        </button>
      </div>

      {/* Recalibration from data */}
      <div className="border-t border-gray-800 pt-5">
        <h3 className="text-sm font-medium text-gray-300 mb-3">Re-calibrar desde datos históricos</h3>
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label className="text-xs text-gray-500">Desde</label>
            <input
              type="date"
              className="block mt-1 bg-gray-800 text-gray-200 text-sm rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-amber-500"
              value={windowStart}
              onChange={(e) => setWindowStart(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">Hasta</label>
            <input
              type="date"
              className="block mt-1 bg-gray-800 text-gray-200 text-sm rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-amber-500"
              value={windowEnd}
              onChange={(e) => setWindowEnd(e.target.value)}
            />
          </div>
          <button
            className="px-4 py-2 bg-blue-700 hover:bg-blue-600 text-white font-medium text-sm rounded transition-colors disabled:opacity-50"
            disabled={loading}
            onClick={handleRecalibrate}
          >
            {loading ? "Calculando…" : "Re-calibrar con OLS"}
          </button>
        </div>

        {proposed && (
          <div className="mt-4 bg-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm font-medium text-gray-200">Betas propuestos</p>
                <p className="text-xs text-gray-500">
                  R²={proposed.r_squared} · RMSE={proposed.rmse} · {proposed.observations} obs
                </p>
              </div>
              <button
                className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white font-medium text-sm rounded transition-colors disabled:opacity-50"
                disabled={loading}
                onClick={() =>
                  handleSaveAndActivate(
                    proposed.proposed_params,
                    `ols_${windowStart}_${windowEnd}`
                  )
                }
              >
                Activar propuestos
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(proposed.proposed_params).map(([key, val]) => (
                <div key={key} className="bg-gray-700 rounded p-2">
                  <p className="text-xs text-gray-400">{BETA_LABELS[key] || key}</p>
                  <p className="font-mono text-sm text-amber-300">{val.toFixed(4)}</p>
                  {proposed.pvalues?.[key] != null && (
                    <p className="text-xs text-gray-500">
                      p={proposed.pvalues[key].toFixed(3)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>

    </div>
  );
}
