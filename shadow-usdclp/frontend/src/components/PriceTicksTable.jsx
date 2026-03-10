import { useEffect, useState, useCallback } from "react";
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy, arrayMove, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { api } from "../api/client";

const COLUMNS = [
  { key: "shadow_price", label: "Shadow USDCLP", group: "index", color: "#f59e0b" },
  { key: "usdclp_buda",  label: "USDC Buda",     group: "spot" },
  { key: "usdclp_usdt",  label: "USDT Buda",     group: "spot" },
  { key: "usdclp_spot",  label: "USDCLP Spot",     group: "spot" },
  { key: "usdclp_ndf",   label: "NDF 1M",         group: "spot" },
  { key: "usdbrl",       label: "USDBRL",         group: "forex" },
  { key: "usdmxn",       label: "USDMXN",         group: "forex" },
  { key: "usdcop",       label: "USDCOP",         group: "forex" },
  { key: "dxy",          label: "DXY (YF)",       group: "macro" },
  { key: "dxy_proxy",    label: "DXY (ECB)",      group: "macro" },
  { key: "copper",       label: "Cobre",          group: "macro" },
  { key: "vix",          label: "VIX",            group: "macro" },
  { key: "us10y",        label: "US10Y",          group: "macro" },
  { key: "ech",          label: "ECH",            group: "macro" },
];

const GROUPS = [
  { id: "index", label: "Índice" },
  { id: "spot",  label: "Spot CLP" },
  { id: "forex", label: "Forex" },
  { id: "macro", label: "Macro" },
];

const COL_ORDER_KEY = "priceticks-col-order";
const DEFAULT_ORDER = COLUMNS.map((c) => c.key);

function SortableColumnHeader({ col }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: col.key });

  const style = {
    color: col.color || "#6b7280",
    transform: CSS.Translate.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
    cursor: "grab",
  };

  return (
    <th
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className="pb-2 pr-4 font-medium whitespace-nowrap select-none"
      style={style}
    >
      {col.label}
    </th>
  );
}

function formatNum(v, decimals = 2) {
  if (v == null) return "—";
  return v.toLocaleString("es-CL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

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

export default function PriceTicksTable({ hours }) {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [visibleCols, setVisibleCols] = useState(() => {
    const state = {};
    COLUMNS.forEach((c) => (state[c.key] = true));
    return state;
  });

  const [columnOrder, setColumnOrder] = useState(() => {
    const currentKeys = new Set(DEFAULT_ORDER);
    try {
      const saved = JSON.parse(localStorage.getItem(COL_ORDER_KEY) || "[]");
      const validSaved = saved.filter((k) => currentKeys.has(k));
      const newKeys = DEFAULT_ORDER.filter((k) => !new Set(validSaved).has(k));
      if (validSaved.length > 0) return [...validSaved, ...newKeys];
    } catch (_) {}
    return DEFAULT_ORDER;
  });

  useEffect(() => {
    localStorage.setItem(COL_ORDER_KEY, JSON.stringify(columnOrder));
  }, [columnOrder]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  function handleDragEnd(event) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setColumnOrder((prev) => {
      const oldIndex = prev.indexOf(active.id);
      const newIndex = prev.indexOf(over.id);
      return arrayMove(prev, oldIndex, newIndex);
    });
  }

  const load = useCallback(async () => {
    try {
      const result = await api.getPriceTicksTable(hours, page);
      setData(result);
    } catch (_) {}
  }, [hours, page]);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  // Reset page when hours change
  useEffect(() => setPage(1), [hours]);

  function toggleCol(key) {
    setVisibleCols((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function toggleGroup(groupId) {
    const keys = COLUMNS.filter((c) => c.group === groupId).map((c) => c.key);
    const allOn = keys.every((k) => visibleCols[k]);
    setVisibleCols((prev) => {
      const next = { ...prev };
      keys.forEach((k) => (next[k] = !allOn));
      return next;
    });
  }

  const activeCols = columnOrder
    .map((key) => COLUMNS.find((c) => c.key === key))
    .filter((c) => c && visibleCols[c.key]);

  if (!data) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <div className="h-24 flex items-center justify-center text-gray-600 text-sm">
          Cargando precios...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-gray-200">Precios por activo</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Fuente: price_ticks · Bucket: {data.bucket_interval} · {data.total_rows} registros
          </p>
        </div>
      </div>

      {/* Filtros de columnas por grupo */}
      <div className="mb-4 space-y-2">
        {GROUPS.map((g) => {
          const cols = COLUMNS.filter((c) => c.group === g.id);
          return (
            <div key={g.id} className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <button
                onClick={() => toggleGroup(g.id)}
                className="text-xs text-gray-500 hover:text-gray-300 underline underline-offset-2 mr-1 min-w-[60px]"
              >
                {g.label}
              </button>
              {cols.map((c) => (
                <label key={c.key} className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={visibleCols[c.key]}
                    onChange={() => toggleCol(c.key)}
                    className="sr-only"
                  />
                  <span
                    className="w-3 h-3 rounded-sm flex-shrink-0 border"
                    style={{
                      backgroundColor: visibleCols[c.key]
                        ? (c.color || "#6b7280")
                        : "transparent",
                      borderColor: c.color || "#6b7280",
                    }}
                  />
                  <span className="text-xs text-gray-400">{c.label}</span>
                </label>
              ))}
            </div>
          );
        })}
      </div>

      {/* Tabla */}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="pb-2 pr-4 text-gray-500 font-medium whitespace-nowrap sticky left-0 bg-gray-900 z-10">
                Hora
              </th>
              <SortableContext items={activeCols.map((c) => c.key)} strategy={horizontalListSortingStrategy}>
                {activeCols.map((c) => (
                  <SortableColumnHeader key={c.key} col={c} />
                ))}
              </SortableContext>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r, i) => (
              <tr
                key={r.time}
                className={`border-b border-gray-800/50 ${i % 2 === 0 ? "" : "bg-gray-800/20"}`}
              >
                <td className="py-1.5 pr-4 text-gray-400 whitespace-nowrap font-mono sticky left-0 bg-gray-900 z-10">
                  {formatTime(r.time, hours)}
                </td>
                {activeCols.map((c) => {
                  const v = r[c.key];
                  const isIndex = c.key === "shadow_price";
                  const decimals = c.group === "forex" || c.group === "macro" ? 4 : 2;
                  return (
                    <td
                      key={c.key}
                      className={`py-1.5 pr-4 font-mono whitespace-nowrap ${
                        v == null
                          ? "text-gray-700"
                          : isIndex
                          ? "text-amber-400"
                          : "text-gray-300"
                      }`}
                    >
                      {formatNum(v, decimals)}
                    </td>
                  );
                })}
              </tr>
            ))}
            {data.rows.length === 0 && (
              <tr>
                <td
                  colSpan={activeCols.length + 1}
                  className="py-8 text-center text-gray-600"
                >
                  Sin datos para este período
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      </DndContext>

      {/* Paginación */}
      {data.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-gray-600">
            Página {data.page} de {data.total_pages}
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 rounded text-xs bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30"
            >
              ← Anterior
            </button>
            <button
              onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
              disabled={page === data.total_pages}
              className="px-3 py-1 rounded text-xs bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30"
            >
              Siguiente →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
