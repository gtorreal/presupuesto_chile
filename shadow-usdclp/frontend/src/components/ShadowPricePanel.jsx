import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Clock, AlertCircle, CheckCircle } from "lucide-react";
import { api } from "../api/client";

function Badge({ ok, label }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
        ok ? "bg-emerald-900 text-emerald-300" : "bg-red-900 text-red-300"
      }`}
    >
      {ok ? <CheckCircle size={11} /> : <AlertCircle size={11} />}
      {label}
    </span>
  );
}

export default function ShadowPricePanel() {
  const [data, setData] = useState(null);
  const [sources, setSources] = useState([]);
  const [error, setError] = useState(null);

  const load = async () => {
    try {
      const [price, srcs] = await Promise.all([
        api.getShadowPrice(),
        api.getSourcesStatus(),
      ]);
      setData(price);
      setSources(srcs);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, []);

  if (error) {
    return (
      <div className="bg-red-950 border border-red-800 rounded-xl p-6 text-red-300">
        <AlertCircle className="inline mr-2" size={16} />
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-gray-900 rounded-xl p-6 animate-pulse h-48" />
    );
  }

  const delta = data.shadow_usdclp - data.bec_last_close;
  const deltaPct = (delta / data.bec_last_close) * 100;
  const isUp = delta >= 0;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Main shadow price card */}
      <div className="lg:col-span-2 bg-gray-900 rounded-xl p-6 border border-gray-800">
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-sm text-gray-400 font-medium tracking-widest uppercase">
              Shadow USDCLP
            </p>
            <div className="flex items-baseline gap-3 mt-1">
              <span className="text-5xl font-bold tracking-tight">
                {data.shadow_usdclp.toFixed(2)}
              </span>
              <span
                className={`flex items-center gap-1 text-lg font-semibold ${
                  isUp ? "text-red-400" : "text-emerald-400"
                }`}
              >
                {isUp ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                {isUp ? "+" : ""}
                {delta.toFixed(2)} ({isUp ? "+" : ""}
                {deltaPct.toFixed(2)}%)
              </span>
            </div>
          </div>
          <div className="text-right text-xs text-gray-500">
            <p>Actualizado</p>
            <p className="text-gray-400">{new Date(data.timestamp).toLocaleTimeString("es-CL")}</p>
          </div>
        </div>

        {/* Confidence band */}
        <div className="bg-gray-800 rounded-lg p-3 flex items-center justify-between text-sm">
          <div>
            <span className="text-gray-400">Banda confianza</span>
            <span className="ml-2 text-amber-300 font-mono">
              {data.confidence_low.toFixed(2)} – {data.confidence_high.toFixed(2)}
            </span>
          </div>
          <span className="text-gray-500 text-xs">
            ±{((data.confidence_high - data.confidence_low) / 2).toFixed(2)}
          </span>
        </div>
      </div>

      {/* BEC close & age */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 flex flex-col justify-between">
        <div>
          <p className="text-sm text-gray-400 font-medium tracking-widest uppercase mb-1">
            Último cierre BEC
          </p>
          <p className="text-3xl font-bold">{data.bec_last_close?.toFixed(2) ?? "—"}</p>
        </div>
        <div className="mt-4 flex items-center gap-2 text-sm text-gray-400">
          <Clock size={14} />
          <span>
            {data.bec_close_age_hours != null
              ? (() => {
                  const h = Math.floor(data.bec_close_age_hours);
                  const m = Math.round((data.bec_close_age_hours - h) * 60);
                  return `Hace ${h}h ${m.toString().padStart(2, "0")}min`;
                })()
              : "—"}
          </span>
        </div>
        <div className="mt-4">
          <p className="text-xs text-gray-500 mb-1">Modelo: {data.model_version}</p>
        </div>
      </div>

      {/* Sources status */}
      <div className="lg:col-span-3 bg-gray-900 rounded-xl p-4 border border-gray-800">
        <p className="text-xs text-gray-400 uppercase tracking-widest mb-3">Estado de fuentes</p>
        <div className="flex flex-wrap gap-2">
          {sources.map((s) => (
            <Badge key={s.source} ok={s.is_live} label={`${s.source} (${s.minutes_ago}m)`} />
          ))}
          {sources.length === 0 && (
            <span className="text-gray-600 text-sm">Sin datos aún…</span>
          )}
        </div>
      </div>
    </div>
  );
}
