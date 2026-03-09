import { useEffect, useState, useMemo } from "react";
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "../api/client";
import PriceTicksTable from "./PriceTicksTable";

const HOUR_OPTIONS = [
  { label: "6h", value: 6 },
  { label: "24h", value: 24 },
  { label: "48h", value: 48 },
  { label: "7d", value: 168 },
];

// Precio series (eje izquierdo, CLP)
const PRICE_SERIES = [
  { key: "shadow", label: "Shadow USDCLP", color: "#f59e0b", width: 2, dash: undefined },
  { key: "high",   label: "Banda alta",    color: "#d97706", width: 1, dash: "4 4" },
  { key: "low",    label: "Banda baja",    color: "#d97706", width: 1, dash: "4 4" },
  { key: "bec",    label: "Cierre BEC",    color: "#6b7280", width: 1, dash: "8 4" },
];

// Factor Δ% series (eje derecho, %)
const DELTA_SERIES = [
  { key: "delta_ndf",     label: "NDF (Δ%)",     color: "#60a5fa" },
  { key: "delta_usdbrl",  label: "USDBRL (Δ%)",  color: "#34d399" },
  { key: "delta_dxy",     label: "DXY (Δ%)",     color: "#a78bfa" },
  { key: "delta_copper",  label: "Cobre (Δ%)",   color: "#f87171" },
  { key: "delta_usdmxn",  label: "USDMXN (Δ%)",  color: "#fb923c" },
  { key: "delta_vix",     label: "VIX (Δ%)",     color: "#e879f9" },
  { key: "delta_us10y",   label: "US10Y (Δ%)",   color: "#38bdf8" },
  { key: "delta_usdcop",  label: "USDCOP (Δ%)",  color: "#4ade80" },
  { key: "delta_ech",     label: "ECH (Δ%)",     color: "#fbbf24" },
];

const DELTA_KEY_MAP = {
  beta_ndf:        "delta_ndf",
  beta_usdbrl:     "delta_usdbrl",
  beta_dxy:        "delta_dxy",
  beta_copper_inv: "delta_copper",
  beta_usdmxn:     "delta_usdmxn",
  beta_vix:        "delta_vix",
  beta_us10y:      "delta_us10y",
  beta_usdcop:     "delta_usdcop",
  beta_ech:        "delta_ech",
};

function formatTime(isoStr, hours) {
  const d = new Date(isoStr);
  if (hours <= 24) {
    return d.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleString("es-CL", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function pct(v) {
  if (v == null) return "—";
  return (v * 100).toFixed(3) + "%";
}

function clp(v) {
  if (v == null) return "—";
  return v.toFixed(2);
}

// Default: todos los precios ON, todos los factores OFF
const defaultVisible = () => {
  const state = {};
  PRICE_SERIES.forEach((s) => (state[s.key] = true));
  DELTA_SERIES.forEach((s) => (state[s.key] = false));
  return state;
};

export default function HistoricalChart() {
  const [hours, setHours] = useState(24);
  const [rawData, setRawData] = useState([]);
  const [visible, setVisible] = useState(defaultVisible());
  const [tablePage, setTablePage] = useState(0);
  const TABLE_PAGE_SIZE = 50;

  const load = async () => {
    try {
      const history = await api.getShadowHistory(hours);
      setRawData(history);
    } catch (_) {}
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [hours]);

  // Cambiar período resetea página de tabla
  useEffect(() => setTablePage(0), [hours]);

  const chartData = useMemo(
    () =>
      rawData.map((r) => {
        const deltas = r.factor_deltas || {};
        const point = {
          time:   formatTime(r.time, hours),
          shadow: r.shadow_price,
          low:    r.confidence_low,
          high:   r.confidence_high,
          bandWidth: (r.confidence_high != null && r.confidence_low != null)
            ? r.confidence_high - r.confidence_low : null,
          bec:    r.bec_last_close,
        };
        for (const [betaKey, chartKey] of Object.entries(DELTA_KEY_MAP)) {
          point[chartKey] = deltas[betaKey] != null ? deltas[betaKey] : null;
        }
        return point;
      }),
    [rawData, hours]
  );

  // Dominio del eje Y calculado desde los datos reales (evita que stacked areas lo distorsionen)
  const priceDomain = useMemo(() => {
    const prices = chartData.flatMap((d) =>
      [d.shadow, d.low, d.high, d.bec].filter((v) => v != null)
    );
    if (!prices.length) return [undefined, undefined];
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const pad = Math.max(1, (max - min) * 0.1);
    return [Math.floor(min - pad), Math.ceil(max + pad)];
  }, [chartData]);

  const hasDeltaSeries = DELTA_SERIES.some((s) => visible[s.key]);

  function toggle(key) {
    setVisible((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function toggleGroup(series) {
    const keys = series.map((s) => s.key);
    const allOn = keys.every((k) => visible[k]);
    setVisible((prev) => {
      const next = { ...prev };
      keys.forEach((k) => (next[k] = !allOn));
      return next;
    });
  }

  // Tabla: invertida (más reciente primero) y paginada
  const tableRows = useMemo(() => [...rawData].reverse(), [rawData]);
  const totalPages = Math.ceil(tableRows.length / TABLE_PAGE_SIZE);
  const pageRows = tableRows.slice(
    tablePage * TABLE_PAGE_SIZE,
    (tablePage + 1) * TABLE_PAGE_SIZE
  );

  return (
    <div className="space-y-4">
      {/* Gráfico */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-semibold text-gray-200">Histórico Shadow USDCLP</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {hasDeltaSeries ? "Precios (izq.) · Deltas % (der.)" : "Shadow vs cierre BEC"}
            </p>
          </div>
          <div className="flex gap-1">
            {HOUR_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setHours(opt.value)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  hours === opt.value
                    ? "bg-amber-500 text-gray-900"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Filtros */}
        <div className="mb-4 space-y-2">
          {/* Grupo precios */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <button
              onClick={() => toggleGroup(PRICE_SERIES)}
              className="text-xs text-gray-500 hover:text-gray-300 underline underline-offset-2 mr-1"
            >
              Precios
            </button>
            {PRICE_SERIES.map((s) => (
              <label key={s.key} className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={visible[s.key]}
                  onChange={() => toggle(s.key)}
                  className="sr-only"
                />
                <span
                  className="w-3 h-3 rounded-sm flex-shrink-0 border"
                  style={{
                    backgroundColor: visible[s.key] ? s.color : "transparent",
                    borderColor: s.color,
                  }}
                />
                <span className="text-xs text-gray-400">{s.label}</span>
              </label>
            ))}
          </div>
          {/* Grupo factores */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <button
              onClick={() => toggleGroup(DELTA_SERIES)}
              className="text-xs text-gray-500 hover:text-gray-300 underline underline-offset-2 mr-1"
            >
              Factores
            </button>
            {DELTA_SERIES.map((s) => (
              <label key={s.key} className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={visible[s.key]}
                  onChange={() => toggle(s.key)}
                  className="sr-only"
                />
                <span
                  className="w-3 h-3 rounded-sm flex-shrink-0 border"
                  style={{
                    backgroundColor: visible[s.key] ? s.color : "transparent",
                    borderColor: s.color,
                  }}
                />
                <span className="text-xs text-gray-400">{s.label}</span>
              </label>
            ))}
          </div>
        </div>

        {chartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
            Sin datos históricos aún
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={chartData} margin={{ top: 5, right: hasDeltaSeries ? 50 : 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" tick={{ fill: "#6b7280", fontSize: 11 }} />

              {/* Eje izquierdo: precios CLP */}
              <YAxis
                yAxisId="price"
                orientation="left"
                domain={priceDomain}
                allowDataOverflow
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickFormatter={(v) => v.toFixed(0)}
              />

              {/* Eje derecho: factor deltas % (solo si hay alguno visible) */}
              {hasDeltaSeries && (
                <YAxis
                  yAxisId="delta"
                  orientation="right"
                  domain={["auto", "auto"]}
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  tickFormatter={(v) => (v * 100).toFixed(2) + "%"}
                  width={60}
                />
              )}

              <Tooltip
                contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151" }}
                labelStyle={{ color: "#9ca3af" }}
                itemStyle={{ color: "#e5e7eb" }}
                formatter={(value, name) => {
                  const isDelta = DELTA_SERIES.some((s) => s.label === name);
                  return isDelta ? pct(value) : clp(value);
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />

              {/* Banda de confianza rellena (stacked: low invisible + bandWidth visible) */}
              {visible.high && visible.low && (
                <>
                  <Area
                    yAxisId="price"
                    stackId="confidence"
                    type="monotone"
                    dataKey="low"
                    stroke="none"
                    fill="transparent"
                    activeDot={false}
                    legendType="none"
                    tooltipType="none"
                    connectNulls
                    isAnimationActive={false}
                  />
                  <Area
                    yAxisId="price"
                    stackId="confidence"
                    type="monotone"
                    dataKey="bandWidth"
                    stroke="none"
                    fill="#f59e0b"
                    fillOpacity={0.25}
                    activeDot={false}
                    legendType="none"
                    tooltipType="none"
                    connectNulls
                    isAnimationActive={false}
                  />
                </>
              )}

              {/* Series de precio */}
              {PRICE_SERIES.filter((s) => visible[s.key]).map((s) => (
                <Line
                  key={s.key}
                  yAxisId="price"
                  type="monotone"
                  dataKey={s.key}
                  stroke={s.color}
                  strokeWidth={s.width}
                  strokeDasharray={s.dash}
                  dot={false}
                  name={s.label}
                  connectNulls
                />
              ))}

              {/* Series de delta */}
              {DELTA_SERIES.filter((s) => visible[s.key]).map((s) => (
                <Line
                  key={s.key}
                  yAxisId={hasDeltaSeries ? "delta" : "price"}
                  type="monotone"
                  dataKey={s.key}
                  stroke={s.color}
                  strokeWidth={1}
                  dot={false}
                  name={s.label}
                  connectNulls
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Tabla de precios por activo */}
      <PriceTicksTable hours={hours} />

      {/* Tabla de datos shadow */}
      {rawData.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-200">Datos históricos</h2>
            <span className="text-xs text-gray-500">{rawData.length} registros</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="pb-2 pr-4 text-gray-500 font-medium whitespace-nowrap">Hora</th>
                  <th className="pb-2 pr-4 text-gray-500 font-medium whitespace-nowrap">Shadow</th>
                  <th className="pb-2 pr-4 text-gray-500 font-medium whitespace-nowrap">Banda baja</th>
                  <th className="pb-2 pr-4 text-gray-500 font-medium whitespace-nowrap">Banda alta</th>
                  <th className="pb-2 pr-4 text-gray-500 font-medium whitespace-nowrap">Cierre BEC</th>
                  {DELTA_SERIES.map((s) => (
                    <th key={s.key} className="pb-2 pr-4 font-medium whitespace-nowrap" style={{ color: s.color }}>
                      {s.label.replace(" (Δ%)", "")}
                    </th>
                  ))}
                  <th className="pb-2 text-gray-500 font-medium whitespace-nowrap">Modelo</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((r, i) => {
                  const deltas = r.factor_deltas || {};
                  return (
                    <tr
                      key={r.time}
                      className={`border-b border-gray-800/50 ${i % 2 === 0 ? "" : "bg-gray-800/20"}`}
                    >
                      <td className="py-1.5 pr-4 text-gray-400 whitespace-nowrap font-mono">
                        {formatTime(r.time, hours)}
                      </td>
                      <td className="py-1.5 pr-4 text-amber-400 font-mono">{clp(r.shadow_price)}</td>
                      <td className="py-1.5 pr-4 text-gray-300 font-mono">{clp(r.confidence_low)}</td>
                      <td className="py-1.5 pr-4 text-gray-300 font-mono">{clp(r.confidence_high)}</td>
                      <td className="py-1.5 pr-4 text-gray-400 font-mono">{clp(r.bec_last_close)}</td>
                      {Object.entries(DELTA_KEY_MAP).map(([betaKey, _]) => {
                        const v = deltas[betaKey];
                        const isPos = v > 0;
                        return (
                          <td
                            key={betaKey}
                            className={`py-1.5 pr-4 font-mono ${
                              v == null ? "text-gray-700" : isPos ? "text-emerald-400" : "text-rose-400"
                            }`}
                          >
                            {pct(v)}
                          </td>
                        );
                      })}
                      <td className="py-1.5 text-gray-600 whitespace-nowrap">{r.model_version || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Paginación */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-gray-600">
                Página {tablePage + 1} de {totalPages}
              </span>
              <div className="flex gap-1">
                <button
                  onClick={() => setTablePage((p) => Math.max(0, p - 1))}
                  disabled={tablePage === 0}
                  className="px-3 py-1 rounded text-xs bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30"
                >
                  ← Anterior
                </button>
                <button
                  onClick={() => setTablePage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={tablePage === totalPages - 1}
                  className="px-3 py-1 rounded text-xs bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30"
                >
                  Siguiente →
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
