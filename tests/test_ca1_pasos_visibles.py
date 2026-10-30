"""CA-1: el flujo muestra la secuencia de pasos requeridos y el paso actual en todo momento."""
from tests.conftest import DATOS_VALIDOS


def test_al_iniciar_muestra_los_5_pasos_y_el_primero_es_el_actual(iniciar):
    ob = iniciar()
    assert ob["total_pasos"] == 5
    assert [p["clave"] for p in ob["pasos"]] == list(DATOS_VALIDOS)
    assert ob["paso_actual"]["clave"] == "datos_personales"
    assert [p["estado"] for p in ob["pasos"]] == ["ACTUAL", "PENDIENTE", "PENDIENTE", "PENDIENTE", "PENDIENTE"]
    assert ob["siguiente_accion"].startswith("Paso 1 de 5: Datos personales")


def test_cada_paso_completado_avanza_el_paso_actual(client, iniciar):
    ob = iniciar()
    for n, (paso, datos) in enumerate(list(DATOS_VALIDOS.items())[:-1], start=1):
        ob = client.post(f"/api/onboardings/{ob['id']}/pasos/{paso}", json=datos).json()
        assert ob["pasos_completados"] == n
        assert ob["paso_actual"]["orden"] == n + 1
        estados = [p["estado"] for p in ob["pasos"]]
        assert estados.count("ACTUAL") == 1
        assert estados[:n] == ["COMPLETADO"] * n


def test_retomar_un_onboarding_devuelve_el_paso_donde_quedo(client, iniciar):
    ob = iniciar()
    client.post(f"/api/onboardings/{ob['id']}/pasos/datos_personales", json=DATOS_VALIDOS["datos_personales"])
    retomado = client.get(f"/api/onboardings/{ob['id']}").json()
    assert retomado["paso_actual"]["clave"] == "celular"


def test_no_se_puede_saltar_pasos(client, iniciar):
    ob = iniciar()
    r = client.post(f"/api/onboardings/{ob['id']}/pasos/clave", json=DATOS_VALIDOS["clave"])
    assert r.status_code == 409
    assert r.json()["codigo"] == "PASO_FUERA_DE_ORDEN"
    assert "Datos personales" in r.json()["mensaje"]


def test_catalogo_de_pasos_publico(client):
    pasos = client.get("/api/onboarding/pasos").json()
    assert [p["orden"] for p in pasos] == [1, 2, 3, 4, 5]
