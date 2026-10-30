"""Salida analítica del onboarding (CA-4, CA-5 y CA-6).

Todo se calcula a partir de los eventos, igual que lo haría una
herramienta de analítica externa. Definición usada para la duración
(pregunta abierta de la historia, ver docs/supuestos-y-decisiones.md):

    duración = ocurrido_en(wallet_activada) - ocurrido_en(onboarding_iniciado)

Solo cuentan los onboardings que terminaron con la wallet activa.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import median

from app.domain import CLAVES_PASOS, TipoEvento

MEDIANA_OBJETIVO_MIN = 3.0
MEDIANA_LINEA_BASE_MIN = 8.0
MAU_MIN, MAU_MAX = 1000, 2000
CAC_OBJETIVO_PEN = 10.0


def _dt(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


def _mes(texto: str) -> str:
    return texto[:7]


def mediana(valores: list[float]) -> float | None:
    return round(median(valores), 2) if valores else None


def _indexar(eventos: list[dict]) -> dict[str, dict]:
    """Agrupa los eventos por onboarding: inicio, activación, cierre, pasos."""
    por_id: dict[str, dict] = defaultdict(lambda: {"pasos": set(), "errores": []})
    for e in eventos:
        info = por_id[e["onboarding_id"]]
        info["canal"] = e["canal"]
        tipo = e["tipo"]
        if tipo == TipoEvento.ONBOARDING_INICIADO.value:
            info["inicio"] = e["ocurrido_en"]
        elif tipo == TipoEvento.WALLET_ACTIVADA.value:
            info["activacion"] = e["ocurrido_en"]
        elif tipo == TipoEvento.ONBOARDING_CERRADO.value:
            info["resultado"] = e["resultado"]
        elif tipo == TipoEvento.PASO_COMPLETADO.value:
            info["pasos"].add(e["paso"])
        elif tipo == TipoEvento.PASO_FALLIDO.value:
            info["errores"].append((e["paso"], e["codigo_error"]))
    return {k: v for k, v in por_id.items() if "inicio" in v}


def duracion_min(info: dict) -> float | None:
    if "activacion" not in info:
        return None
    return (_dt(info["activacion"]) - _dt(info["inicio"])).total_seconds() / 60


def resumen(eventos: list[dict], desde: date | None = None, hasta: date | None = None) -> dict:
    """Embudo y tiempos para los onboardings iniciados entre `desde` y `hasta` (inclusive)."""
    def en_rango(info: dict) -> bool:
        dia = _dt(info["inicio"]).date()
        return (desde is None or dia >= desde) and (hasta is None or dia <= hasta)

    cohorte = [i for i in _indexar(eventos).values() if en_rango(i)]
    resultados = Counter(i.get("resultado", "EN_CURSO") for i in cohorte)
    duraciones = [d for d in (duracion_min(i) for i in cohorte) if d is not None]
    iniciados = len(cohorte)
    completados = resultados["COMPLETADO"]
    med = mediana(duraciones)
    errores = Counter(f"{paso}:{codigo}" for i in cohorte for paso, codigo in i["errores"])
    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "iniciados": iniciados,
        "completados": completados,
        "abandonados": resultados["ABANDONADO"],
        "rechazados": resultados["RECHAZADO"],
        "en_curso": resultados["EN_CURSO"],
        "tasa_finalizacion": round(completados / iniciados, 4) if iniciados else None,
        "mediana_minutos": med,
        "linea_base_minutos": MEDIANA_LINEA_BASE_MIN,
        "objetivo_minutos": MEDIANA_OBJETIVO_MIN,
        "cumple_objetivo_mediana": med is not None and med <= MEDIANA_OBJETIVO_MIN,
        "embudo": [
            {"paso": p, "orden": n, "completaron": sum(1 for i in cohorte if p in i["pasos"])}
            for n, p in enumerate(CLAVES_PASOS, start=1)
        ],
        "errores_frecuentes": [{"error": k, "veces": v} for k, v in errores.most_common(5)],
    }


def reporte_mensual(eventos: list[dict], gastos: list[dict]) -> list[dict]:
    """Conteos mensuales de nuevos usuarios activos y atribución del gasto (CA-6).

    Un "nuevo usuario activo" es una wallet activada ese mes. El CAC del mes es
    el gasto de adquisición del mes dividido entre los nuevos usuarios activos.
    """
    activados: dict[str, list[dict]] = defaultdict(list)
    iniciados: Counter = Counter()
    for info in _indexar(eventos).values():
        iniciados[_mes(info["inicio"])] += 1
        if "activacion" in info:
            activados[_mes(info["activacion"])].append(info)

    gasto_mes: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for g in gastos:
        gasto_mes[g["mes"]][g["canal"]] += float(g["monto_pen"])

    filas = []
    for mes in sorted(set(activados) | set(iniciados) | set(gasto_mes)):
        nuevos = activados.get(mes, [])
        por_canal_nuevos = Counter(i["canal"] for i in nuevos)
        gasto_canales = gasto_mes.get(mes, {})
        gasto_total = round(sum(gasto_canales.values()), 2)
        canales = sorted(set(por_canal_nuevos) | set(gasto_canales))
        # Sin gasto registrado el CAC no se puede calcular (no es "cero").
        cac = round(gasto_total / len(nuevos), 2) if nuevos and gasto_total > 0 else None
        med = mediana([duracion_min(i) for i in nuevos])
        filas.append({
            "mes": mes,
            "onboardings_iniciados": iniciados.get(mes, 0),
            "nuevos_usuarios_activos": len(nuevos),
            "mediana_minutos": med,
            "gasto_adquisicion_pen": gasto_total,
            "cac_pen": cac,
            "cumple_rango_mau": MAU_MIN <= len(nuevos) <= MAU_MAX,
            "cumple_cac": None if cac is None else cac <= CAC_OBJETIVO_PEN,
            "cumple_mediana": med is not None and med <= MEDIANA_OBJETIVO_MIN,
            "por_canal": [
                {
                    "canal": c,
                    "nuevos_usuarios_activos": por_canal_nuevos.get(c, 0),
                    "gasto_pen": round(gasto_canales.get(c, 0.0), 2),
                    "cac_pen": (round(gasto_canales[c] / por_canal_nuevos[c], 2)
                                if por_canal_nuevos.get(c) and gasto_canales.get(c) else None),
                }
                for c in canales
            ],
        })
    return filas


def metas() -> dict:
    return {
        "mediana_onboarding_minutos": {"linea_base": MEDIANA_LINEA_BASE_MIN, "objetivo": MEDIANA_OBJETIVO_MIN},
        "nuevos_usuarios_activos_mes": {"min": MAU_MIN, "max": MAU_MAX},
        "cac_pen": {"objetivo": CAC_OBJETIVO_PEN},
    }
