# Trazabilidad: criterio → implementación → prueba

| CA | Criterio | Implementación | Pruebas | Cómo verlo en la demo |
|---|---|---|---|---|
| CA-1 | El flujo muestra la secuencia de pasos requeridos y el paso actual en todo momento. | `OnboardingService._vista` devuelve `pasos[]` (con estado `COMPLETADO`, `ACTUAL` o `PENDIENTE`), `paso_actual` y `siguiente_accion`. El frontend dibuja la barra de progreso y los 5 pasos. | `test_ca1_pasos_visibles.py` (5 pruebas) | "Paso 2 de 5" y los círculos de pasos en cada pantalla. Al recargar, se retoma el mismo paso. |
| CA-2 | Si falta información obligatoria o hay datos inválidos, el flujo bloquea el avance y muestra un mensaje accionable. | `domain.validar_*` devuelve `ErrorValidacion` con campo, código y mensaje. La API responde `422`. El frontend marca cada campo y muestra el mensaje. | `test_ca2_validaciones.py` (23 pruebas: 18 casos parametrizados + 5) | Enviar el DNI `1234`, el OTP `000000` o la clave `123456`. |
| CA-3 | Al finalizar, la wallet pasa a activa y el usuario accede al punto de entrada de pagos. | Al completar el paso 5: `wallet.estado = ACTIVA` y `punto_entrada_pagos`. `GET /api/wallets/{id}/pagos` responde `403` si la wallet no está activa. | `test_ca3_activacion.py` (5 pruebas) | Pantalla "¡Tu wallet está activa!" y luego "Ir a pagar". Antes de terminar, la pestaña Pagos aparece bloqueada. |
| CA-4 | Se registran eventos de inicio, finalización de cada paso y cierre del flujo. | Eventos `onboarding_iniciado`, `paso_completado`, `paso_fallido`, `wallet_activada` y `onboarding_cerrado` (con `resultado` y `duracion_segundos`). Sin datos personales. | `test_ca4_eventos.py` (5 pruebas) | Analítica → "Últimos eventos reales". |
| CA-5 | La mediana de finalización baja de 8 a 3 minutos (meta de negocio). | `analytics.resumen` calcula la mediana de `onboarding_iniciado` a `wallet_activada` y la compara contra la meta. | `test_ca5_ca6_analitica.py` | Tarjeta "Mediana de onboarding" y columna "Mediana ≤ 3" por mes. En los datos ficticios baja de 5.6 a 2.8 min. |
| CA-6 | Conteo mensual de nuevos usuarios activos y atribución del gasto para verificar MAU 1,000–2,000 y CAC PEN 10. | `analytics.reporte_mensual` calcula nuevos activos, gasto, CAC y desglose por canal. `POST /api/analitica/gasto` registra el gasto. | `test_ca5_ca6_analitica.py` (7 pruebas en total con CA-5) | Tabla "Reporte mensual (CA-6)". |

**Total:** 52 pruebas automatizadas (`python -m pytest -v`): 45 de comportamiento, por criterio, y 7 de las verificaciones SDD (`tests/test_herramientas_sdd.py`).

Esta matriz se comprueba automáticamente con `python tools/check_trazabilidad.py`, que lee los criterios de [la spec](../specs/001-registro-activacion/spec.md).

Además se hizo una verificación manual de punta a punta en el navegador (Chromium, viewport de celular 390 px): un registro completo con errores intencionales en DNI, términos y clave, recarga a mitad del flujo, activación, acceso a pagos y analítica. Sin errores de JavaScript. Las capturas están en `docs/capturas/`.
