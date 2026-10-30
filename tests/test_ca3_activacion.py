"""CA-3: al finalizar, la wallet queda activa y el usuario accede al punto de entrada de pagos."""
from tests.conftest import DATOS_VALIDOS


def test_onboarding_completo_activa_la_wallet(completar):
    ob = completar()
    assert ob["estado"] == "COMPLETADO"
    assert ob["wallet"]["estado"] == "ACTIVA"
    assert ob["wallet"]["activada_en"] is not None
    assert ob["puede_pagar"] is True
    assert ob["punto_entrada_pagos"] == f"/api/wallets/{ob['wallet']['id']}/pagos"


def test_wallet_activa_accede_al_punto_de_entrada_de_pagos(client, completar):
    ob = completar()
    r = client.get(ob["punto_entrada_pagos"])
    assert r.status_code == 200
    assert {o["clave"] for o in r.json()["opciones"]} == {"pagar_qr", "transferir_alias"}


def test_wallet_pendiente_no_accede_a_pagos(client, iniciar):
    ob = iniciar()
    assert ob["wallet"]["estado"] == "PENDIENTE"
    assert ob["punto_entrada_pagos"] is None
    r = client.get(f"/api/wallets/{ob['wallet']['id']}/pagos")
    assert r.status_code == 403
    assert r.json()["codigo"] == "WALLET_NO_ACTIVA"


def test_onboarding_terminado_no_acepta_mas_pasos(client, completar):
    ob = completar()
    r = client.post(f"/api/onboardings/{ob['id']}/pasos/clave", json=DATOS_VALIDOS["clave"])
    assert r.status_code == 409
    assert r.json()["codigo"] == "ONBOARDING_CERRADO"


def test_la_clave_no_se_guarda_en_texto_plano(client, completar):
    ob = completar()
    with client.app.state.store.read() as db:
        guardado = db["onboardings"][ob["id"]]["datos"]
    assert "clave" not in guardado
    assert guardado["clave_hash"].startswith("pbkdf2_sha256$")
    assert "482915" not in guardado["clave_hash"]
