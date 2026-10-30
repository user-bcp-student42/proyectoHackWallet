"""CA-5 y CA-6: mediana de onboarding y reporte mensual de nuevos activos, gasto y CAC.

Las metas (mediana <= 3 min, 1,000-2,000 nuevos activos, CAC <= PEN 10) se verifican
en producción. Aquí se prueba que la salida analítica las calcula correctamente.
"""
from datetime import date

from app import analytics, seed


def test_mediana_se_mide_de_inicio_a_wallet_activada(client, completar):
    for minutos in (1, 2, 3):  # 5 pasos -> 5, 10 y 15 minutos
        completar(dni=f"4000000{minutos}", minutos_por_paso=minutos)
    r = client.get("/api/analitica/onboarding", params={"incluir_demo": False}).json()
    assert r["completados"] == 3
    assert r["mediana_minutos"] == 10.0
    assert r["cumple_objetivo_mediana"] is False


def test_resumen_cuenta_embudo_abandonos_y_tasa(client, completar, iniciar):
    completar(minutos_por_paso=0.5)
    abandonado = iniciar()
    client.post(f"/api/onboardings/{abandonado['id']}/abandonar")
    r = client.get("/api/analitica/onboarding", params={"incluir_demo": False}).json()
    assert (r["iniciados"], r["completados"], r["abandonados"]) == (2, 1, 1)
    assert r["tasa_finalizacion"] == 0.5
    assert r["mediana_minutos"] == 2.5
    assert r["cumple_objetivo_mediana"] is True
    assert r["embudo"][0] == {"paso": "datos_personales", "orden": 1, "completaron": 1}


def test_reporte_mensual_cuenta_nuevos_activos_y_calcula_cac(client, completar):
    completar(canal="redes_sociales", dni="40000001")
    completar(canal="referidos", dni="40000002")
    client.post("/api/analitica/gasto", json={"mes": "2026-10", "canal": "redes_sociales", "monto_pen": 15})
    client.post("/api/analitica/gasto", json={"mes": "2026-10", "canal": "referidos", "monto_pen": 5})

    mes = client.get("/api/analitica/mensual", params={"incluir_demo": False}).json()["meses"][0]
    assert mes["mes"] == "2026-10"
    assert mes["nuevos_usuarios_activos"] == 2
    assert mes["gasto_adquisicion_pen"] == 20.0
    assert mes["cac_pen"] == 10.0
    assert mes["cumple_cac"] is True
    assert mes["cumple_rango_mau"] is False  # 2 usuarios, fuera del rango 1,000-2,000
    canales = {c["canal"]: c for c in mes["por_canal"]}
    assert canales["redes_sociales"]["cac_pen"] == 15.0
    assert canales["referidos"]["cac_pen"] == 5.0


def test_gasto_invalido_se_rechaza(client):
    r = client.post("/api/analitica/gasto", json={"mes": "2026-13", "canal": "tv", "monto_pen": -1})
    assert r.status_code == 422


def test_datos_demo_muestran_la_evolucion_hacia_las_metas():
    eventos, gastos = seed.generar(date(2026, 10, 30))
    meses = analytics.reporte_mensual(eventos, gastos)
    assert [m["mes"] for m in meses] == ["2026-07", "2026-08", "2026-09"]
    ultimo = meses[-1]
    assert ultimo["cumple_mediana"] and ultimo["cumple_cac"] and ultimo["cumple_rango_mau"]
    assert meses[0]["mediana_minutos"] > meses[-1]["mediana_minutos"]
    assert all(e["demo"] for e in eventos)


def test_mediana_de_lista_par_e_impar():
    assert analytics.mediana([1, 3, 2]) == 2
    assert analytics.mediana([1, 2, 3, 10]) == 2.5
    assert analytics.mediana([]) is None


def test_sin_gasto_registrado_el_cac_queda_sin_datos(client, completar):
    completar()
    mes = client.get("/api/analitica/mensual", params={"incluir_demo": False}).json()["meses"][0]
    assert mes["gasto_adquisicion_pen"] == 0
    assert mes["cac_pen"] is None
    assert mes["cumple_cac"] is None
