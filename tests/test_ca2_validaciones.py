"""CA-2: datos faltantes o inválidos bloquean el avance con un mensaje accionable."""
import pytest

from tests.conftest import DATOS_VALIDOS


def avanzar_hasta(client, ob_id, paso_destino):
    for paso, datos in DATOS_VALIDOS.items():
        if paso == paso_destino:
            return
        assert client.post(f"/api/onboardings/{ob_id}/pasos/{paso}", json=datos).status_code == 200


def enviar(client, iniciar, paso, cambios=None, quitar=None):
    ob = iniciar()
    avanzar_hasta(client, ob["id"], paso)
    datos = {**DATOS_VALIDOS[paso], **(cambios or {})}
    for campo in quitar or []:
        datos.pop(campo)
    return ob, client.post(f"/api/onboardings/{ob['id']}/pasos/{paso}", json=datos)


CASOS = [
    ("datos_personales", {"dni": "1234"}, None, "dni", "DNI_INVALIDO"),
    ("datos_personales", {"dni": "4567891A"}, None, "dni", "DNI_INVALIDO"),
    ("datos_personales", None, ["dni"], "dni", "CAMPO_OBLIGATORIO"),
    ("datos_personales", {"nombres": "R2D2"}, None, "nombres", "NOMBRE_INVALIDO"),
    ("datos_personales", None, ["apellidos"], "apellidos", "CAMPO_OBLIGATORIO"),
    ("datos_personales", {"fecha_nacimiento": "2012-01-01"}, None, "fecha_nacimiento", "MENOR_DE_EDAD"),
    ("datos_personales", {"fecha_nacimiento": "12/04/1995"}, None, "fecha_nacimiento", "FECHA_INVALIDA"),
    ("celular", {"celular": "812345678"}, None, "celular", "CELULAR_INVALIDO"),
    ("celular", {"codigo_otp": "000000"}, None, "codigo_otp", "OTP_INCORRECTO"),
    ("celular", None, ["codigo_otp"], "codigo_otp", "CAMPO_OBLIGATORIO"),
    ("identidad", {"autoriza_validacion": False}, None, "autoriza_validacion", "AUTORIZACION_REQUERIDA"),
    ("terminos", {"acepta_terminos": False}, None, "acepta_terminos", "TERMINOS_REQUERIDOS"),
    ("terminos", None, ["acepta_tratamiento_datos"], "acepta_tratamiento_datos", "TRATAMIENTO_DATOS_REQUERIDO"),
    ("clave", {"clave": "123456", "confirmacion_clave": "123456"}, None, "clave", "CLAVE_INSEGURA"),
    ("clave", {"clave": "777777", "confirmacion_clave": "777777"}, None, "clave", "CLAVE_INSEGURA"),
    ("clave", {"clave": "120495", "confirmacion_clave": "120495"}, None, "clave", "CLAVE_INSEGURA"),
    ("clave", {"clave": "48291"}, None, "clave", "CLAVE_FORMATO_INVALIDO"),
    ("clave", {"confirmacion_clave": "482916"}, None, "confirmacion_clave", "CLAVES_NO_COINCIDEN"),
]


@pytest.mark.parametrize("paso,cambios,quitar,campo,codigo", CASOS)
def test_dato_invalido_bloquea_y_explica_como_corregir(client, iniciar, paso, cambios, quitar, campo, codigo):
    ob, r = enviar(client, iniciar, paso, cambios, quitar)

    assert r.status_code == 422
    cuerpo = r.json()
    error = next(e for e in cuerpo["errores"] if e["campo"] == campo)
    assert error["codigo"] == codigo
    assert len(error["mensaje"]) > 15  # mensaje en lenguaje natural, no solo un código

    # El avance queda bloqueado: seguimos en el mismo paso.
    estado = client.get(f"/api/onboardings/{ob['id']}").json()
    assert estado["paso_actual"]["clave"] == paso


def test_reporta_todos_los_campos_con_error_a_la_vez(client, iniciar):
    ob = iniciar()
    r = client.post(f"/api/onboardings/{ob['id']}/pasos/datos_personales", json={})
    campos = {e["campo"] for e in r.json()["errores"]}
    assert campos == {"dni", "nombres", "apellidos", "fecha_nacimiento"}


def test_tras_corregir_el_dato_el_flujo_avanza(client, iniciar):
    ob, r = enviar(client, iniciar, "datos_personales", {"dni": "1234"})
    assert r.status_code == 422
    r = client.post(f"/api/onboardings/{ob['id']}/pasos/datos_personales", json=DATOS_VALIDOS["datos_personales"])
    assert r.status_code == 200
    assert r.json()["paso_actual"]["clave"] == "celular"


def test_celular_acepta_prefijo_peruano_y_espacios(client, iniciar):
    _, r = enviar(client, iniciar, "celular", {"celular": "+51 987 654 321"})
    assert r.status_code == 200
    assert r.json()["resumen_datos"]["celular"] == "******321"


def test_dni_con_wallet_activa_no_puede_registrarse_otra_vez(client, completar, iniciar):
    completar(dni="45678912")
    _, r = enviar(client, iniciar, "datos_personales")
    assert r.status_code == 422
    assert r.json()["errores"][0]["codigo"] == "DNI_YA_REGISTRADO"


def test_identidad_no_validada_cierra_el_flujo_con_wallet_rechazada(client, iniciar):
    ob = iniciar()
    datos = {**DATOS_VALIDOS["datos_personales"], "dni": "99999999"}
    client.post(f"/api/onboardings/{ob['id']}/pasos/datos_personales", json=datos)
    client.post(f"/api/onboardings/{ob['id']}/pasos/celular", json=DATOS_VALIDOS["celular"])
    r = client.post(f"/api/onboardings/{ob['id']}/pasos/identidad", json=DATOS_VALIDOS["identidad"])
    cuerpo = r.json()
    assert r.status_code == 200
    assert cuerpo["estado"] == "RECHAZADO"
    assert cuerpo["wallet"]["estado"] == "RECHAZADA"
    assert cuerpo["puede_pagar"] is False
    assert "agencia" in cuerpo["siguiente_accion"]
