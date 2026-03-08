import { useState, useEffect, useCallback } from "react";
import { QRCodeSVG } from "qrcode.react";

const API = (path) => `/api/v1/users${path}`;

function authHeaders() {
  const token = localStorage.getItem("shadow_token");
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(API(path), { headers: authHeaders(), ...opts });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// OTP Section
// ---------------------------------------------------------------------------

function OtpSection({ currentUser }) {
  const [otpEnabled, setOtpEnabled] = useState(currentUser.otp_enabled);
  const [setupData, setSetupData] = useState(null); // { secret, uri }
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState(null); // { type: "ok"|"err", text }
  const [loading, setLoading] = useState(false);

  async function startSetup() {
    setMsg(null);
    setLoading(true);
    try {
      const data = await apiFetch("/me/otp-setup", { method: "POST" });
      setSetupData(data);
      setCode("");
    } catch (e) {
      setMsg({ type: "err", text: e.message });
    } finally {
      setLoading(false);
    }
  }

  async function confirmEnable() {
    if (code.length !== 6) return;
    setLoading(true);
    setMsg(null);
    try {
      await apiFetch("/me/otp-enable", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setOtpEnabled(true);
      setSetupData(null);
      setCode("");
      setMsg({ type: "ok", text: "OTP activado correctamente." });
    } catch (e) {
      setMsg({ type: "err", text: e.message });
    } finally {
      setLoading(false);
    }
  }

  async function confirmDisable() {
    if (code.length !== 6) return;
    setLoading(true);
    setMsg(null);
    try {
      await apiFetch("/me/otp-disable", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setOtpEnabled(false);
      setCode("");
      setMsg({ type: "ok", text: "OTP desactivado." });
    } catch (e) {
      setMsg({ type: "err", text: e.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-200">Autenticación de dos factores (OTP)</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Usa Google Authenticator, Authy u otra app TOTP compatible.
          </p>
        </div>
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            otpEnabled
              ? "bg-emerald-950 text-emerald-400 border border-emerald-900"
              : "bg-gray-800 text-gray-500 border border-gray-700"
          }`}
        >
          {otpEnabled ? "Activo" : "Inactivo"}
        </span>
      </div>

      {msg && (
        <p
          className={`text-xs rounded-lg px-3 py-2 mb-4 ${
            msg.type === "ok"
              ? "bg-emerald-950 border border-emerald-900 text-emerald-400"
              : "bg-red-950 border border-red-900 text-red-400"
          }`}
        >
          {msg.text}
        </p>
      )}

      {/* Setup flow */}
      {!otpEnabled && !setupData && (
        <button
          onClick={startSetup}
          disabled={loading}
          className="text-sm bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-900 font-semibold px-4 py-2 rounded-lg transition-colors"
        >
          {loading ? "Generando..." : "Activar OTP"}
        </button>
      )}

      {!otpEnabled && setupData && (
        <div className="space-y-4">
          <p className="text-xs text-gray-400">
            Escanea este código QR con tu app autenticadora, luego ingresa el código de 6 dígitos para confirmar.
          </p>
          <div className="flex justify-center">
            <div className="bg-white p-3 rounded-lg inline-block">
              <QRCodeSVG value={setupData.uri} size={180} />
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">O ingresa la clave manualmente:</p>
            <code className="text-xs text-amber-400 bg-gray-800 px-3 py-1.5 rounded block break-all">
              {setupData.secret}
            </code>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              placeholder="Código de 6 dígitos"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors tracking-widest text-center"
            />
            <button
              onClick={confirmEnable}
              disabled={loading || code.length !== 6}
              className="bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-900 font-semibold text-sm px-4 py-2 rounded-lg transition-colors"
            >
              {loading ? "..." : "Confirmar"}
            </button>
            <button
              onClick={() => { setSetupData(null); setCode(""); setMsg(null); }}
              className="text-sm text-gray-500 hover:text-gray-300 px-3 py-2 rounded-lg transition-colors"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Disable flow */}
      {otpEnabled && (
        <div className="space-y-3">
          <p className="text-xs text-gray-400">
            Para desactivar OTP, ingresa un código válido de tu app autenticadora.
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              placeholder="Código de 6 dígitos"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors tracking-widest text-center"
            />
            <button
              onClick={confirmDisable}
              disabled={loading || code.length !== 6}
              className="bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white font-semibold text-sm px-4 py-2 rounded-lg transition-colors"
            >
              {loading ? "..." : "Desactivar"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Change Password Section
// ---------------------------------------------------------------------------

function ChangePasswordSection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (next !== confirm) {
      setMsg({ type: "err", text: "Las contraseñas nuevas no coinciden." });
      return;
    }
    setLoading(true);
    setMsg(null);
    try {
      await apiFetch("/me/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      setMsg({ type: "ok", text: "Contraseña actualizada." });
      setCurrent(""); setNext(""); setConfirm("");
    } catch (e) {
      setMsg({ type: "err", text: e.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-gray-200 mb-4">Cambiar contraseña</h3>
      <form onSubmit={handleSubmit} className="space-y-3">
        {[
          { label: "Contraseña actual", value: current, set: setCurrent, auto: "current-password" },
          { label: "Nueva contraseña", value: next, set: setNext, auto: "new-password" },
          { label: "Confirmar nueva contraseña", value: confirm, set: setConfirm, auto: "new-password" },
        ].map(({ label, value, set, auto }) => (
          <div key={label}>
            <label className="block text-xs text-gray-500 mb-1">{label}</label>
            <input
              type="password"
              value={value}
              onChange={(e) => set(e.target.value)}
              autoComplete={auto}
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors"
            />
          </div>
        ))}
        {msg && (
          <p className={`text-xs rounded-lg px-3 py-2 ${msg.type === "ok" ? "bg-emerald-950 border border-emerald-900 text-emerald-400" : "bg-red-950 border border-red-900 text-red-400"}`}>
            {msg.text}
          </p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-900 font-semibold text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {loading ? "Guardando..." : "Actualizar contraseña"}
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// User Management Section (admin only)
// ---------------------------------------------------------------------------

function UserManagementSection() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch("");
      setUsers(data);
    } catch (e) {
      setMsg({ type: "err", text: e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createUser(e) {
    e.preventDefault();
    setCreating(true);
    setMsg(null);
    try {
      await apiFetch("", {
        method: "POST",
        body: JSON.stringify({ username: newUsername, password: newPassword, role: "admin" }),
      });
      setNewUsername(""); setNewPassword(""); setShowForm(false);
      setMsg({ type: "ok", text: `Usuario "${newUsername}" creado.` });
      await load();
    } catch (e) {
      setMsg({ type: "err", text: e.message });
    } finally {
      setCreating(false);
    }
  }

  async function deleteUser(username) {
    if (!window.confirm(`¿Eliminar al usuario "${username}"?`)) return;
    setMsg(null);
    try {
      await apiFetch(`/${username}`, { method: "DELETE" });
      setMsg({ type: "ok", text: `Usuario "${username}" eliminado.` });
      await load();
    } catch (e) {
      setMsg({ type: "err", text: e.message });
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-200">Usuarios</h3>
        <button
          onClick={() => { setShowForm((v) => !v); setMsg(null); }}
          className="text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 px-3 py-1.5 rounded-lg transition-colors"
        >
          {showForm ? "Cancelar" : "+ Agregar usuario"}
        </button>
      </div>

      {msg && (
        <p className={`text-xs rounded-lg px-3 py-2 mb-3 ${msg.type === "ok" ? "bg-emerald-950 border border-emerald-900 text-emerald-400" : "bg-red-950 border border-red-900 text-red-400"}`}>
          {msg.text}
        </p>
      )}

      {showForm && (
        <form onSubmit={createUser} className="mb-4 p-4 bg-gray-800 rounded-lg space-y-3 border border-gray-700">
          <h4 className="text-xs font-semibold text-gray-400">Nuevo usuario</h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Usuario</label>
              <input
                type="text"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                required
                minLength={2}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-amber-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Contraseña</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-amber-500 transition-colors"
              />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Rol: <span className="text-gray-300">Admin</span></span>
            <button
              type="submit"
              disabled={creating}
              className="text-sm bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-900 font-semibold px-4 py-1.5 rounded-lg transition-colors"
            >
              {creating ? "Creando..." : "Crear"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-xs text-gray-500 py-4 text-center">Cargando...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                {["Usuario", "Rol", "OTP", "Creado", ""].map((h) => (
                  <th key={h} className="text-left text-xs text-gray-500 font-medium pb-2 pr-4 last:pr-0">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username} className="border-b border-gray-800/50 last:border-0">
                  <td className="py-2.5 pr-4 text-gray-200 font-medium">{u.username}</td>
                  <td className="py-2.5 pr-4">
                    <span className="text-xs bg-amber-950 text-amber-400 border border-amber-900 px-2 py-0.5 rounded-full">
                      {u.role}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={`text-xs ${u.otp_enabled ? "text-emerald-400" : "text-gray-600"}`}>
                      {u.otp_enabled ? "Activo" : "—"}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-gray-500">
                    {new Date(u.created_at).toLocaleDateString("es-CL")}
                  </td>
                  <td className="py-2.5 text-right">
                    <button
                      onClick={() => deleteUser(u.username)}
                      className="text-xs text-gray-600 hover:text-red-400 transition-colors"
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && (
            <p className="text-xs text-gray-600 py-4 text-center">No hay usuarios.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Settings Panel
// ---------------------------------------------------------------------------

export default function SettingsPanel({ currentUser }) {
  return (
    <div className="space-y-8">
      {/* Mi cuenta */}
      <section>
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Mi cuenta</h2>
        <div className="space-y-4">
          <OtpSection currentUser={currentUser} />
          <ChangePasswordSection />
        </div>
      </section>

      {/* Cuentas y permisos — admin only */}
      {currentUser.role === "admin" && (
        <section>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Cuentas y permisos
          </h2>
          <UserManagementSection />
        </section>
      )}
    </div>
  );
}
