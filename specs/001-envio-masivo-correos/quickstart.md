# Quickstart: validación de punta a punta

Guía para comprobar que la feature funciona. No contiene implementación; referencia
[contracts/](./contracts/) y [data-model.md](./data-model.md).

## Prerrequisitos
- Desarrollo: macOS o Windows con `uv`; `uv sync` instala Python 3.13 gestionado (incluye Tk).
- Build: GitHub Actions `windows-latest` (o un Windows 10/11 con `uv`).
- Pruebas con cuenta real (Q): un buzón Microsoft 365 **de prueba** con *Authenticated SMTP*
  habilitado por TI, y 3–5 direcciones propias como destinatarios. Nunca destinatarios reales.

## A. Tests automatizados (cada cambio)
```bash
uv run pytest                       # unit + contract + integration (aiosmtpd local)
uv run pytest --cov=envio_correos   # cobertura del núcleo
```
Esperado: todo verde. Cubre la tabla de motivos de `send-provider.md`, la selección/búsqueda de
`RecipientList`, el formato de `failed-report-xlsx.md` (ida y vuelta: generar → releer como
reintento) y la reanudación tras matar el hilo de envío a mitad.

## B. Escenarios manuales con SMTP local (sin cuenta real)
Levantar el servidor de prueba incluido (`uv run python -m envio_correos.devtools.fake_smtp`,
rechaza `rechazar@…` con 550 y simula 4xx para `lento@…`) y apuntar la app en modo desarrollo.

| # | Escenario | Esperado |
|---|---|---|
| B1 | US1 completo con `fixtures/lista_20.xlsx`, modo Uno por uno | 20 mensajes en el servidor de prueba, 1 destinatario visible cada uno |
| B2 | Desmarcar 3 filas, buscar "bogota", desmarcar 1 más, limpiar búsqueda | "Se enviará a 16"; las 4 siguen desmarcadas; no aparecen en el Excel de fallidos |
| B3 | Lista con `rechazar@ejemplo.com` y `juan@empresa.con` | `empresa.con` marcado inválido en la preview; `rechazar@…` falla al enviar; Excel de fallidos con 2 filas y columnas originales + Estado/Motivo/Código |
| B4 | Corregir ambos en el Excel de fallidos → Corregir y reintentar | Solo 2 envíos, mismo asunto/cuerpo/adjuntos, código `-R2` |
| B5 | Agregar al Excel de fallidos una fila con una dirección ya enviada | Aparece como "Ya enviado", desmarcada |
| B6 | Matar el proceso con 10/20 enviados y reabrir | "Hay un envío sin terminar"; Continuar envía solo los pendientes; 0 duplicados |
| B7 | Modo Todos a la vez con `{Nombre}` en el cuerpo | No deja avanzar, explica por qué |
| B8 | Adjuntos > 25 MB | No deja avanzar, indica cuánto reducir |

## P. Rendimiento (Windows, en el `.exe`)
| # | Medición | Objetivo |
|---|---|---|
| P1 | Smoke test en CI: el `.exe` abre, carga keyring (backend Windows), cierra | Exit 0 |
| P2 | `bench/b2_tree.py` equivalente con 5.000 filas en la app | Filtrar < 0,5 s (SC-010) |
| P3 | Campaña de 5.000 al servidor local con ritmo desactivado (modo dev), RSS cada 500 | < 200 MB y sin crecimiento sostenido (SC-011) |
| P4 | Tiempo de arranque del `.exe` onefile en un equipo de oficina | < 10 s (SC-006) |

## Q. Con cuenta real de Microsoft 365 (antes del release; confirma los `[NO VERIFICADO]`)
| # | Escenario | Qué confirma |
|---|---|---|
| Q1 | Probar conexión con contraseña correcta, incorrecta y (si aplica) contraseña de aplicación | Texto real de los 535 y si las contraseñas de aplicación funcionan (research R1, R3) |
| Q2 | Probar con un buzón sin Authenticated SMTP | Texto real de 5.7.139 "disabled" → `AUTH_SMTP_DISABLED` |
| Q3 | Enviar a `noexiste-xyz@gmail.com` y a un dominio interno inexistente | Si el rechazo es inmediato o rebote asíncrono (research R4) |
| Q4 | Todos a la vez con 150 destinatarios propios/alias | División en lotes de 100 y entrega en CCO |
| Q5 | 40 envíos seguidos | Que el ritmo de 2,1 s no dispare throttling |

Resultado de Q1–Q5 se anota en `research.md` (se cambia `[NO VERIFICADO]` por la evidencia).
