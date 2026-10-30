"""Genera datos ficticios de 3 meses para demostrar la analítica (CA-5 y CA-6).

Solo crea eventos y gasto de adquisición: no hay datos personales. Usa una
semilla fija, así el reporte es igual en cada ejecución.
"""
from __future__ import annotations

import math
import random
import uuid
from datetime import date, datetime, timedelta, timezone

from app.domain import CANALES, CLAVES_PASOS, TipoEvento

# (iniciados, tasa de finalización, mediana en minutos, gasto total PEN)
# Cuenta la historia esperada: la mediana baja de ~6 a <3 minutos y el CAC llega a la meta.
PERFIL_MESES = (
    (1500, 0.62, 5.6, 11_000.0),
    (1900, 0.70, 3.6, 13_600.0),
    (2200, 0.76, 2.8, 15_800.0),
)
PESO_CANALES = {"organico": 0.25, "redes_sociales": 0.40, "referidos": 0.20, "campana_comercios": 0.15}
TASA_RECHAZO = 0.03


def meses_previos(hoy: date, cantidad: int = 3) -> list[date]:
    """Primer día de los `cantidad` meses completos anteriores a `hoy`."""
    meses, cursor = [], hoy.replace(day=1)
    for _ in range(cantidad):
        cursor = (cursor - timedelta(days=1)).replace(day=1)
        meses.append(cursor)
    return list(reversed(meses))


def _evento(tipo: TipoEvento, oid: str, canal: str, momento: datetime, **extra) -> dict:
    e = {"id": str(uuid.uuid4()), "tipo": tipo.value, "onboarding_id": oid, "canal": canal,
         "ocurrido_en": momento.isoformat(timespec="seconds"), "demo": True}
    e.update(extra)
    return e


def generar(hoy: date, semilla: int = 42) -> tuple[list[dict], list[dict]]:
    rnd = random.Random(semilla)
    eventos: list[dict] = []
    gastos: list[dict] = []
    canales = list(PESO_CANALES)
    pesos = list(PESO_CANALES.values())

    for inicio_mes, (iniciados, tasa, med, gasto) in zip(meses_previos(hoy), PERFIL_MESES):
        mes = inicio_mes.strftime("%Y-%m")
        # El reparto del gasto no es proporcional al volumen: unos canales salen más caros.
        reparto = {"organico": 0.0, "redes_sociales": 0.55, "referidos": 0.15, "campana_comercios": 0.30}
        gastos += [{"mes": mes, "canal": c, "monto_pen": round(gasto * p, 2), "demo": True}
                   for c, p in reparto.items()]

        for _ in range(iniciados):
            oid, canal = str(uuid.uuid4()), rnd.choices(canales, pesos)[0]
            # Se inicia en los primeros 27 días del mes para que la activación caiga en el mismo mes.
            t = datetime(inicio_mes.year, inicio_mes.month, 1, tzinfo=timezone.utc) + timedelta(
                days=rnd.randint(0, 26), seconds=rnd.randint(8 * 3600, 22 * 3600))
            eventos.append(_evento(TipoEvento.ONBOARDING_INICIADO, oid, canal, t))
            total = rnd.lognormvariate(math.log(med * 60), 0.45)

            dado = rnd.random()
            if dado < tasa:
                for orden, paso in enumerate(CLAVES_PASOS, start=1):
                    momento = t + timedelta(seconds=total * orden / len(CLAVES_PASOS))
                    eventos.append(_evento(TipoEvento.PASO_COMPLETADO, oid, canal, momento, paso=paso, orden=orden))
                fin = t + timedelta(seconds=total)
                eventos.append(_evento(TipoEvento.WALLET_ACTIVADA, oid, canal, fin))
                eventos.append(_evento(TipoEvento.ONBOARDING_CERRADO, oid, canal, fin,
                                       resultado="COMPLETADO", duracion_segundos=int(total)))
            elif dado < tasa + TASA_RECHAZO:
                for orden, paso in enumerate(CLAVES_PASOS[:2], start=1):
                    eventos.append(_evento(TipoEvento.PASO_COMPLETADO, oid, canal,
                                           t + timedelta(seconds=total * orden / 5), paso=paso, orden=orden))
                fin = t + timedelta(seconds=total * 3 / 5)
                eventos.append(_evento(TipoEvento.PASO_FALLIDO, oid, canal, fin,
                                       paso="identidad", codigo_error="IDENTIDAD_NO_VALIDADA"))
                eventos.append(_evento(TipoEvento.ONBOARDING_CERRADO, oid, canal, fin,
                                       resultado="RECHAZADO", ultimo_paso="identidad",
                                       duracion_segundos=int(total * 3 / 5)))
            else:
                # Abandono: la mayoría se va en el celular (OTP) o al crear la clave.
                ultimo = rnd.choices(range(len(CLAVES_PASOS)), [0.2, 0.35, 0.1, 0.1, 0.25])[0]
                for orden, paso in enumerate(CLAVES_PASOS[:ultimo], start=1):
                    eventos.append(_evento(TipoEvento.PASO_COMPLETADO, oid, canal,
                                           t + timedelta(seconds=total * orden / 5), paso=paso, orden=orden))
                fin = t + timedelta(seconds=total * (ultimo + 1) / 5)
                if rnd.random() < 0.5:
                    codigo = {"datos_personales": "DNI_INVALIDO", "celular": "OTP_INCORRECTO",
                              "identidad": "AUTORIZACION_REQUERIDA", "terminos": "TERMINOS_REQUERIDOS",
                              "clave": "CLAVE_INSEGURA"}[CLAVES_PASOS[ultimo]]
                    eventos.append(_evento(TipoEvento.PASO_FALLIDO, oid, canal, fin,
                                           paso=CLAVES_PASOS[ultimo], codigo_error=codigo))
                eventos.append(_evento(TipoEvento.ONBOARDING_CERRADO, oid, canal, fin,
                                       resultado="ABANDONADO", ultimo_paso=CLAVES_PASOS[ultimo],
                                       duracion_segundos=int(total * (ultimo + 1) / 5)))
    assert set(PESO_CANALES) == set(CANALES)
    return eventos, gastos


def cargar(store, hoy: date) -> dict:
    """Carga los datos demo en memoria (no se escriben en el archivo JSON)."""
    eventos, gastos = generar(hoy)
    with store.read():
        store.demo = {"eventos": eventos, "gasto_adquisicion": gastos}
    return {"eventos_demo": len(eventos), "registros_gasto_demo": len(gastos)}
