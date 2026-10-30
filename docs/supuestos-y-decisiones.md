# Supuestos, decisiones y limitaciones

## Alcance elegido

Historia **"Registro y activación del MVP de wallet"**, completa en sus 6 criterios de aceptación:

- CA-1 a CA-4 se **implementan y demuestran** en vivo.
- CA-5 y CA-6 son **metas de negocio** que solo se pueden comprobar después del lanzamiento con usuarios reales. Lo que se entrega es la **instrumentación**: los eventos y el cálculo de la mediana, nuevos activos, gasto y CAC. Se demuestra con datos ficticios.

## Supuestos

| ID | Supuesto | Por qué |
|---|---|---|
| SUP-1 | El onboarding tiene 5 pasos: datos personales, celular con OTP, validación de identidad, términos y clave de pagos. | La historia pide definir el KYC con cumplimiento. Esta es una propuesta mínima a validar con ellos. |
| SUP-2 | El DNI tiene 8 dígitos. El celular tiene 9 dígitos y empieza por 9 (se acepta el prefijo +51). | Formatos habituales en Perú. |
| SUP-3 | La edad mínima es 18 años. | Pendiente de confirmar con cumplimiento. |
| SUP-4 | La clave de pagos tiene 6 dígitos y no puede ser repetida (111111), una secuencia (123456) ni la fecha de nacimiento. | Buenas prácticas habituales para claves numéricas. |
| SUP-5 | Un DNI no puede tener dos wallets activas. | Evita duplicidad de cuentas. |
| SUP-6 | Un "nuevo usuario activo" del mes es una wallet que se activó ese mes. | Es la definición literal del CA-6 ("conteos mensuales de nuevos usuarios activos"). |
| SUP-7 | CAC del mes = gasto de adquisición del mes / nuevos usuarios activos del mes. Si no hay gasto registrado, el CAC queda "sin datos" (no se informa 0). | Definición estándar de CAC. |
| SUP-8 | El usuario declara el canal de adquisición al empezar. En producción vendría de UTM, códigos de referido o la campaña. | Permite atribuir el gasto por canal. |

## Decisiones

| ID | Decisión | Alternativas descartadas |
|---|---|---|
| DEC-1 | **Pregunta abierta de la historia:** la duración del onboarding va de `onboarding_iniciado` (el usuario pulsa "Empezar") a `wallet_activada`. Solo cuentan los onboardings completados. | Medir desde la descarga de la app, que no es observable en este MVP, o incluir los abandonos, que distorsiona la mediana. Los abandonos se miden aparte con la tasa de finalización. |
| DEC-2 | Los pasos se envían en orden. Saltar un paso devuelve `409 PASO_FUERA_DE_ORDEN`. | Permitir saltos complica el estado y la medición por paso. |
| DEC-3 | Un error de validación responde `422` con **todos** los campos inválidos a la vez y un mensaje en lenguaje natural por campo. | Devolver solo el primer error obliga al usuario a varios intentos. |
| DEC-4 | Los intentos fallidos generan el evento `paso_fallido` con el código de error. | Permite ver dónde se traba la gente (sección "errores más frecuentes"). |
| DEC-5 | Los eventos **no contienen datos personales**: solo ids técnicos, canal, paso, códigos y fechas. DNI y celular se muestran enmascarados (`*****912`). | Alineado con la Ley N.° 29733 de Protección de Datos Personales. |
| DEC-6 | La clave se guarda con hash PBKDF2-SHA256 y sal aleatoria, nunca en texto plano. | — |
| DEC-7 | Si la identidad no se valida, la wallet queda `RECHAZADA` y el flujo se cierra con un mensaje que indica qué hacer (ir a una agencia). | Reintentos indefinidos abren la puerta al fraude. |
| DEC-8 | El backend sirve también el frontend: un único servicio para desplegar. | Dos despliegues separados con CORS. |
| DEC-9 | La base de datos es un archivo JSON con escritura atómica. Los datos ficticios de 3 meses viven solo en memoria y se regeneran al arrancar. | Una base de datos real no aporta valor en una demo y complica el despliegue. |

## Integraciones simuladas

| Integración real | Simulación en la demo |
|---|---|
| Envío de OTP por SMS | El código siempre es `123456`. El botón "Enviar código" solo muestra un aviso. |
| Validación de identidad contra el registro nacional | Todos los DNI se aprueban, salvo `99999999`, que se rechaza. |
| Punto de entrada de pagos | Pantalla con "Pagar con QR" y "Transferir a un celular" sin funcionalidad. Los pagos son otra historia del MVP. |
| Herramienta de analítica | Los eventos se guardan en el mismo JSON y la analítica se calcula en el backend. |
| Gasto de adquisición | Se registra manualmente (`POST /api/analitica/gasto`) o viene en los datos ficticios. |

## Limitaciones conocidas

- **No hay autenticación.** Cualquiera que conozca el id de un onboarding puede consultarlo. En producción, el id iría ligado a una sesión del dispositivo.
- **El almacenamiento en JSON** no escala ni soporta varias instancias; es solo para la demo.
- **MAU real:** el CA-6 pide nuevos usuarios activos. El MAU completo, que incluye usuarios recurrentes, necesita los eventos de pago de las otras historias.
- **Sin límite de intentos** de OTP ni de clave (riesgo de fuerza bruta en producción).
- **No hay recuperación** de un onboarding desde otro dispositivo.

## Preguntas pendientes

| ID | Pregunta | Quién responde | Qué bloquea |
|---|---|---|---|
| PREG-1 | ¿Qué datos y documentos exige cumplimiento para el KYC del segmento MVP? | Cumplimiento + Producto | La lista definitiva de pasos (SUP-1) |
| PREG-2 | ¿Se aprueba la definición de duración de DEC-1 como oficial? | Producto + Analítica | La comparación oficial contra la meta de 3 minutos |
| PREG-3 | ¿Qué proveedor de OTP y de validación de identidad se usará? | Tecnología + Partners | Reemplazar las simulaciones |
| PREG-4 | ¿Cuántos intentos fallidos de OTP o de identidad se permiten antes de bloquear? | Seguridad + Cumplimiento | Reglas antifraude |
| PREG-5 | ¿De qué fuente sale el gasto de adquisición por canal? | Marketing + Finanzas | La automatización del cálculo del CAC |
