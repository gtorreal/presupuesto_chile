# Shadow USDCLP

Índice sintético en tiempo real del USDCLP para horas fuera de mercado BEC.

## Arquitectura

```
┌─────────────┐   ticks   ┌──────────────┐   shadow   ┌─────────────┐
│  collector  │ ────────► │  TimescaleDB │ ◄───────── │  calculator │
│ (pollers)   │           │  PostgreSQL  │            │  (shadow +  │
└─────────────┘           └──────────────┘            │  corr engine│
                                  │                   └─────────────┘
                                  ▼
                          ┌──────────────┐
                          │   FastAPI    │ ◄── Buda pricing engine
                          └──────────────┘
                                  │
                          ┌──────────────┐
                          │  React SPA   │ ◄── Dashboard web
                          └──────────────┘
```

## Quick start

```bash
# 1. Copiar y completar variables de entorno
cp .env.example .env
# Editar .env con tus API keys (el MVP funciona sin keys externas)

# 2. Levantar todos los servicios
docker compose up -d

# 3. (Opcional) Cargar datos históricos
docker compose exec collector python /app/../scripts/seed_historical.py

# 4. Abrir el dashboard
open http://localhost:3000
```

## Servicios

| Servicio     | Puerto | Descripción |
|-------------|--------|-------------|
| `db`        | 5432   | TimescaleDB |
| `collector` | 8001   | Health endpoint del colector |
| `calculator`| 8002   | Health endpoint del calculador |
| `api`       | 8000   | REST API (FastAPI + Swagger en /docs) |
| `frontend`  | 3000   | Dashboard React |

## MVP — Fuentes activas sin API keys

| Fuente        | Símbolo        | API key requerida |
|--------------|----------------|-------------------|
| Buda USDC-CLP | USDCLP        | No                |
| Buda USDT-CLP | USDCLP_USDT   | No                |
| mindicador.cl | USDCLP_OBS    | No                |
| CMF Chile     | USDCLP_OBS    | Sí (gratis)       |
| Massive.com   | USDBRL/MXN/COP| Sí ($49/mo)       |
| Twelve Data   | DXY/HG/VIX/etc| Sí ($99/mo)       |

## Fórmula Shadow USDCLP

```
Shadow(t) = BEC_LastClose × (1 + Σ βᵢ × Δ%Factorᵢ(t))

Donde:
  Δ%Factor(t) = (Factor_now - Factor_at_BEC_close) / Factor_at_BEC_close
  Copper y ECH se invierten (higher → CLP stronger → USDCLP lower)
  Si faltan factores, se re-normalizan los betas proporcionalmente
```

**Banda de confianza:**
```
spread_half = k × σ_model × √(hours_since_BEC_close / 24)
```

## API REST

```bash
# Shadow price actual
curl http://localhost:8000/api/v1/shadow-price

# Correlaciones (ventana 90 días)
curl http://localhost:8000/api/v1/correlations?window=90

# Parámetros del modelo
curl http://localhost:8000/api/v1/model/params

# Re-calibrar con OLS
curl -X POST http://localhost:8000/api/v1/model/recalibrate \
  -H "Content-Type: application/json" \
  -d '{"window_start":"2024-07-01","window_end":"2025-01-01"}'

# Activar parámetros
curl -X POST http://localhost:8000/api/v1/model/activate \
  -H "Content-Type: application/json" \
  -d '{"param_id":2}'
```

Swagger UI completa en: http://localhost:8000/docs

## Datos manuales (stubs premium)

### NDF USDCLP 1M

Actualizar `/data/ndf_manual.json` montado en el collector:
```json
{"usdclp_ndf_1m": 955.50, "updated_at": "2025-01-15T18:00:00Z"}
```

### BEC/Datatec cierre oficial

Actualizar `/data/bec_close.json`:
```json
{"usdclp_close": 951.20, "date": "2025-01-15", "source": "manual"}
```

O usar CSV (`/data/bec_close.csv`):
```csv
date,close
2025-01-15,951.20
2025-01-14,948.50
```

## Calibración del modelo

1. Ir al tab **Calibración** en el dashboard
2. Click en **Re-calibrar con OLS** seleccionando la ventana histórica
3. Revisar los betas propuestos, R² y p-values
4. Click **Activar propuestos** si los resultados son satisfactorios

## Iteración futura

- [ ] Massive.com WebSocket feed (en vez de polling REST)
- [ ] Twelve Data WebSocket feed
- [ ] Integración NDF via LSEG Workspace API
- [ ] Scraper BEC/Datatec
- [ ] Panel histórico con "biggest misses"
- [ ] Alertas (Slack/email) cuando shadow diverge >X% del BEC close
