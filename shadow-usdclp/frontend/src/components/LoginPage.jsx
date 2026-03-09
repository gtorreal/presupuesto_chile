import { useState } from "react";
import BudaLogo from "./BudaLogo";

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [step, setStep] = useState("credentials"); // "credentials" | "otp"
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleCredentials(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        setError("Usuario o contraseña incorrectos");
        return;
      }
      const data = await res.json();
      if (data.requires_otp) {
        setStep("otp");
      } else {
        localStorage.setItem("shadow_token", data.access_token);
        onLogin(data.access_token);
      }
    } catch {
      setError("No se pudo conectar con el servidor");
    } finally {
      setLoading(false);
    }
  }

  async function handleOtp(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, otp_code: otpCode }),
      });
      if (!res.ok) {
        setError("Código incorrecto. Intenta de nuevo.");
        setOtpCode("");
        return;
      }
      const data = await res.json();
      localStorage.setItem("shadow_token", data.access_token);
      onLogin(data.access_token);
    } catch {
      setError("No se pudo conectar con el servidor");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="mb-4">
            <BudaLogo size={48} />
          </div>
          <h1 className="text-xl font-bold text-gray-100">Shadow USDCLP</h1>
          <p className="text-sm text-gray-500 mt-1">Buda.com — Índice sintético</p>
        </div>

        {/* Card */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          {step === "credentials" ? (
            <>
              <h2 className="text-sm font-semibold text-gray-300 mb-4">Iniciar sesión</h2>
              <form onSubmit={handleCredentials} className="space-y-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1.5">Usuario</label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                    required
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors"
                    placeholder="usuario"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1.5">Contraseña</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors"
                    placeholder="••••••••"
                  />
                </div>
                {error && (
                  <p className="text-xs text-red-400 bg-red-950 border border-red-900 rounded-lg px-3 py-2">
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-gray-900 font-semibold text-sm rounded-lg py-2.5 transition-colors"
                >
                  {loading ? "Verificando..." : "Continuar"}
                </button>
              </form>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-4">
                <button
                  onClick={() => { setStep("credentials"); setError(null); setOtpCode(""); }}
                  className="text-gray-500 hover:text-gray-300 transition-colors text-xs"
                >
                  ← Volver
                </button>
              </div>
              <h2 className="text-sm font-semibold text-gray-300 mb-1">Autenticación de dos factores</h2>
              <p className="text-xs text-gray-500 mb-4">
                Ingresa el código de 6 dígitos de tu app autenticadora.
              </p>
              <form onSubmit={handleOtp} className="space-y-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1.5">Código OTP</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                    autoFocus
                    required
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors tracking-widest text-center text-lg"
                    placeholder="000000"
                  />
                </div>
                {error && (
                  <p className="text-xs text-red-400 bg-red-950 border border-red-900 rounded-lg px-3 py-2">
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={loading || otpCode.length !== 6}
                  className="w-full bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-gray-900 font-semibold text-sm rounded-lg py-2.5 transition-colors"
                >
                  {loading ? "Verificando..." : "Ingresar"}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
