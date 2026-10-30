# PLAN-001 · Registro y activación

Plan técnico para [spec.md](spec.md). Describe **cómo** se cumple la spec; si algo aquí contradice la spec, manda la spec.

## Arquitectura

![Arquitectura](../../docs/arquitectura.png)

Detalle de componentes, secuencia y estados en [docs/arquitectura.md](../../docs/arquitectura.md).

| Capa | Archivo | Cubre |
|---|---|---|
| Reglas | `app/domain.py` | RN-1 a RN-8, RN-12, enmascarado (RS-4) |
| Caso de uso | `app/onboarding.py` | CA-1, CA-3, CA-4, RN-9 a RN-11, RS-1, RS-2 |
| Analítica | `app/analytics.py` | CA-5, CA-6 |
| API | `app/main.py` | Contrato HTTP, errores 422/409/403/404 (CA-2, RS-5) |
| Frontend | `frontend/app.js` | Presentación de CA-1 a CA-3, RNF-1, RNF-2 |
| Almacenamiento | `app/store.py` | RNF-3 |

## Contrato

[contracts/openapi.yaml](contracts/openapi.yaml). Cada operación declara en `x-spec` los criterios y reglas que cubre. `tools/check_contrato.py` compara el contrato con las rutas reales de la app.

## Decisiones

| ID | Decisión |
|---|---|
| DEC-1 | Duración del onboarding: de `onboarding_iniciado` a `wallet_activada` (respuesta a la pregunta abierta de la historia). |
| DEC-2 | Pasos en orden estricto (RN-10). |
| DEC-3 | Un 422 devuelve todos los campos inválidos a la vez. |
| DEC-4 | Los intentos fallidos se registran como `paso_fallido`. |
| DEC-5 | Eventos sin datos personales; DNI y celular enmascarados. |
| DEC-6 | Hash PBKDF2-SHA256 con sal aleatoria de 16 bytes y 200,000 iteraciones. |
| DEC-7 | Identidad no validada: wallet RECHAZADA y registro cerrado. |
| DEC-8 | Un solo servicio sirve la API y el frontend. |
| DEC-9 | Almacenamiento en archivo JSON; datos demo solo en memoria. |

Justificación y alternativas en [docs/supuestos-y-decisiones.md](../../docs/supuestos-y-decisiones.md).

## Verificación

| Qué | Cómo | Dónde |
|---|---|---|
| Comportamiento | 45 pruebas pytest, un archivo por criterio, más 7 pruebas de las propias verificaciones | `tests/` |
| Trazabilidad | Cada CA-n de la spec tiene pruebas | `python tools/check_trazabilidad.py` |
| Contrato | Rutas del contrato = rutas de la app, y cada `x-spec` existe en la spec | `python tools/check_contrato.py` |
| Revisión por roles | 6 agentes validadores (Architect, Backend, Frontend, Testing, Security, Chapter) | Proyecto `crew-validacion-sdd` |

Los tres primeros corren en CI en cada push.
