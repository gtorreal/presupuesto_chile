// Returns true if the given market schedule is currently open (UTC-based).
function isMarketOpen(schedule) {
  const now = new Date();
  const day = now.getUTCDay(); // 0=Sun, 1=Mon...5=Fri, 6=Sat
  const hhmm = now.getUTCHours() * 60 + now.getUTCMinutes();

  switch (schedule) {
    case "forex":
      // Open Sun 22:00 UTC – Fri 22:00 UTC
      if (day === 6) return false;
      if (day === 0 && hhmm < 22 * 60) return false;
      if (day === 5 && hhmm >= 22 * 60) return false;
      return true;
    case "us_equity":
      // NYSE/CBOE: Mon–Fri 13:30–20:00 UTC (EDT)
      if (day === 0 || day === 6) return false;
      return hhmm >= 13 * 60 + 30 && hhmm < 20 * 60;
    case "us_futures":
      // CME/ICE futures: Sun 22:00 – Fri 21:00 UTC
      if (day === 6) return false;
      if (day === 0 && hhmm < 22 * 60) return false;
      if (day === 5 && hhmm >= 21 * 60) return false;
      return true;
    case "stub":
    default:
      return false;
  }
}

function MarketStatus({ schedule }) {
  if (schedule === "stub") {
    return <span className="text-gray-600 text-xs">— stub</span>;
  }
  const open = isMarketOpen(schedule);
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${open ? "text-emerald-400" : "text-gray-500"}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${open ? "bg-emerald-400" : "bg-gray-600"}`} />
      {open ? "Abierto" : "Cerrado"}
    </span>
  );
}

const FACTORS = [
  {
    name: "NDF USDCLP 1M",
    symbol: "USDCLP_NDF",
    beta: "0.55",
    direction: "Directo",
    inverted: false,
    source: "Stub manual (futuro: Bloomberg/Reuters)",
    schedule: "stub",
    scheduleDesc: "N/A (sin feed activo)",
  },
  {
    name: "USD/BRL",
    symbol: "USDBRL",
    beta: "0.20",
    direction: "Directo",
    inverted: false,
    source: "Yahoo Finance / Frankfurter (ECB)",
    schedule: "forex",
    scheduleDesc: "Forex 24h — Dom 22:00–Vie 22:00 UTC",
  },
  {
    name: "DXY (Índice Dólar)",
    symbol: "DXY",
    beta: "0.15",
    direction: "Directo",
    inverted: false,
    source: "Yahoo Finance (DX-Y.NYB)",
    schedule: "us_futures",
    scheduleDesc: "ICE Futures — Dom 22:00–Vie 21:00 UTC",
  },
  {
    name: "Cobre (HG Futures)",
    symbol: "COPPER",
    beta: "0.10",
    direction: "Invertido",
    inverted: true,
    source: "Yahoo Finance (HG=F)",
    schedule: "us_futures",
    scheduleDesc: "COMEX — Dom 23:00–Vie 22:00 UTC",
  },
  {
    name: "USD/MXN",
    symbol: "USDMXN",
    beta: "0.08",
    direction: "Directo",
    inverted: false,
    source: "Yahoo Finance / Frankfurter (ECB)",
    schedule: "forex",
    scheduleDesc: "Forex 24h — Dom 22:00–Vie 22:00 UTC",
  },
  {
    name: "VIX (volatilidad S&P)",
    symbol: "VIX",
    beta: "0.05",
    direction: "Directo",
    inverted: false,
    source: "Yahoo Finance (^VIX)",
    schedule: "us_equity",
    scheduleDesc: "CBOE — Lun–Vie 13:30–20:00 UTC",
  },
  {
    name: "US10Y (Bono 10Y EE.UU.)",
    symbol: "US10Y",
    beta: "0.04",
    direction: "Directo",
    inverted: false,
    source: "Yahoo Finance (^TNX)",
    schedule: "us_futures",
    scheduleDesc: "CME Futures — Dom 22:00–Vie 21:00 UTC",
  },
  {
    name: "USD/COP",
    symbol: "USDCOP",
    beta: "0.04",
    direction: "Directo",
    inverted: false,
    source: "Yahoo Finance / Frankfurter (ECB)",
    schedule: "forex",
    scheduleDesc: "Forex 24h — Dom 22:00–Vie 22:00 UTC",
  },
  {
    name: "ECH (ETF Chile iShares)",
    symbol: "ECH",
    beta: "0.03",
    direction: "Invertido",
    inverted: true,
    source: "Yahoo Finance (ECH)",
    schedule: "us_equity",
    scheduleDesc: "NYSE Arca — Lun–Vie 13:30–21:00 UTC",
  },
];

export default function AcercaDePanel() {
  return (
    <div className="space-y-6 max-w-4xl">

      {/* Factores y betas */}
      <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-amber-400 mb-4">Factores del modelo y fuentes de datos</h2>
        <p className="text-gray-300 text-sm mb-4">
          Los betas actuales son estimaciones iniciales basadas en literatura académica y comportamiento
          histórico observado del USDCLP. Se recalibrarán por regresión OLS una vez que haya suficiente
          historia acumulada en la base de datos.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-400 font-medium pb-2 pr-4">Factor</th>
                <th className="text-left text-gray-400 font-medium pb-2 pr-4">Símbolo</th>
                <th className="text-right text-gray-400 font-medium pb-2 pr-4">Beta (β)</th>
                <th className="text-left text-gray-400 font-medium pb-2 pr-4">Dirección</th>
                <th className="text-left text-gray-400 font-medium pb-2 pr-4">Horario (UTC)</th>
                <th className="text-left text-gray-400 font-medium pb-2 pr-4">Estado</th>
                <th className="text-left text-gray-400 font-medium pb-2">Fuente</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {FACTORS.map((f) => (
                <tr key={f.symbol}>
                  <td className="py-2.5 pr-4 text-gray-100">{f.name}</td>
                  <td className="py-2.5 pr-4 font-mono text-gray-400">{f.symbol}</td>
                  <td className="py-2.5 pr-4 text-right font-mono text-amber-300">{f.beta}</td>
                  <td className={`py-2.5 pr-4 ${f.inverted ? "text-emerald-400" : "text-gray-300"}`}>
                    {f.inverted ? `Invertido ↑${f.symbol.replace("beta_", "")} = ↓USDCLP` : "Directo"}
                  </td>
                  <td className="py-2.5 pr-4 text-gray-500 text-xs">{f.scheduleDesc}</td>
                  <td className="py-2.5 pr-4"><MarketStatus schedule={f.schedule} /></td>
                  <td className="py-2.5 text-gray-400">{f.source}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-700">
                <td colSpan={2} className="pt-2.5 text-gray-400 text-xs">Total pesos</td>
                <td className="pt-2.5 text-right font-mono text-amber-300 font-semibold">1.24</td>
                <td colSpan={4} className="pt-2.5 text-gray-500 text-xs">
                  (los betas no suman 1 por diseño; el modelo los renormaliza si faltan factores)
                </td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm">
            <p className="text-gray-400 font-medium mb-1">Yahoo Finance</p>
            <p className="text-gray-500">
              API no oficial (crumb auth). Actualiza cada <strong className="text-gray-300">5 minutos</strong>.
              Cubre DXY, VIX, cobre, US10Y, ECH y todos los pares forex.
              No requiere API key; datos con ~15 min de delay para algunos instrumentos.
            </p>
          </div>
          <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm">
            <p className="text-gray-400 font-medium mb-1">Frankfurter (ECB)</p>
            <p className="text-gray-500">
              API oficial del Banco Central Europeo. <strong className="text-gray-300">Gratuita, sin registro</strong>.
              Actualiza cada <strong className="text-gray-300">30 segundos</strong> (aunque los datos son diarios).
              Cubre USDBRL, USDMXN, USDCOP. Sirve de respaldo cuando Yahoo no responde.
            </p>
          </div>
          <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm">
            <p className="text-gray-400 font-medium mb-1">Buda.com</p>
            <p className="text-gray-500">
              Precio de mercado USDC-CLP en Buda como proxy del tipo de cambio spot.
              Actualiza cada <strong className="text-gray-300">30 segundos</strong>.
            </p>
          </div>
          <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm">
            <p className="text-gray-400 font-medium mb-1">Mindicador / CMF</p>
            <p className="text-gray-500">
              Dólar observado (USDCLP_OBS) publicado por el Banco Central de Chile.
              Es el precio oficial de cierre BEC del día anterior.
              Se usa como anclaje base del modelo.
            </p>
          </div>
        </div>
      </section>

      {/* Qué es */}
      <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-amber-400 mb-3">¿Qué es Shadow USDCLP?</h2>
        <p className="text-gray-300 leading-relaxed">
          El tipo de cambio oficial USD/CLP que publica la Bolsa Electrónica de Chile (BEC) solo existe
          durante el horario de operación: <strong className="text-gray-100">lunes a viernes de 9:00 a 15:30 CLT</strong>.
          Fuera de ese horario —noches, fines de semana y feriados— el mercado local está cerrado,
          pero el mundo sigue moviéndose: el peso brasileño sube, el cobre cae, el dólar se fortalece.
        </p>
        <p className="text-gray-300 leading-relaxed mt-3">
          Shadow USDCLP es un <strong className="text-gray-100">índice sintético en tiempo real</strong> que estima
          dónde debería estar el dólar chileno si la BEC estuviera abierta en este momento.
          Está pensado para operaciones en Buda.com y para cualquier contexto donde se necesite
          una referencia de precio fuera del horario oficial.
        </p>
      </section>

      {/* Fórmula */}
      <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-amber-400 mb-3">Cómo se calcula</h2>
        <p className="text-gray-300 leading-relaxed mb-4">
          El modelo parte del <strong className="text-gray-100">último cierre oficial de la BEC</strong> y le aplica
          un ajuste proporcional basado en cuánto se movieron los factores externos desde ese cierre:
        </p>

        <div className="bg-gray-950 border border-gray-700 rounded-lg px-5 py-4 font-mono text-sm text-amber-300 mb-4">
          Shadow(t) = BEC_LastClose × (1 + Σ βᵢ × Δ%Factorᵢ(t))
        </div>

        <ul className="space-y-2 text-gray-300 text-sm">
          <li>
            <span className="text-gray-100 font-medium">BEC_LastClose</span> — precio de cierre del último día hábil en la Bolsa Electrónica de Chile.
          </li>
          <li>
            <span className="text-gray-100 font-medium">Δ%Factorᵢ(t)</span> — variación porcentual del factor i desde el cierre hasta ahora:
            <span className="font-mono text-amber-300 ml-1">(precio_ahora − precio_al_cierre) / precio_al_cierre</span>
          </li>
          <li>
            <span className="text-gray-100 font-medium">βᵢ</span> — peso (sensibilidad) de cada factor, calibrado por regresión sobre datos históricos.
          </li>
        </ul>

        <p className="text-gray-400 text-sm mt-4">
          Algunos factores se invierten antes de aplicar el beta: el cobre y el ETF ECH
          tienen relación inversa con el USDCLP (cuando suben, el peso se aprecia y el dólar baja).
          El modelo los invierte automáticamente antes de computar el ajuste.
        </p>

        <p className="text-gray-400 text-sm mt-3">
          Si algún factor no está disponible en el momento de cálculo, el modelo renormaliza
          los betas restantes para que la suma de pesos se mantenga equivalente. Si no hay ningún
          factor disponible, el shadow price cae back al último cierre BEC con una banda de confianza
          máxima.
        </p>
      </section>

      {/* Banda de confianza */}
      <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-amber-400 mb-3">Banda de confianza</h2>
        <p className="text-gray-300 leading-relaxed mb-3">
          El modelo reconoce que su precisión se degrada con el tiempo: cuánto más lejos estamos
          del último cierre, más incertidumbre hay. La banda se calcula como:
        </p>
        <div className="bg-gray-950 border border-gray-700 rounded-lg px-5 py-4 font-mono text-sm text-amber-300 mb-4">
          spread_half = k × σ_modelo × √(horas_desde_cierre / 24)
        </div>
        <ul className="space-y-2 text-gray-300 text-sm">
          <li>
            <span className="text-gray-100 font-medium">σ_modelo</span> — desviación estándar del error del modelo,
            calculada sobre los últimos 60 puntos donde existió precio oficial para comparar.
          </li>
          <li>
            <span className="text-gray-100 font-medium">k = 2.0</span> — factor de cobertura (configurable). Con k=2 la banda cubre aproximadamente ±2σ.
          </li>
          <li>
            <span className="text-gray-100 font-medium">√(horas / 24)</span> — la incertidumbre crece con la raíz cuadrada del tiempo, como un proceso de difusión.
          </li>
        </ul>
      </section>

      {/* Pestañas */}
      <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-amber-400 mb-4">Guía de pestañas</h2>
        <div className="space-y-4">
          <div className="flex gap-4">
            <span className="text-amber-400 font-medium w-28 shrink-0">Dashboard</span>
            <p className="text-gray-300 text-sm leading-relaxed">
              Precio shadow actual con su banda de confianza, tiempo desde el último cierre BEC,
              y tabla de factores activos con sus valores actuales y el delta acumulado desde el cierre.
            </p>
          </div>
          <div className="flex gap-4">
            <span className="text-amber-400 font-medium w-28 shrink-0">Factores</span>
            <p className="text-gray-300 text-sm leading-relaxed">
              Detalle completo de cada factor: precio al cierre BEC, precio actual, variación porcentual,
              beta aplicado y contribución individual al ajuste del shadow price.
            </p>
          </div>
          <div className="flex gap-4">
            <span className="text-amber-400 font-medium w-28 shrink-0">Histórico</span>
            <p className="text-gray-300 text-sm leading-relaxed">
              Gráfico del shadow USDCLP y su banda de confianza a lo largo del tiempo.
              Permite visualizar cómo se fue comportando el estimado respecto al cierre oficial.
            </p>
          </div>
          <div className="flex gap-4">
            <span className="text-amber-400 font-medium w-28 shrink-0">Correlaciones</span>
            <p className="text-gray-300 text-sm leading-relaxed">
              Matriz de correlación entre el USDCLP histórico y cada factor. Muestra qué tan bien
              explica cada variable los movimientos del tipo de cambio en la ventana seleccionada.
            </p>
          </div>
          <div className="flex gap-4">
            <span className="text-amber-400 font-medium w-28 shrink-0">Calibración</span>
            <p className="text-gray-300 text-sm leading-relaxed">
              Permite recalibrar los betas por regresión OLS sobre un período histórico,
              comparar distintas versiones del modelo y activar el conjunto de parámetros que
              mejor se ajuste a los datos recientes.
            </p>
          </div>
        </div>
      </section>

      {/* Limitaciones */}
      <section className="bg-gray-900 border border-amber-900/30 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-amber-400 mb-3">Limitaciones y consideraciones</h2>
        <ul className="space-y-2 text-gray-400 text-sm">
          <li className="flex gap-2"><span className="text-amber-500 shrink-0">—</span>
            El modelo es lineal y no captura efectos de segundo orden ni cambios de régimen bruscos.
          </li>
          <li className="flex gap-2"><span className="text-amber-500 shrink-0">—</span>
            Los betas iniciales son estimaciones; la precisión mejora con cada recalibración sobre datos propios.
          </li>
          <li className="flex gap-2"><span className="text-amber-500 shrink-0">—</span>
            Yahoo Finance puede experimentar delays o rate-limiting; en ese caso el modelo opera
            con los factores disponibles (Frankfurter) y renormaliza.
          </li>
          <li className="flex gap-2"><span className="text-amber-500 shrink-0">—</span>
            El NDF USDCLP 1M (beta más alto: 0.55) actualmente usa un stub estático.
            Conectarlo a datos reales de Bloomberg o Reuters mejoraría significativamente la precisión.
          </li>
          <li className="flex gap-2"><span className="text-amber-500 shrink-0">—</span>
            Este índice es una estimación con fines informativos. No constituye asesoría financiera.
          </li>
        </ul>
      </section>

    </div>
  );
}
