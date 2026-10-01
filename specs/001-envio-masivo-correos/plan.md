# Implementation Plan: Envío masivo de correos guiado

**Branch**: `001-envio-masivo-correos` | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-envio-masivo-correos/spec.md`

## Summary

App de escritorio para Windows, distribuida como un único `.exe` sin instalación, que guía a una
usuaria no técnica en 7 pasos para enviar correos desde su cuenta Microsoft 365 a una lista de un
Excel: uno por uno (con variables) o todos a la vez (CCO), con preview marcable y con buscador,
verificación de dominios antes de enviar, envío al ritmo que permite Microsoft (30/min), journal
persistente por destinatario (sin pérdidas ni duplicados ante cierres), Excel de fallidos con la
misma estructura que el original y ciclo "corregir y reintentar" sobre ese archivo.

Enfoque técnico: Python 3.13 con un **núcleo sin GUI** (Excel, validación, plantillas, motor,
journal, reporte) detrás de una interfaz `SendProvider` (v1: SMTP AUTH con contraseña); GUI
CustomTkinter + `ttk.Treeview`; SQLite para el journal; PyInstaller onefile compilado en CI
Windows. Decisiones y evidencia en [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13 (gestionado por `uv`; research R8)

**Primary Dependencies**: customtkinter 6.0.0, openpyxl 3.1.5, dnspython 2.8.0, keyring 25.7.0,
platformdirs 4.x; build: PyInstaller 6.22.3; tests: pytest, pytest-cov, aiosmtpd 1.4.6

**Storage**: SQLite (stdlib, WAL) en `%LOCALAPPDATA%\EnvioCorreos\campaigns.db`; credenciales en
Windows Credential Manager vía keyring; borrador y preferencias en JSON en la misma carpeta

**Testing**: pytest (unit, contract contra `aiosmtpd` local, integration del motor con
reanudación); presenters de la GUI sin Tk; recorrido manual del [quickstart](./quickstart.md)

**Target Platform**: Windows 10/11 x64 (desarrollo también en macOS)

**Project Type**: desktop-app (single project)

**Performance Goals**: preview de 5.000 filas < 5 s (SC-007); búsqueda < 0,5 s (SC-010); arranque
< 10 s (SC-006); ritmo de envío limitado por el proveedor, no por la app (research R7.5)

**Constraints**: RSS < 200 MB y estable durante una campaña de 5.000 (SC-011, research R7);
logs ≤ 6 MB; journal ≤ 30 días; sin red solo para enviar; sin permisos de admin

**Scale/Scope**: 1 usuaria por equipo; campañas de decenas a ~5.000 destinatarios
(≤ 10.000/24 h por el límite de Microsoft); 8 pantallas (inicio + 7 pasos)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cómo se cumple | Estado |
|---|---|---|
| I. Usuario no técnico primero | Asistente de 7 pasos ([wizard-ui.md](./contracts/wizard-ui.md)); textos de error en español con acción ([send-provider.md](./contracts/send-provider.md)); confirmación con cantidad, modo y tiempo estimado | ✅ |
| II. Portable, sin instalación | PyInstaller onefile validado en macOS; en Windows lo valida el smoke test del CI (P1); datos en `%LOCALAPPDATA%` | ✅ (validación Windows en P1) |
| III. Ningún fallo silencioso | Journal SQLite con commit por destinatario y estado `SENDING` previo; todo destinatario termina en un estado; "No se sabe si se envió" explícito; aviso de rebotes tardíos | ✅ |
| IV. Seguridad y privacidad | keyring opcional; STARTTLS obligatorio con verificación; CCO por defecto; logs con direcciones enmascaradas y sin texto completo del servidor. Journal con PII → ver Complexity Tracking | ✅ con justificación |
| V. Verificado, no asumido | research.md marca cada hallazgo `[DOC]`/`[BENCH]`/`[NO VERIFICADO]`; los no verificados tienen escenario Q/P que los confirma; tests contra SMTP local | ✅ |
| VI. Observabilidad con track_id | `track_id` de sesión (`S-xxxx`) fuera de campaña y de intento (`C-7F3A-R2`) dentro, inyectado por `logging.Filter`; el de intento está en el Excel y en el resumen; botón "Abrir carpeta de registros" | ✅ |
| VII. Autenticación desacoplada | Motor depende solo de `SendProvider`; límites en `ProviderLimits`/`config.py` | ✅ |
| VIII. Consultar grafo | `graphify update .` ejecutado: el grafo solo contiene tooling de spec-kit (proyecto nuevo, sin código); no hay módulos afectados. Aplica desde la primera tarea de implementación | ✅ (N/A greenfield) |

**Re-check post-diseño (Phase 1)**: sin violaciones nuevas. El diseño agregó verificación de
dominios (FR-026, red saliente DNS) — compatible con II ("sin red salvo para enviar" se interpreta
como: la app funciona sin red y la verificación se omite con aviso).

## Project Structure

### Documentation (this feature)

```text
specs/001-envio-masivo-correos/
├── spec.md
├── plan.md              # este archivo
├── research.md          # Phase 0 (con evidencia)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── send-provider.md
│   ├── failed-report-xlsx.md
│   └── wizard-ui.md
├── bench/               # scripts de los benchmarks de research.md
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
pyproject.toml                 # uv; dependencias fijadas; config de pytest/coverage
src/envio_correos/
├── __main__.py                # entrada: logging, purga, limpieza _MEI, lanza GUI
├── config.py                  # constantes con nombre: límites (R2), rutas, retención, timeouts
├── logging_setup.py           # RotatingFileHandler, track_id de sesión (S-xxxx) y de campaña (C-xxxx-Rn), enmascarado
├── core/                      # SIN imports de tkinter/customtkinter (verificado por test)
│   ├── excel_reader.py        # read_only → RecipientList (tuplas)
│   ├── recipients.py          # RecipientList: validación, duplicados, selección, búsqueda
│   ├── domain_check.py        # MX/A con dnspython, caché por dominio acotada a la lista
│   ├── template.py            # {Columna}, escapes, validación de variables
│   ├── attachments.py         # AttachmentRef (path/size/sha256), carga única por intento
│   ├── message_builder.py     # OutgoingMessage por destinatario/lote
│   ├── engine.py              # CampaignRunner (hilo): ritmo, reintentos, lotes, Detener, eventos
│   ├── journal.py             # SQLite: campaign/attempt/recipient, reanudación, purga, 24 h
│   ├── report.py              # write_only → Excel de fallidos (+ hoja _meta)
│   ├── retry.py               # leer Excel de fallidos → lista de reintento + campaña asociada
│   ├── credentials.py         # keyring (guardar/leer/olvidar)
│   └── providers/
│       ├── base.py            # SendProvider, ProviderLimits, OutgoingMessage, SendOutcome…
│       ├── smtp_errors.py     # tabla de datos SMTP → ReasonCode (contrato)
│       └── m365_smtp.py       # M365SmtpPasswordProvider
├── gui/
│   ├── app.py                 # ventana, navegación del asistente, cola de eventos (after 100 ms)
│   ├── os_open.py             # abrir archivos/carpetas con la app predeterminada (startfile/open)
│   ├── presenters/            # lógica de cada paso, testeable sin Tk
│   ├── steps/                 # vistas: start, account, recipients, message, mode, review, sending, result, retry_wait
│   ├── widgets/recipient_table.py   # Treeview con casillas + detach/reattach
│   └── tutorial/              # textos y capturas del tutorial de conexión
├── texts/es.py                # todos los textos visibles (sin strings sueltos en vistas)
└── devtools/fake_smtp.py      # aiosmtpd con STARTTLS autofirmado para pruebas manuales (no se empaqueta)

tests/
├── unit/                      # recipients, template, report, retry, journal, smtp_errors
├── contract/                  # SendProvider vs aiosmtpd (una prueba por ReasonCode)
├── integration/               # engine end-to-end, reanudación, reintento ida y vuelta
└── fixtures/                  # lista_20.xlsx, lista_5000.xlsx (generada), casos borde

tests/gui/                     # recorridos E2E de la GUI real + chequeo automático de privacidad de logs

packaging/
├── envio_correos.spec         # PyInstaller onefile --windowed, excluye devtools
└── smoke_test.py              # usado por CI (P1)

scripts/perf_campaign.py       # mediciones P2/P3 (para correr en Windows)
docs/guia-usuario.md           # guía para la usuaria final

.github/workflows/build-windows.yml   # tests + build + smoke test + artefacto .exe
```

**Structure Decision**: proyecto único. La frontera `core/` ↔ `gui/` es la que exige el principio V
(núcleo testeable sin GUI) y `core/providers/` la del principio VII. Un test de arquitectura falla
si `core/` importa `tkinter`/`customtkinter`.

## Diseño del motor (resumen; detalle en data-model y contracts)

- **Hilo único de envío** (`CampaignRunner`) → eventos a `queue.Queue` → la GUI los drena con
  `after(100)`. Tk nunca se toca desde el hilo (research R7.7).
- **Ritmo**: `time.monotonic()`; espera `limits.min_interval_s` entre `send()`; `threading.Event`
  para Detener (interrumpe la espera de inmediato).
- **Reintentos**: TRANSIENT → 2 reintentos (30 s, 120 s) sobre el mismo destinatario; si persiste
  → campaña `PAUSED`, el destinatario vuelve a `PENDING`. ACCOUNT → `PAUSED` con mensaje.
  PERMANENT_RECIPIENT → `FAILED` y sigue.
- **Lotes (todos a la vez)**: `max_recipients_per_message`; `TOO_MANY_RECIPIENTS` → divide a la
  mitad y reintenta ese lote.
- **Límite de 24 h**: antes de confirmar, `journal.sent_last_24h(account)`; si la campaña lo
  supera, se avisa cuántos se enviarán hoy; el resto queda `PENDING` y la campaña se pausa al
  llegar al tope.
- **Memoria** (research R7): adjuntos leídos una vez por intento; mensaje armado y descartado por
  envío; sin listas paralelas por destinatario en memoria (el estado vive en el journal).

## Modo desarrollo y TLS (principio IV)

El modo desarrollo (apuntar a `devtools/fake_smtp.py`) se activa **solo** con la variable de entorno
`ENVIO_CORREOS_DEV_SMTP=host:puerto` y **nunca** cuando `sys.frozen` es verdadero (el `.exe` lo
ignora; hay test). El servidor de prueba ofrece STARTTLS con un certificado autofirmado y el modo
dev confía solo en ese certificado concreto (no desactiva la verificación). En producción TLS con
verificación es obligatorio y no configurable.

## Trazabilidad (principio VI)

`track_id` de **sesión** `S-xxxx` desde que se abre la app (probar conexión, cargar Excel,
verificar dominios) y de **campaña** `C-xxxx-Rn` mientras dura un intento; ambos van en cada línea
de log. El de campaña figura además en el Excel de fallidos y en el resumen.

## Riesgos de implementación

| Riesgo | Mitigación |
|---|---|
| Textos reales de 535 distintos a los de Q&A | Tabla de datos `smtp_errors.py` + `AUTH_UNKNOWN` con código; Q1–Q2 |
| Antivirus marca el onefile | Plan B `--onedir` en `.zip` sin cambiar el código (research R8) |
| keyring sin backend en el `.exe` | Smoke test P1 en CI; si falla, `collect_entry_point("keyring.backends")` en el `.spec` |
| Excel abierto/bloqueado por Excel | Mensajes específicos en lectura y escritura (edge cases de la spec) |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Journal guarda valores de filas (PII) en disco (tensión con principio IV) | Generar el Excel de fallidos tras un cierre inesperado y en reintentos aunque el archivo de origen haya cambiado (FR-056, FR-061, FR-063) | Guardar solo ruta + número de fila: si la usuaria edita el Excel (justo el caso de uso de reintento), las filas ya no corresponden y el reporte sale con datos equivocados. Mitigado con retención de 30 días, borrado manual y ubicación en el perfil del usuario |
| Dependencia extra `dnspython` | FR-026: detectar typos de dominio antes de enviar, que el servidor no rechaza en el momento (research R4) | Solo sintaxis: no detecta `empresa.con`, que es el caso de uso que motivó el reintento |
