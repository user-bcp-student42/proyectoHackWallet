"""Reglas del onboarding: pasos, estados y validaciones (sin dependencias web)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum


class EstadoWallet(str, Enum):
    PENDIENTE = "PENDIENTE"
    ACTIVA = "ACTIVA"
    RECHAZADA = "RECHAZADA"


class EstadoFlujo(str, Enum):
    EN_CURSO = "EN_CURSO"
    COMPLETADO = "COMPLETADO"
    ABANDONADO = "ABANDONADO"
    RECHAZADO = "RECHAZADO"


class TipoEvento(str, Enum):
    ONBOARDING_INICIADO = "onboarding_iniciado"
    PASO_COMPLETADO = "paso_completado"
    PASO_FALLIDO = "paso_fallido"
    WALLET_ACTIVADA = "wallet_activada"
    ONBOARDING_CERRADO = "onboarding_cerrado"


@dataclass(frozen=True)
class Paso:
    clave: str
    titulo: str
    descripcion: str


PASOS: tuple[Paso, ...] = (
    Paso("datos_personales", "Datos personales", "Ingresa tu DNI, nombres y fecha de nacimiento."),
    Paso("celular", "Verifica tu celular", "Ingresa tu celular y el código que te enviamos por SMS."),
    Paso("identidad", "Verificación de identidad", "Autoriza la validación de tu DNI."),
    Paso("terminos", "Términos y condiciones", "Acepta los términos y el tratamiento de tus datos."),
    Paso("clave", "Crea tu clave de pagos", "Crea una clave de 6 dígitos para confirmar tus pagos."),
)
CLAVES_PASOS = tuple(p.clave for p in PASOS)

CANALES = ("organico", "redes_sociales", "referidos", "campana_comercios")

# Integraciones simuladas (documentadas en docs/supuestos-y-decisiones.md).
OTP_SIMULADO = "123456"
DNIS_RECHAZADOS_SIMULADOS = frozenset({"99999999"})

EDAD_MINIMA = 18
NOMBRE_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]{2,60}$")


class ErrorValidacion(Exception):
    """Datos inválidos u obligatorios faltantes: bloquea el avance (CA-2)."""

    def __init__(self, errores: list[dict[str, str]]) -> None:
        super().__init__("Datos inválidos")
        self.errores = errores

    @property
    def codigo(self) -> str:
        return self.errores[0]["codigo"]


def _err(campo: str, codigo: str, mensaje: str) -> dict[str, str]:
    return {"campo": campo, "codigo": codigo, "mensaje": mensaje}


def _texto(datos: dict, campo: str) -> str:
    valor = datos.get(campo)
    return valor.strip() if isinstance(valor, str) else ""


def calcular_edad(nacimiento: date, hoy: date) -> int:
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def validar_datos_personales(datos: dict, hoy: date) -> dict:
    errores = []
    dni = _texto(datos, "dni")
    if not dni:
        errores.append(_err("dni", "CAMPO_OBLIGATORIO", "Ingresa tu número de DNI."))
    elif not re.fullmatch(r"\d{8}", dni):
        errores.append(_err("dni", "DNI_INVALIDO", "El DNI debe tener exactamente 8 dígitos, sin letras ni espacios."))

    for campo, etiqueta in (("nombres", "tus nombres"), ("apellidos", "tus apellidos")):
        valor = _texto(datos, campo)
        if not valor:
            errores.append(_err(campo, "CAMPO_OBLIGATORIO", f"Ingresa {etiqueta}."))
        elif not NOMBRE_RE.fullmatch(valor):
            errores.append(_err(campo, "NOMBRE_INVALIDO",
                                f"Revisa {etiqueta}: usa solo letras y espacios (entre 2 y 60 caracteres)."))

    texto_fecha = _texto(datos, "fecha_nacimiento")
    nacimiento = None
    if not texto_fecha:
        errores.append(_err("fecha_nacimiento", "CAMPO_OBLIGATORIO", "Ingresa tu fecha de nacimiento."))
    else:
        try:
            nacimiento = date.fromisoformat(texto_fecha)
        except ValueError:
            errores.append(_err("fecha_nacimiento", "FECHA_INVALIDA",
                                "La fecha de nacimiento no es válida. Usa el formato AAAA-MM-DD."))
    if nacimiento is not None:
        edad = calcular_edad(nacimiento, hoy)
        if nacimiento > hoy or edad > 120:
            errores.append(_err("fecha_nacimiento", "FECHA_INVALIDA", "Revisa tu fecha de nacimiento."))
        elif edad < EDAD_MINIMA:
            errores.append(_err("fecha_nacimiento", "MENOR_DE_EDAD",
                                f"Debes tener al menos {EDAD_MINIMA} años para abrir tu wallet."))

    if errores:
        raise ErrorValidacion(errores)
    return {
        "dni": dni,
        "nombres": " ".join(_texto(datos, "nombres").split()),
        "apellidos": " ".join(_texto(datos, "apellidos").split()),
        "fecha_nacimiento": nacimiento.isoformat(),
    }


def validar_celular(datos: dict) -> dict:
    errores = []
    celular = re.sub(r"[\s-]", "", _texto(datos, "celular"))
    if celular.startswith("+51"):
        celular = celular[3:]
    if not celular:
        errores.append(_err("celular", "CAMPO_OBLIGATORIO", "Ingresa tu número de celular."))
    elif not re.fullmatch(r"9\d{8}", celular):
        errores.append(_err("celular", "CELULAR_INVALIDO",
                            "El celular debe tener 9 dígitos y empezar con 9, por ejemplo 987654321."))

    otp = _texto(datos, "codigo_otp")
    if not otp:
        errores.append(_err("codigo_otp", "CAMPO_OBLIGATORIO", "Ingresa el código de 6 dígitos que te enviamos por SMS."))
    elif not re.fullmatch(r"\d{6}", otp):
        errores.append(_err("codigo_otp", "OTP_FORMATO_INVALIDO", "El código tiene 6 dígitos."))
    elif otp != OTP_SIMULADO:
        errores.append(_err("codigo_otp", "OTP_INCORRECTO",
                            "El código no es correcto. Revisa el SMS e inténtalo otra vez."))

    if errores:
        raise ErrorValidacion(errores)
    return {"celular": celular}


def validar_identidad(datos: dict, dni: str) -> dict:
    if datos.get("autoriza_validacion") is not True:
        raise ErrorValidacion([_err("autoriza_validacion", "AUTORIZACION_REQUERIDA",
                                    "Necesitamos tu autorización para validar tu DNI. Marca la casilla para continuar.")])
    return {"identidad_aprobada": dni not in DNIS_RECHAZADOS_SIMULADOS}


def validar_terminos(datos: dict) -> dict:
    errores = []
    if datos.get("acepta_terminos") is not True:
        errores.append(_err("acepta_terminos", "TERMINOS_REQUERIDOS",
                            "Para continuar debes aceptar los términos y condiciones."))
    if datos.get("acepta_tratamiento_datos") is not True:
        errores.append(_err("acepta_tratamiento_datos", "TRATAMIENTO_DATOS_REQUERIDO",
                            "Para continuar debes autorizar el tratamiento de tus datos personales (Ley N.° 29733)."))
    if errores:
        raise ErrorValidacion(errores)
    return {}


def _es_secuencia(clave: str) -> bool:
    difs = {int(b) - int(a) for a, b in zip(clave, clave[1:])}
    return difs in ({1}, {-1})


def validar_clave(datos: dict, fecha_nacimiento: str) -> str:
    clave = _texto(datos, "clave")
    confirmacion = _texto(datos, "confirmacion_clave")
    if not clave:
        raise ErrorValidacion([_err("clave", "CAMPO_OBLIGATORIO", "Crea una clave de 6 dígitos.")])
    if not re.fullmatch(r"\d{6}", clave):
        raise ErrorValidacion([_err("clave", "CLAVE_FORMATO_INVALIDO", "La clave debe tener exactamente 6 dígitos.")])
    if len(set(clave)) == 1 or _es_secuencia(clave):
        raise ErrorValidacion([_err("clave", "CLAVE_INSEGURA",
                                    "Tu clave es fácil de adivinar. Evita dígitos repetidos (111111) o seguidos (123456).")])
    a, m, d = fecha_nacimiento.split("-")
    if clave in {d + m + a[2:], a[2:] + m + d}:
        raise ErrorValidacion([_err("clave", "CLAVE_INSEGURA",
                                    "No uses tu fecha de nacimiento como clave.")])
    if not confirmacion:
        raise ErrorValidacion([_err("confirmacion_clave", "CAMPO_OBLIGATORIO", "Repite tu clave para confirmarla.")])
    if confirmacion != clave:
        raise ErrorValidacion([_err("confirmacion_clave", "CLAVES_NO_COINCIDEN",
                                    "Las claves no coinciden. Escríbelas de nuevo.")])
    return clave


def enmascarar(valor: str | None, visibles: int = 3) -> str | None:
    if not valor:
        return None
    return "*" * (len(valor) - visibles) + valor[-visibles:]
