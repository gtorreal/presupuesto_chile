import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "../api/client";

const HOUR_OPTIONS = [
  { label: "6h", value: 6 },
  { label: "24h", value: 24 },
  { label: "48h", value: 48 },
  { label: "7d", value: 168 },
];

function formatTime(isoStr) {
  const d = new Date(isoStr);
  return d.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
}

export default function HistoricalChart() {
  const [hours, setHours] = useState(24);
  const [chartData, setChartData] = useState([]);

  const load = async () => {
    try {
      const history = await api.getShadowHistory(hours);
      setChartData(
        history.map((r) => ({
          time: formatTime(r.time),
          shadow: r.shadow_price,
          low: r.confidence_low,
          high: r.confidence_high,
          bec: r.bec_last_close,
        }))
      );
    } catch (_) {}
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [hours]);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-gray-200">Histórico Shadow USDCLP</h2>
          <p className="text-xs text-gray-500 mt-0.5">Shadow vs último cierre BEC</p>
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

      {chartData.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
          Sin datos históricos aún
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" tick={{ fill: "#6b7280", fontSize: 11 }} />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: "#6b7280", fontSize: 11 }}
              tickFormatter={(v) => v.toFixed(0)}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151" }}
              labelStyle={{ color: "#9ca3af" }}
              itemStyle={{ color: "#e5e7eb" }}
              formatter={(value) => value?.toFixed(2)}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />

            {/* Confidence band — upper */}
            <Line
              type="monotone"
              dataKey="high"
              stroke="#d97706"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              name="Banda alta"
            />
            {/* Shadow price */}
            <Line
              type="monotone"
              dataKey="shadow"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
              name="Shadow USDCLP"
            />
            {/* Confidence band — lower */}
            <Line
              type="monotone"
              dataKey="low"
              stroke="#d97706"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              name="Banda baja"
            />
            {/* BEC close reference */}
            <Line
              type="monotone"
              dataKey="bec"
              stroke="#6b7280"
              strokeWidth={1}
              strokeDasharray="8 4"
              dot={false}
              name="Cierre BEC"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
