"""CA-4: se registran los eventos de inicio, finalización de cada paso y cierre del flujo."""
import json

from tests.conftest import DATOS_VALIDOS


def tipos(client, ob_id):
    return [(e["tipo"], e.get("paso"), e.get("resultado"))
            for e in client.get(f"/api/onboardings/{ob_id}/eventos").json()]


def test_flujo_exitoso_registra_inicio_cada_paso_y_cierre(client, completar):
    ob = completar()
    assert tipos(client, ob["id"]) == [
        ("onboarding_iniciado", None, None),
        ("paso_completado", "datos_personales", None),
        ("paso_completado", "celular", None),
        ("paso_completado", "identidad", None),
        ("paso_completado", "terminos", None),
        ("paso_completado", "clave", None),
        ("wallet_activada", None, None),
        ("onboarding_cerrado", None, "COMPLETADO"),
    ]


def test_abandono_registra_cierre_con_ultimo_paso(client, iniciar):
    ob = iniciar()
    client.post(f"/api/onboardings/{ob['id']}/pasos/datos_personales", json=DATOS_VALIDOS["datos_personales"])
    r = client.post(f"/api/onboardings/{ob['id']}/abandonar")
    assert r.json()["estado"] == "ABANDONADO"
    cierre = client.get(f"/api/onboardings/{ob['id']}/eventos").json()[-1]
    assert cierre["tipo"] == "onboarding_cerrado"
    assert cierre["resultado"] == "ABANDONADO"
    assert cierre["ultimo_paso"] == "celular"


def test_intento_fallido_registra_evento_con_codigo_de_error(client, iniciar):
    ob = iniciar()
    client.post(f"/api/onboardings/{ob['id']}/pasos/datos_personales", json={"dni": "12"})
    fallido = client.get(f"/api/onboardings/{ob['id']}/eventos").json()[-1]
    assert fallido["tipo"] == "paso_fallido"
    assert fallido["paso"] == "datos_personales"
    assert fallido["codigo_error"] in {"DNI_INVALIDO", "CAMPO_OBLIGATORIO"}


def test_eventos_tienen_fecha_canal_y_no_exponen_datos_personales(client, completar):
    ob = completar(canal="referidos")
    eventos = client.get(f"/api/onboardings/{ob['id']}/eventos").json()
    texto = json.dumps(eventos)
    for dato in ("45678912", "987654321", "Rosa", "Quispe", "482915"):
        assert dato not in texto
    assert all(e["canal"] == "referidos" and e["ocurrido_en"] for e in eventos)


def test_eventos_se_persisten_en_el_archivo_json(tmp_path, reloj):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.store import JsonStore

    ruta = tmp_path / "db.json"
    c = TestClient(create_app(store=JsonStore(str(ruta)), reloj=reloj, cargar_demo=False))
    ob = c.post("/api/onboardings", json={}).json()

    recargado = JsonStore(str(ruta))
    with recargado.read() as db:
        assert ob["id"] in db["onboardings"]
        assert db["eventos"][0]["tipo"] == "onboarding_iniciado"
