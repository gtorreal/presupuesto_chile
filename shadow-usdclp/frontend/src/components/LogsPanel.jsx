import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";

const PAGE_SIZE = 50;

const ACTION_LABELS = {
  login: "Inicio de sesión",
  login_failed: "Login fallido",
  login_failed_otp: "OTP fallido",
  password_change: "Cambio de contraseña",
  otp_setup: "Configuración OTP",
  otp_enable: "OTP activado",
  otp_disable: "OTP desactivado",
  user_create: "Usuario creado",
  user_delete: "Usuario eliminado",
  model_activate: "Modelo activado",
  model_save: "Modelo guardado",
  config_change: "Config modificada",
  code_commit: "Commit",
};

const ACTION_COLORS = {
  login: "text-emerald-400 bg-emerald-950 border-emerald-900",
  login_failed: "text-red-400 bg-red-950 border-red-900",
  login_failed_otp: "text-red-400 bg-red-950 border-red-900",
  password_change: "text-amber-400 bg-amber-950 border-amber-900",
  otp_setup: "text-blue-400 bg-blue-950 border-blue-900",
  otp_enable: "text-blue-400 bg-blue-950 border-blue-900",
  otp_disable: "text-blue-400 bg-blue-950 border-blue-900",
  user_create: "text-violet-400 bg-violet-950 border-violet-900",
  user_delete: "text-red-400 bg-red-950 border-red-900",
  model_activate: "text-cyan-400 bg-cyan-950 border-cyan-900",
  model_save: "text-cyan-400 bg-cyan-950 border-cyan-900",
  config_change: "text-amber-400 bg-amber-950 border-amber-900",
  code_commit: "text-gray-300 bg-gray-800 border-gray-700",
};

function relativeTime(isoString) {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diff = now - then;

  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "hace un momento";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `hace ${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `hace ${days}d`;
  return new Date(isoString).toLocaleDateString("es-CL");
}

function formatDetail(action, detail) {
  if (!detail) return null;
  switch (action) {
    case "user_create":
      return `→ ${detail.target} (${detail.role})`;
    case "user_delete":
      return `→ ${detail.target}`;
    case "model_activate":
      return `ID #${detail.param_id}`;
    case "model_save":
      return `"${detail.name}" → ID #${detail.param_id}`;
    case "config_change":
      return `${detail.key} = ${detail.value}s`;
    case "code_commit": {
      const stats = detail.insertions != null
        ? ` +${detail.insertions} −${detail.deletions}`
        : "";
      const coAuth = detail.co_author ? ` [${detail.co_author.split("<")[0].trim()}]` : "";
      return `${detail.commit} — ${detail.message} (${detail.files_changed} archivos${stats})${coAuth}`;
    }
    default:
      return JSON.stringify(detail);
  }
}

export default function LogsPanel() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [filterAction, setFilterAction] = useState("");
  const [filterUsername, setFilterUsername] = useState("");

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAuditLogs({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        action: filterAction || undefined,
        username: filterUsername || undefined,
      });
      setLogs(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, filterAction, filterUsername]);

  useEffect(() => {
    load();
  }, [load]);

  function handleFilterChange(setter) {
    return (e) => {
      setter(e.target.value);
      setPage(0);
    };
  }

  const actionOptions = Object.entries(ACTION_LABELS);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]">
            <label className="block text-xs text-gray-500 mb-1">Acción</label>
            <select
              value={filterAction}
              onChange={handleFilterChange(setFilterAction)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-amber-500 transition-colors"
            >
              <option value="">Todas</option>
              {actionOptions.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[160px]">
            <label className="block text-xs text-gray-500 mb-1">Usuario</label>
            <input
              type="text"
              value={filterUsername}
              onChange={handleFilterChange(setFilterUsername)}
              placeholder="Filtrar por usuario..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors"
            />
          </div>
          <div className="text-xs text-gray-500 py-2">
            {total} {total === 1 ? "registro" : "registros"}
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs rounded-lg px-3 py-2 bg-red-950 border border-red-900 text-red-400">
          {error}
        </p>
      )}

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? (
          <p className="text-xs text-gray-500 py-8 text-center">Cargando...</p>
        ) : logs.length === 0 ? (
          <p className="text-xs text-gray-600 py-8 text-center">No hay registros.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  {["Fecha", "Usuario", "Acción", "Detalle", "IP"].map((h) => (
                    <th
                      key={h}
                      className="text-left text-xs text-gray-500 font-medium px-4 py-3"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className="border-b border-gray-800/50 last:border-0 hover:bg-gray-800/30 transition-colors"
                  >
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <span
                        className="text-xs text-gray-400"
                        title={new Date(log.ts).toLocaleString("es-CL")}
                      >
                        {relativeTime(log.ts)}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-200 font-medium">
                      {log.username || "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`text-xs font-medium px-2 py-0.5 rounded-full border ${
                          ACTION_COLORS[log.action] ||
                          "text-gray-400 bg-gray-800 border-gray-700"
                        }`}
                      >
                        {ACTION_LABELS[log.action] || log.action}
                      </span>
                    </td>
                    <td
                      className="px-4 py-2.5 text-xs text-gray-400 max-w-xs truncate"
                      title={formatDetail(log.action, log.detail) || ""}
                    >
                      {formatDetail(log.action, log.detail)}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-600 font-mono">
                      {log.ip || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="text-xs text-gray-400 hover:text-gray-200 disabled:text-gray-700 disabled:cursor-not-allowed transition-colors"
            >
              ← Anterior
            </button>
            <span className="text-xs text-gray-500">
              Página {page + 1} de {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="text-xs text-gray-400 hover:text-gray-200 disabled:text-gray-700 disabled:cursor-not-allowed transition-colors"
            >
              Siguiente →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
