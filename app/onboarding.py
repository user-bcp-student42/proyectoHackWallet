"""Caso de uso: registro y activación de la wallet."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Callable

from app import domain
from app.domain import EstadoFlujo, EstadoWallet, ErrorValidacion, TipoEvento
from app.store import JsonStore

Reloj = Callable[[], datetime]


def reloj_utc() -> datetime:
    return datetime.now(timezone.utc)


class NoEncontrado(Exception):
    pass


class Conflicto(Exception):
    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def hash_clave(clave: str, sal: bytes | None = None) -> str:
    sal = sal or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, 200_000)
    return f"pbkdf2_sha256${sal.hex()}${digest.hex()}"


def nuevo_evento(tipo: TipoEvento, onboarding: dict, momento: datetime, **extra) -> dict:
    """Evento analítico (CA-4). Nunca incluye datos personales."""
    evento = {
        "id": str(uuid.uuid4()),
        "tipo": tipo.value,
        "onboarding_id": onboarding["id"],
        "canal": onboarding["canal_adquisicion"],
        "ocurrido_en": _iso(momento),
    }
    evento.update({k: v for k, v in extra.items() if v is not None})
    return evento


class OnboardingService:
    def __init__(self, store: JsonStore, reloj: Reloj = reloj_utc) -> None:
        self.store = store
        self.reloj = reloj

    # ── Comandos ──────────────────────────────────────────────────────────

    def iniciar(self, canal: str | None = None) -> dict:
        canal = canal or "organico"
        if canal not in domain.CANALES:
            raise ErrorValidacion([{
                "campo": "canal_adquisicion", "codigo": "CANAL_INVALIDO",
                "mensaje": f"Canal desconocido. Usa uno de: {', '.join(domain.CANALES)}.",
            }])
        ahora = self.reloj()
        onboarding = {
            "id": str(uuid.uuid4()),
            "wallet_id": str(uuid.uuid4()),
            "canal_adquisicion": canal,
            "estado": EstadoFlujo.EN_CURSO.value,
            "pasos_completados": [],
            "datos": {},
            "iniciado_en": _iso(ahora),
            "cerrado_en": None,
        }
        wallet = {"id": onboarding["wallet_id"], "onboarding_id": onboarding["id"],
                  "estado": EstadoWallet.PENDIENTE.value, "activada_en": None}
        with self.store.write() as db:
            db["onboardings"][onboarding["id"]] = onboarding
            db["wallets"][wallet["id"]] = wallet
            db["eventos"].append(nuevo_evento(TipoEvento.ONBOARDING_INICIADO, onboarding, ahora))
        return self.obtener(onboarding["id"])

    def enviar_paso(self, onboarding_id: str, paso: str, datos: dict) -> dict:
        if paso not in domain.CLAVES_PASOS:
            raise NoEncontrado(f"Paso desconocido: {paso}")
        error: ErrorValidacion | None = None
        with self.store.write() as db:
            onboarding = self._cargar(db, onboarding_id)
            self._exigir_en_curso(onboarding)
            actual = self._paso_actual(onboarding)
            if paso != actual:
                raise Conflicto("PASO_FUERA_DE_ORDEN",
                                f"Primero completa el paso «{self._titulo(actual)}».")
            ahora = self.reloj()
            try:
                self._aplicar_paso(db, onboarding, paso, datos, ahora)
            except ErrorValidacion as exc:
                # El avance queda bloqueado, pero el intento fallido se registra.
                db["eventos"].append(nuevo_evento(TipoEvento.PASO_FALLIDO, onboarding, ahora,
                                                  paso=paso, codigo_error=exc.codigo))
                error = exc
        if error:
            raise error
        return self.obtener(onboarding_id)

    def abandonar(self, onboarding_id: str) -> dict:
        with self.store.write() as db:
            onboarding = self._cargar(db, onboarding_id)
            self._exigir_en_curso(onboarding)
            ahora = self.reloj()
            self._cerrar(db, onboarding, EstadoFlujo.ABANDONADO, ahora,
                         ultimo_paso=self._paso_actual(onboarding))
        return self.obtener(onboarding_id)

    # ── Consultas ─────────────────────────────────────────────────────────

    def obtener(self, onboarding_id: str) -> dict:
        with self.store.read() as db:
            onboarding = self._cargar(db, onboarding_id)
            wallet = db["wallets"][onboarding["wallet_id"]]
            return self._vista(onboarding, wallet)

    def eventos(self, onboarding_id: str) -> list[dict]:
        with self.store.read() as db:
            self._cargar(db, onboarding_id)
            return [e for e in db["eventos"] if e["onboarding_id"] == onboarding_id]

    def punto_entrada_pagos(self, wallet_id: str) -> dict:
        """CA-3: solo una wallet activa accede al punto de entrada de pagos."""
        with self.store.read() as db:
            wallet = db["wallets"].get(wallet_id)
            if wallet is None:
                raise NoEncontrado("Wallet no encontrada")
            if wallet["estado"] != EstadoWallet.ACTIVA.value:
                raise Conflicto("WALLET_NO_ACTIVA",
                                "Tu wallet aún no está activa. Completa tu registro para empezar a pagar.")
            onboarding = db["onboardings"][wallet["onboarding_id"]]
            return {
                "wallet_id": wallet_id,
                "titular": onboarding["datos"].get("nombres"),
                "estado_wallet": wallet["estado"],
                "opciones": [
                    {"clave": "pagar_qr", "titulo": "Pagar con QR"},
                    {"clave": "transferir_alias", "titulo": "Transferir a un celular"},
                ],
                "nota": "Punto de entrada simulado: los pagos de bajo monto pertenecen a otra historia del MVP.",
            }

    # ── Internos ──────────────────────────────────────────────────────────

    def _aplicar_paso(self, db: dict, onboarding: dict, paso: str, datos: dict, ahora: datetime) -> None:
        guardados = onboarding["datos"]
        if paso == "datos_personales":
            validos = domain.validar_datos_personales(datos, ahora.date())
            if self._dni_con_wallet_activa(db, validos["dni"]):
                raise ErrorValidacion([{
                    "campo": "dni", "codigo": "DNI_YA_REGISTRADO",
                    "mensaje": "Ya existe una wallet activa con este DNI. Si es tuya, ingresa con tu celular.",
                }])
            guardados.update(validos)
        elif paso == "celular":
            guardados.update(domain.validar_celular(datos))
        elif paso == "identidad":
            resultado = domain.validar_identidad(datos, guardados["dni"])
            if not resultado["identidad_aprobada"]:
                db["eventos"].append(nuevo_evento(TipoEvento.PASO_FALLIDO, onboarding, ahora,
                                                  paso=paso, codigo_error="IDENTIDAD_NO_VALIDADA"))
                self._cerrar(db, onboarding, EstadoFlujo.RECHAZADO, ahora, ultimo_paso=paso)
                return
        elif paso == "terminos":
            domain.validar_terminos(datos)
            guardados["terminos_aceptados_en"] = _iso(ahora)
        elif paso == "clave":
            clave = domain.validar_clave(datos, guardados["fecha_nacimiento"])
            guardados["clave_hash"] = hash_clave(clave)

        onboarding["pasos_completados"].append(paso)
        db["eventos"].append(nuevo_evento(TipoEvento.PASO_COMPLETADO, onboarding, ahora,
                                          paso=paso, orden=domain.CLAVES_PASOS.index(paso) + 1))
        if len(onboarding["pasos_completados"]) == len(domain.PASOS):
            wallet = db["wallets"][onboarding["wallet_id"]]
            wallet["estado"] = EstadoWallet.ACTIVA.value
            wallet["activada_en"] = _iso(ahora)
            db["eventos"].append(nuevo_evento(TipoEvento.WALLET_ACTIVADA, onboarding, ahora))
            self._cerrar(db, onboarding, EstadoFlujo.COMPLETADO, ahora)

    def _cerrar(self, db: dict, onboarding: dict, resultado: EstadoFlujo, ahora: datetime,
                ultimo_paso: str | None = None) -> None:
        onboarding["estado"] = resultado.value
        onboarding["cerrado_en"] = _iso(ahora)
        if resultado == EstadoFlujo.RECHAZADO:
            db["wallets"][onboarding["wallet_id"]]["estado"] = EstadoWallet.RECHAZADA.value
        inicio = datetime.fromisoformat(onboarding["iniciado_en"])
        duracion = int((ahora - inicio).total_seconds())
        db["eventos"].append(nuevo_evento(TipoEvento.ONBOARDING_CERRADO, onboarding, ahora,
                                          resultado=resultado.value, ultimo_paso=ultimo_paso,
                                          duracion_segundos=duracion))

    @staticmethod
    def _dni_con_wallet_activa(db: dict, dni: str) -> bool:
        return any(
            o["datos"].get("dni") == dni
            and db["wallets"][o["wallet_id"]]["estado"] == EstadoWallet.ACTIVA.value
            for o in db["onboardings"].values()
        )

    @staticmethod
    def _cargar(db: dict, onboarding_id: str) -> dict:
        onboarding = db["onboardings"].get(onboarding_id)
        if onboarding is None:
            raise NoEncontrado("Registro no encontrado")
        return onboarding

    @staticmethod
    def _exigir_en_curso(onboarding: dict) -> None:
        if onboarding["estado"] != EstadoFlujo.EN_CURSO.value:
            raise Conflicto("ONBOARDING_CERRADO",
                            "Este registro ya terminó. Si necesitas una wallet nueva, inicia otro registro.")

    @staticmethod
    def _paso_actual(onboarding: dict) -> str | None:
        hechos = onboarding["pasos_completados"]
        return domain.CLAVES_PASOS[len(hechos)] if len(hechos) < len(domain.PASOS) else None

    @staticmethod
    def _titulo(clave: str | None) -> str:
        return next((p.titulo for p in domain.PASOS if p.clave == clave), "")

    def _vista(self, onboarding: dict, wallet: dict) -> dict:
        """Respuesta pública. Incluye la secuencia de pasos y el paso actual (CA-1)."""
        estado = onboarding["estado"]
        actual = self._paso_actual(onboarding) if estado == EstadoFlujo.EN_CURSO.value else None
        hechos = set(onboarding["pasos_completados"])
        pasos = []
        for i, p in enumerate(domain.PASOS, start=1):
            if p.clave in hechos:
                estado_paso = "COMPLETADO"
            elif p.clave == actual:
                estado_paso = "ACTUAL"
            elif estado == EstadoFlujo.RECHAZADO.value and p.clave == "identidad":
                estado_paso = "FALLIDO"
            else:
                estado_paso = "PENDIENTE"
            pasos.append({"orden": i, "clave": p.clave, "titulo": p.titulo,
                          "descripcion": p.descripcion, "estado": estado_paso})

        paso_actual = next((p for p in pasos if p["estado"] == "ACTUAL"), None)
        if paso_actual:
            siguiente = (f"Paso {paso_actual['orden']} de {len(pasos)}: {paso_actual['titulo']}. "
                         f"{paso_actual['descripcion']}")
        elif estado == EstadoFlujo.COMPLETADO.value:
            siguiente = "¡Tu wallet está activa! Ya puedes hacer pagos de bajo monto."
        elif estado == EstadoFlujo.RECHAZADO.value:
            siguiente = ("No pudimos validar tu identidad con el DNI ingresado. "
                         "Acércate a una agencia con tu DNI físico para completar tu registro.")
        else:
            siguiente = "Cerraste el registro. Puedes empezar de nuevo cuando quieras."

        datos = onboarding["datos"]
        activa = wallet["estado"] == EstadoWallet.ACTIVA.value
        return {
            "id": onboarding["id"],
            "estado": estado,
            "canal_adquisicion": onboarding["canal_adquisicion"],
            "total_pasos": len(pasos),
            "pasos_completados": len(hechos),
            "paso_actual": paso_actual,
            "pasos": pasos,
            "siguiente_accion": siguiente,
            "wallet": {"id": wallet["id"], "estado": wallet["estado"], "activada_en": wallet["activada_en"]},
            "puede_pagar": activa,
            "punto_entrada_pagos": f"/api/wallets/{wallet['id']}/pagos" if activa else None,
            "resumen_datos": {
                "dni": domain.enmascarar(datos.get("dni")),
                "nombres": datos.get("nombres"),
                "celular": domain.enmascarar(datos.get("celular")),
            },
            "iniciado_en": onboarding["iniciado_en"],
            "cerrado_en": onboarding["cerrado_en"],
        }
