"""Pruebas de las verificaciones SDD (tools/): deben fallar cuando la spec y el código divergen."""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_contrato  # noqa: E402
import check_trazabilidad  # noqa: E402
from spec_ids import CONTRATO, ids_definidos, leer_spec  # noqa: E402

SPEC = leer_spec()


def test_la_spec_define_criterios_reglas_y_requisitos():
    ids = ids_definidos(SPEC)
    assert {f"CA-{n}" for n in range(1, 7)} <= ids
    assert {"RN-1", "RN-12", "RS-1", "RS-7", "RNF-4"} <= ids


def test_trazabilidad_actual_pasa():
    ok, filas, errores = check_trazabilidad.verificar(SPEC)
    assert ok, errores
    assert len(filas) == 6


def test_trazabilidad_falla_si_un_criterio_no_tiene_pruebas():
    spec = SPEC + "\n### CA-7 · Criterio nuevo sin pruebas\n"
    ok, _, errores = check_trazabilidad.verificar(spec)
    assert not ok
    assert "CA-7 no tiene pruebas" in errores


def test_trazabilidad_falla_si_una_prueba_cita_un_criterio_inexistente(tmp_path):
    (tmp_path / "test_x.py").write_text('"""CA-1 y CA-9: algo."""\ndef test_a():\n    pass\n', encoding="utf-8")
    ok, _, errores = check_trazabilidad.verificar(SPEC, tmp_path)
    assert not ok
    assert any("CA-9" in e for e in errores)


def _contrato():
    return yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))


def test_contrato_actual_coincide_con_la_app():
    ok, errores = check_contrato.verificar(_contrato(), SPEC, check_contrato.operaciones_app())
    assert ok, errores


def test_contrato_falla_si_la_app_tiene_una_ruta_no_documentada():
    reales = check_contrato.operaciones_app() | {("DELETE", "/api/onboardings/{}")}
    ok, errores = check_contrato.verificar(_contrato(), SPEC, reales)
    assert not ok
    assert "DELETE /api/onboardings/{} está en la app pero no en el contrato" in errores


def test_contrato_falla_si_cita_un_id_inexistente_o_no_cita_nada():
    contrato = _contrato()
    contrato["paths"]["/api/salud"]["get"]["x-spec"] = ["RN-99"]
    del contrato["paths"]["/api/onboarding/pasos"]["get"]["x-spec"]
    ok, errores = check_contrato.verificar(contrato, SPEC, check_contrato.operaciones_app())
    assert not ok
    assert "GET /api/salud cita RN-99, que no existe en la spec" in errores
    assert "GET /api/onboarding/pasos no declara x-spec" in errores
