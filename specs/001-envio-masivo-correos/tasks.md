---

description: "Task list for 001-envio-masivo-correos"
---

# Tasks: Envío masivo de correos guiado

**Input**: Design documents from `/specs/001-envio-masivo-correos/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: SÍ se incluyen. La constitución (principio V) exige tests automatizados para todo el
núcleo y prohíbe probar contra destinatarios reales. Se escriben primero y deben fallar antes de
implementar (rojo → verde).

**Organization**: por historia de usuario (US1…US7 de spec.md), cada una entregable y probable por
separado.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias con tareas incompletas)
- **[Story]**: historia de spec.md a la que pertenece (US1…US7)
- Rutas relativas a la raíz del repo (`src/envio_correos/`, `tests/`, `packaging/`), según plan.md

## Reglas transversales (aplican a TODAS las tareas)

- Ningún literal de límite, ruta, timeout o texto visible fuera de `src/envio_correos/config.py` y
  `src/envio_correos/texts/es.py` (principio VII y regla "no hardcodear").
- `core/` nunca importa `tkinter`/`customtkinter` (lo verifica T012).
- Logs solo vía `logging` con nivel explícito; nunca `print`; nunca contraseñas, cuerpo del mensaje
  ni direcciones completas (principio IV/VI).
- Donde se sacrifique legibilidad por memoria (tuplas, `bytearray`, `array`), comentario que
  explique el porqué y cite research R7.
- Commits en Conventional Commits, uno por tarea o grupo lógico.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: inicializar el proyecto, herramientas y guardarraíles

- [X] T001 Crear `pyproject.toml` con uv: `requires-python = ">=3.13,<3.14"`, dependencias fijadas de plan.md (customtkinter 6.0.0, openpyxl 3.1.5, dnspython 2.8.0, keyring 25.7.0, platformdirs), grupo `dev` (pytest, pytest-cov, aiosmtpd 1.4.6, ruff, pyinstaller 6.22.3), layout `src/`, config de pytest (`testpaths = ["tests"]`) y coverage (`source = ["envio_correos"]`), en pyproject.toml
- [X] T002 Crear el esqueleto de paquetes vacíos (`__init__.py`) según plan.md: `src/envio_correos/{core,core/providers,gui,gui/presenters,gui/steps,gui/widgets,gui/tutorial,texts,devtools}/` y `tests/{unit,contract,integration,fixtures}/`
- [X] T003 [P] Configurar ruff (lint + format, `target-version = "py313"`, regla `T20` para prohibir `print`) en pyproject.toml y crear `.gitignore` (`.venv/`, `build/`, `dist/`, `*.spec.bak`, `__pycache__/`, `graphify-out/cache/`)
- [X] T004 [P] Ejecutar la skill `conventional-commits-init` para instalar el hook versionado en `.githooks/commit-msg`
- [X] T005 [P] Ejecutar la skill `guardrails-init` para crear `.claude/guardrails.json` (pytest + CRAP para Python)
- [X] T006 [P] Crear el generador de fixtures `tests/fixtures/make_fixtures.py` que produce con openpyxl: `lista_20.xlsx`, `lista_5000.xlsx` (8 columnas, con tildes), `varias_hojas.xlsx`, `bordes.xlsx` (filas vacías intercaladas, columnas sin nombre, celdas combinadas, celda con `a@x.com; b@x.com`, duplicados con mayúsculas, espacios, vacíos, `juan@empresa.con`), y una fixture de pytest en `tests/conftest.py` que los genera en `tmp_path_factory`
- [X] T007 [P] Crear `.github/workflows/build-windows.yml` (inicial): jobs en `windows-latest` y `macos-latest` que corren `uv sync` + `uv run ruff check` + `uv run pytest --cov`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: configuración, logging, contrato de envío, proveedor SMTP, journal y esqueleto de GUI que usan todas las historias

**⚠️ CRITICAL**: ninguna historia empieza antes de terminar esta fase

- [X] T008 Implementar `src/envio_correos/config.py`: constantes de research R2 (`MESSAGES_PER_MINUTE=30`, `MIN_INTERVAL_MARGIN=1.05`, `RECIPIENTS_PER_24H=10_000`, `MAX_RECIPIENTS_PER_MESSAGE=100`, `MAX_MESSAGE_BYTES=35*1024**2`, `MAX_ATTACHMENTS_RAW_BYTES=25*1024**2`), SMTP (`SMTP_HOST="smtp.office365.com"`, `SMTP_PORT=587`, `SMTP_TIMEOUT_S`), reintentos (`TRANSIENT_RETRY_DELAYS_S=(30,120)`), DNS (`DNS_TIMEOUT_S=3`), retención (`JOURNAL_RETENTION_DAYS=30`), logs (`LOG_MAX_BYTES=1_000_000`, `LOG_BACKUP_COUNT=5`), UI (`EVENT_POLL_MS=100`, `SEARCH_DEBOUNCE_MS=200`), `APP_NAME="EnvioCorreos"`, y rutas vía `platformdirs` (`data_dir()`, `log_dir()`) creadas de forma perezosa
- [X] T009 [P] Crear `src/envio_correos/texts/es.py` con el diccionario de textos visibles, incluyendo los textos de cada `ReasonCode` de contracts/send-provider.md y de cada `ValidationStatus` de data-model.md
- [X] T010 [P] Escribir tests `tests/unit/test_logging_setup.py`: el filtro agrega a cada registro el `track_id` de sesión (`S-xxxx`, generado al iniciar) o, dentro de `campaign_context`, el de intento (`C-xxxx-Rn`), y lo restaura al salir; el filtro de enmascarado convierte `juan.perez@empresa.com` → `ju***@empresa.com` en mensajes y args; rotación con `LOG_MAX_BYTES`
- [X] T011 Implementar `src/envio_correos/logging_setup.py` (`RotatingFileHandler` en `log_dir()`, `TrackIdFilter` con `contextvars` (sesión por defecto, intento dentro de `campaign_context`), `EmailMaskFilter`, formato con `%(track_id)s`, función `campaign_context(track_id)`) hasta que pase T010
- [X] T012 [P] Escribir test de arquitectura `tests/unit/test_architecture.py` que recorre `src/envio_correos/core/**/*.py` con `ast` y falla si algún módulo importa `tkinter` o `customtkinter`
- [X] T013 Implementar los tipos del contrato en `src/envio_correos/core/providers/base.py`: `SendProvider` (Protocol), `ProviderLimits`, `OutgoingMessage`, `Attachment`, `SendOutcome`, `Failure`, `FailureKind`, `ReasonCode`, `ConnectionResult`, `ProviderError`, exactamente como contracts/send-provider.md
- [X] T014 [P] Crear la infraestructura de tests SMTP en `tests/contract/conftest.py`: fixture que levanta `aiosmtpd.controller.Controller` en `127.0.0.1` con STARTTLS (certificado autofirmado generado en `tmp_path`), AUTH LOGIN con credenciales de prueba y un handler programable por test (rechazar direcciones con 550, responder 4xx, 535 con texto dado, 552, 452, cortar conexión, no ofrecer STARTTLS)
- [X] T015 [P] Escribir tests `tests/unit/test_smtp_errors.py`: cada fila de la tabla de contracts/send-provider.md (código + texto del servidor) mapea al `ReasonCode` y `FailureKind` esperados; texto desconocido → `AUTH_UNKNOWN`/`UNKNOWN` con el código preservado
- [X] T016 Implementar `src/envio_correos/core/providers/smtp_errors.py` como tabla de datos (patrones → `ReasonCode`) + función `classify(code, text, phase)` hasta que pase T015
- [X] T017 Escribir tests de contrato `tests/contract/test_m365_smtp_provider.py`: `test_connection` OK / credenciales malas / SMTP deshabilitado / sin STARTTLS → `TLS_UNAVAILABLE` sin enviar credenciales; `send` con un destinatario rechazado devuelve `SendOutcome.rejected` sin lanzar; `From` siempre = `sender_email`; la contraseña no aparece en `repr()`, excepciones ni logs capturados; el texto completo del servidor no llega a `Failure`
- [X] T018 Implementar `src/envio_correos/core/providers/m365_smtp.py` (`M365SmtpPasswordProvider`: `smtplib.SMTP` + `starttls(context=ssl.create_default_context())`, `open/close/send/test_connection`, armado de `EmailMessage` dentro de `send()` y descartado al salir, parámetro `_test_ssl_context` solo para tests) hasta que pase T017
- [X] T019 [P] Escribir tests `tests/unit/test_journal.py` (SQLite en `tmp_path`): creación de esquema de data-model.md en WAL; crear campaña/intento; transiciones `PENDING→SENDING→SENT|FAILED`, `SENDING→PENDING`; commit visible desde otra conexión tras cada transición; `sent_last_24h(account)` suma destinatarios; `already_sent(campaign_id, address)`; `purge(older_than_days)`; generación de código `C-XXXX` sin colisión
- [X] T020 Implementar `src/envio_correos/core/journal.py` (`Journal` con `sqlite3`, `PRAGMA journal_mode=WAL`, un commit por transición de destinatario, índices de data-model.md) hasta que pase T019
- [X] T021 [P] Escribir tests y luego implementar `src/envio_correos/core/credentials.py` (guardar/leer/olvidar en keyring con servicio `APP_NAME`; en tests usar un backend en memoria vía `keyring.set_keyring`) en `tests/unit/test_credentials.py`
- [X] T022 Implementar el armazón de GUI en `src/envio_correos/gui/app.py` y `src/envio_correos/gui/presenters/base.py`: ventana CTk, indicador de pasos 1–7, navegación Atrás/Siguiente que conserva lo ingresado, registro de pasos, cola `queue.Queue` drenada completa cada `EVENT_POLL_MS` con `after()`, diálogo de error estándar (qué pasó + qué hacer)
- [X] T023 Implementar el punto de entrada `src/envio_correos/__main__.py`: inicializa logging, purga el journal (`JOURNAL_RETENTION_DAYS`), borra carpetas `_MEI*` propias huérfanas de más de 1 día (solo si `sys.frozen`), lanza la GUI; captura excepciones no manejadas y las loggea con `logging.exception`
- [X] T024 [P] Implementar `src/envio_correos/devtools/fake_smtp.py` (servidor aiosmtpd con STARTTLS y certificado autofirmado generado en `data_dir()/dev/`, para pruebas manuales del quickstart B: rechaza `rechazar@…` con 550, responde 4xx a `lento@…`, guarda los mensajes en una carpeta), ejecutable con `python -m envio_correos.devtools.fake_smtp`; y el modo desarrollo en `src/envio_correos/config.py`: solo con `ENVIO_CORREOS_DEV_SMTP=host:puerto`, ignorado si `sys.frozen`, confiando únicamente en ese certificado (sin desactivar la verificación), con test en `tests/unit/test_dev_mode.py` (congelado → ignorado; sin variable → producción)

**Checkpoint**: proveedor SMTP probado contra servidor local, journal funcionando, ventana vacía navegable

---

## Phase 3: User Story 1 - Enviar una campaña uno a uno desde un Excel (Priority: P1) 🎯 MVP

**Goal**: conectar cuenta → cargar Excel con preview marcable y buscador → asunto y cuerpo → "Uno por uno" → confirmar → progreso → resumen.

**Independent Test**: con `lista_20.xlsx` y el fake SMTP, completar el asistente; llegan 20 mensajes con 1 destinatario visible cada uno (quickstart B1, B2).

### Tests for User Story 1 ⚠️ (escribir primero, deben fallar)

- [X] T025 [P] [US1] Tests de lectura en `tests/unit/test_excel_reader.py`: abre en `read_only` y cierra aunque falle; lista hojas y elige la primera con datos; descarta filas totalmente vacías; encabezados vacíos → `"Columna C"`; filas como tuplas; archivo bloqueado/abierto → error específico; `.xls`/`.csv`/protegido → error con ayuda para guardar como `.xlsx`
- [X] T026 [P] [US1] Tests de lista en `tests/unit/test_recipients.py`: autodetección de columna de correo (por encabezado y por contenido); normalización; `DUPLICATE` en la segunda aparición case-insensitive; `MULTIPLE_ADDRESSES` y `EMPTY`; marcado por defecto; las inválidas no se pueden marcar; `effective_count`; búsqueda case-insensitive y sin tildes en cualquier columna; la búsqueda no altera `selected`; marcar/desmarcar visibles respeta el filtro; con `lista_5000.xlsx` el filtrado devuelve en < 0,5 s (SC-010)
- [X] T027 [P] [US1] Tests de dominios en `tests/unit/test_domain_check.py` con resolver simulado: MX ok → válido; NXDOMAIN → `INVALID_DOMAIN`; NoAnswer en MX con A presente → válido; timeout/sin red → verificación omitida con aviso; un solo lookup por dominio único; la caché se libera con la lista
- [X] T028 [P] [US1] Tests de armado en `tests/unit/test_message_builder.py` (modo uno por uno, sin variables): un `OutgoingMessage` por destinatario efectivo, `to` de 1 elemento, `display_name`, asunto y cuerpo tal cual
- [X] T029 [P] [US1] Test de integración del motor en `tests/integration/test_engine_one_by_one.py` contra aiosmtpd: 20 destinatarios, el 3 rechazado → `FAILED` y continúa con el 4; reloj inyectado verifica `min_interval_s` entre envíos sin dormir de verdad; `SENDING` se commitea antes de cada `send`; Detener → pendientes `SKIPPED` "Detenido por el usuario"; 4xx persistente → 2 reintentos y luego `PAUSED` con el destinatario en `PENDING`; error de cuenta → `PAUSED`; al alcanzar `RECIPIENTS_PER_24H` (contando lo enviado en las últimas 24 h del journal) la campaña pasa a `PAUSED` con los restantes `PENDING`; si el servidor corta la conexión a mitad, el motor reconecta y continúa sin perder ni duplicar destinatarios; eventos de progreso emitidos en la cola; logs con `track_id`
- [X] T030 [P] [US1] Tests de presenters sin Tk en `tests/unit/test_presenters_us1.py`: cuenta (no avanza sin conexión OK), destinatarios (no avanza con 0 efectivos; contadores), mensaje (asunto vacío pide confirmación), revisión (texto de confirmación con cantidad, modo y tiempo estimado; aviso si supera el límite de 24 h)

### Implementation for User Story 1

- [X] T031 [P] [US1] Implementar `src/envio_correos/core/excel_reader.py` hasta que pase T025 (comentario R7.1 sobre tuplas y `read_only`)
- [X] T032 [US1] Implementar `src/envio_correos/core/recipients.py` (`RecipientList` con `rows: list[tuple]`, `selected/status: bytearray`, `source_row_numbers: array('I')`, `search_index` perezoso; comentario R7 explicando las estructuras) hasta que pase T026
- [X] T033 [P] [US1] Implementar `src/envio_correos/core/domain_check.py` (`dns.resolver.Resolver` con `lifetime=DNS_TIMEOUT_S`, MX y luego A/AAAA, ejecutado en un hilo que publica progreso) hasta que pase T027
- [X] T034 [P] [US1] Implementar `src/envio_correos/core/message_builder.py` para `ONE_BY_ONE` sin variables hasta que pase T028
- [X] T035 [US1] Implementar `src/envio_correos/core/engine.py` (`CampaignRunner` en `threading.Thread`; ritmo con `time.monotonic` y `threading.Event` para Detener; reintentos según `FailureKind`; journal por destinatario; eventos `Progress/Paused/Finished`; `campaign_context(track_id)` en logs; INFO al inicio/fin, WARNING en reintento, ERROR en fallo de cuenta) hasta que pase T029
- [X] T036 [P] [US1] Implementar el paso Cuenta en `src/envio_correos/gui/presenters/account.py` y `src/envio_correos/gui/steps/account.py` (correo, contraseña, nombre visible, "Probar conexión" en un hilo, error mapeado a texto de es.py; "Avanzado" plegado con servidor y puerto de solo lectura)
- [X] T037 [US1] Implementar la tabla `src/envio_correos/gui/widgets/recipient_table.py` (`ttk.Treeview` con columna de casilla ☑/☐, columna Estado, clic y barra espaciadora alternan, filas no marcables en gris con tooltip del motivo, filtrado por `detach/reattach` sin recrear ítems — research R5)
- [X] T038 [US1] Implementar el paso Destinatarios en `src/envio_correos/gui/presenters/recipients.py` y `src/envio_correos/gui/steps/recipients.py` (selector de archivo `.xlsx`, hoja y columna de correo; buscador con debounce `SEARCH_DEBOUNCE_MS` y botón ✕; "Marcar visibles"/"Desmarcar visibles"; filtros rápidos por estado; pie "Se enviará a N · Válidos · Inválidos · Duplicados · Excluidos"; "Verificando dominios… x/y"; mensaje si no hay resultados) según contracts/wizard-ui.md
- [X] T039 [P] [US1] Implementar el paso Mensaje (versión base) en `src/envio_correos/gui/presenters/message.py` y `src/envio_correos/gui/steps/message.py` (asunto, cuerpo en texto plano, guardado de borrador JSON en `data_dir()` al salir del paso y al cerrar la app — FR-033)
- [X] T040 [P] [US1] Implementar el paso Modo (solo tarjeta "Uno por uno", ninguna preseleccionada) en `src/envio_correos/gui/presenters/mode.py` y `src/envio_correos/gui/steps/mode.py`
- [X] T041 [US1] Implementar el paso Revisión en `src/envio_correos/gui/presenters/review.py` y `src/envio_correos/gui/steps/review.py` (resumen remitente/cantidad/modo, tiempo estimado `N × min_interval_s`, aviso de límite de 24 h con `journal.sent_last_24h`, diálogo de confirmación explícita, creación de campaña e intento en journal insertando todos los destinatarios en una sola transacción con `executemany`)
- [X] T042 [US1] Implementar el paso Envío en `src/envio_correos/gui/presenters/sending.py` y `src/envio_correos/gui/steps/sending.py` (barra, enviados/fallidos/restantes, tiempo restante, botón Detener con confirmación, UI responsiva consumiendo eventos de la cola; Atrás deshabilitado)
- [X] T043 [US1] Implementar el paso Resultado (versión base) en `src/envio_correos/gui/presenters/result.py` y `src/envio_correos/gui/steps/result.py` (enviados/fallidos/omitidos, código de campaña, aviso de rebotes tardíos FR-062, "Abrir carpeta de registros", "Nuevo envío") y pasar T030
- [X] T044 [US1] Conectar todos los pasos en `src/envio_correos/gui/app.py` y recorrer manualmente quickstart B1 y B2 contra `devtools/fake_smtp.py`

**Checkpoint**: MVP funcional de punta a punta contra el SMTP local

---

## Phase 4: User Story 2 - Reporte de fallidos en Excel (Priority: P1)

**Goal**: al terminar, Excel con las filas a corregir, con las columnas originales en el mismo orden + Estado/Motivo/Código y la hoja `_meta`.

**Independent Test**: 6 destinatarios, 2 rechazados → 4 enviados y Excel con exactamente 2 filas (quickstart B3).

### Tests for User Story 2 ⚠️

- [X] T045 [P] [US2] Tests en `tests/unit/test_report.py`: filas incluidas/excluidas según la tabla de data-model.md (excluidos por usuario y duplicados NO); mismos encabezados y orden + `Estado`, `Motivo`, `Código de campaña`; valores originales sin normalizar; hoja `_meta` oculta con `format_version`, `campaign_id`, `attempt`, `email_column`, `generated_at`; encabezado congelado; si el origen ya tenía `Estado/Motivo/Código` se reemplazan; nombre `<original>_fallidos_<AAAAMMDD-HHMM>.xlsx`; sin filas → no genera archivo
- [X] T046 [P] [US2] Test de integración `tests/integration/test_report_roundtrip.py`: campaña contra aiosmtpd con 2 rechazados → reporte con 2 filas; ese reporte cargado con `excel_reader` + `recipients` como campaña nueva ignora las columnas agregadas (no son variables ni columna de correo)

### Implementation for User Story 2

- [X] T047 [US2] Implementar `src/envio_correos/core/report.py` con `Workbook(write_only=True)` (freeze panes configurado antes de `append`, guardado único — research R7.2) leyendo filas desde el journal, hasta que pase T045
- [X] T048 [US2] Hacer que `src/envio_correos/core/recipients.py` reconozca las columnas agregadas por la app (nombres desde config) y las excluya de variables y de la autodetección del correo, hasta que pase T046
- [X] T049 [US2] En `src/envio_correos/gui/steps/result.py` y su presenter: generar el reporte al terminar el intento; si la carpeta no tiene permisos o el archivo está bloqueado → diálogo "Guardar como" con el nombre sugerido; botón "Abrir Excel de fallidos" (`os.startfile` en Windows; en macOS `open` vía helper en `src/envio_correos/gui/os_open.py`); mostrar "No hubo fallos" cuando no se genera
- [X] T050 [US2] Guardar `report_path` en el intento en `src/envio_correos/core/journal.py` y recorrer quickstart B3 (`specs/001-envio-masivo-correos/quickstart.md`)

**Checkpoint**: US1 + US2 funcionan; el Excel de fallidos es reutilizable como fuente

---

## Phase 5: User Story 3 - Reintentar solo los fallidos tras corregirlos (Priority: P1)

**Goal**: "Corregir y reintentar" abre el Excel de fallidos, lo relee tras la corrección manual y envía solo esas filas con el mismo mensaje, adjuntos y modo, sin duplicados.

**Independent Test**: typo `juan@empresa.con` corregido en el Excel de fallidos → reintento envía 1 correo con código `-R2` (quickstart B4, B5).

### Tests for User Story 3 ⚠️

- [X] T051 [P] [US3] Tests en `tests/unit/test_retry.py`: con `_meta` válida → asocia la campaña; sin `_meta` pero con columna `Código de campaña` existente en journal → asocia; ninguna → "campaña nueva"; dirección ya `SENT` en la campaña → `ALREADY_SENT` desmarcada pero marcable; filas agregadas a mano → destinatarios normales; filas borradas → no se envían; número de intento siguiente y código `C-XXXX-R{n}`; adjunto con `sha256` distinto o ausente → aviso
- [X] T052 [P] [US3] Test de integración `tests/integration/test_retry_flow.py`: campaña de 5 con 1 rechazo → reporte → editar la dirección con openpyxl → reintento envía solo 1, mismo asunto/cuerpo/adjuntos, intento 2 en journal, nuevo reporte vacío; repetir con fallo nuevo → intento 3

### Implementation for User Story 3

- [X] T053 [US3] Extender `src/envio_correos/core/journal.py` con `next_attempt(campaign_id)`, `get_campaign(campaign_id)` y consulta de direcciones enviadas por campaña (índice `campaign_id, address, state`)
- [X] T054 [US3] Implementar `src/envio_correos/core/retry.py` (leer Excel de fallidos con `excel_reader`, resolver campaña por `_meta` o columna, construir `RecipientList` con `ALREADY_SENT`, devolver la plantilla de la campaña) hasta que pasen T051 y T052
- [X] T055 [US3] Implementar la pantalla de espera de corrección en `src/envio_correos/gui/presenters/retry_wait.py` y `src/envio_correos/gui/steps/retry_wait.py` ("Corregí el archivo, guardalo y cerralo. Después pulsá Continuar"; si sigue bloqueado: "Cerrá el archivo en Excel para continuar") y el botón "Corregir y reintentar" en `src/envio_correos/gui/steps/result.py`
- [X] T056 [US3] Implementar la pantalla de Inicio en `src/envio_correos/gui/presenters/start.py` y `src/envio_correos/gui/steps/start.py` ("Nuevo envío" · "Reintentar fallidos de una campaña anterior" con selector de archivo) y hacer que el paso Mensaje acepte la plantilla precargada de la campaña (editable) en `src/envio_correos/gui/presenters/message.py`
- [X] T057 [US3] Implementar "Borrar historial" (FR-065): `Journal.delete_all()` / `delete_campaign(id)` con test en `tests/unit/test_journal.py`, botón con confirmación en `src/envio_correos/gui/steps/start.py` y su presenter
- [X] T058 [US3] Recorrer quickstart B4 y B5 (`specs/001-envio-masivo-correos/quickstart.md`) con `src/envio_correos/devtools/fake_smtp.py`

**Checkpoint**: ciclo completo enviar → reporte → corregir → reintentar sin duplicados

---

## Phase 6: User Story 4 - Envío "Todos a la vez" (Priority: P2)

**Goal**: segunda tarjeta del paso Modo; un mismo correo a todos en CCO (o visible con advertencia), en lotes.

**Independent Test**: 3 direcciones de prueba en modo Todos a la vez → cada una lo recibe sin ver a las otras.

### Tests for User Story 4 ⚠️

- [X] T059 [P] [US4] Tests en `tests/unit/test_message_builder.py` (ampliar): `ALL_AT_ONCE_BCC` → `to=(sender,)`, `bcc` = lote; `ALL_AT_ONCE_VISIBLE` → `to` = lote; lotes de `max_recipients_per_message`
- [X] T060 [P] [US4] Tests en `tests/integration/test_engine_all_at_once.py`: 250 destinatarios → 3 lotes; aiosmtpd rechaza 2 direcciones del lote → solo esas `FAILED`; `TOO_MANY_RECIPIENTS` → divide el lote a la mitad y reintenta; el contador de 24 h suma destinatarios, no mensajes
- [X] T061 [P] [US4] Tests de presenter en `tests/unit/test_presenters_us4.py`: con variables en asunto/cuerpo no deja elegir/avanzar en Todos a la vez; la opción visible exige aceptar la advertencia; la confirmación informa cuántos mensajes (lotes) se enviarán

### Implementation for User Story 4

- [X] T062 [US4] Implementar modos `ALL_AT_ONCE_*` y división en lotes en `src/envio_correos/core/message_builder.py` hasta que pase T059
- [X] T063 [US4] Implementar envío por lotes, rechazos parciales y división adaptativa en `src/envio_correos/core/engine.py` hasta que pase T060
- [X] T064 [US4] Agregar la tarjeta "Todos a la vez" (ícono y color distintos, casilla "Mostrar los destinatarios entre sí" con advertencia de privacidad, bloqueo por variables) en `src/envio_correos/gui/steps/mode.py` y `src/envio_correos/gui/presenters/mode.py`, y la cantidad de lotes en la confirmación de `src/envio_correos/gui/presenters/review.py`, hasta que pase T061

**Checkpoint**: ambos modos funcionan y son claramente distinguibles

---

## Phase 7: User Story 5 - Personalizar con variables y adjuntar archivos (Priority: P2)

**Goal**: variables `{Columna}` insertables, adjuntos con límite, vista previa por destinatario y "Enviarme una prueba".

**Independent Test**: `Hola {Nombre}` previsualizado en la fila 2 muestra su nombre; la prueba llega a la propia casilla con adjuntos.

### Tests for User Story 5 ⚠️

- [X] T065 [P] [US5] Tests en `tests/unit/test_template.py`: `{Nombre}` se reemplaza (sin distinguir mayúsculas, sí tildes); `{{`/`}}` literales; variable inexistente → error con su nombre; valores `None`/vacíos → cadena vacía + reporte de filas afectadas; números y fechas de Excel con formato legible
- [X] T066 [P] [US5] Tests en `tests/unit/test_attachments.py`: suma de tamaños vs `MAX_ATTACHMENTS_RAW_BYTES` con mensaje de cuánto reducir; los bytes se leen una sola vez por intento (el archivo puede cambiar en disco y todos reciben la misma versión); `sha256` calculado al agregar
- [X] T067 [P] [US5] Test en `tests/integration/test_engine_attachments_memory.py`: 300 envíos con un adjunto de 3 MB contra aiosmtpd con ritmo desactivado; el RSS (psutil) entre el 10% y el 100% no crece más de un umbral configurado (SC-011, research R7.4)

### Implementation for User Story 5

- [X] T068 [US5] Implementar `src/envio_correos/core/template.py` (parser propio de `{...}` con escapes; sin `str.format` para no exponer atributos) hasta que pase T065
- [X] T069 [US5] Implementar `src/envio_correos/core/attachments.py` (`AttachmentRef` con `path/size/sha256`; `load_for_attempt()` → bytes una vez por intento, liberados al terminar; comentario R7.5 sobre por qué no se cachea la parte MIME) e integrarlo en `src/envio_correos/core/message_builder.py` y `src/envio_correos/core/engine.py` hasta que pasen T066 y T067
- [X] T070 [US5] Ampliar el paso Mensaje en `src/envio_correos/gui/steps/message.py` y su presenter: botones por columna que insertan `{Columna}` en el cursor del campo activo, lista de adjuntos con tamaño y quitar, aviso de límite; incluir las rutas de adjuntos en el borrador (FR-033) y, al restaurarlo, avisar si alguno ya no existe
- [X] T071 [US5] Ampliar Revisión en `src/envio_correos/gui/steps/review.py` y su presenter: vista previa personalizada navegable (anterior/siguiente) por destinatario efectivo, aviso "N filas tienen {Columna} vacía" con opción de verlas, botón "Enviarme una prueba" (primera fila, no cuenta en la campaña)
- [X] T072 [US5] Tests de presenter en `tests/unit/test_presenters_us5.py` (inserción de variable, preview navegable, prueba a sí misma no crea destinatario en journal)

**Checkpoint**: uno por uno personalizado con adjuntos

---

## Phase 8: User Story 6 - Tutorial de conexión de la cuenta (Priority: P2)

**Goal**: diagnóstico de conexión con mensaje distinto por causa, tutorial con capturas y texto copiable para TI; recordar cuenta.

**Independent Test**: provocar credenciales malas, SMTP deshabilitado y sin red → tres mensajes distintos con el paso de tutorial correspondiente.

### Tests for User Story 6 ⚠️

- [X] T073 [P] [US6] Tests en `tests/unit/test_presenters_us6.py`: cada `ReasonCode` de cuenta lleva a su sección del tutorial; "Copiar mensaje para TI" genera un texto que incluye el correo de la cuenta y la indicación de habilitar *Authenticated SMTP* (sin datos sensibles); "Recordar mi cuenta" guarda en keyring y "Olvidar mi cuenta" lo borra

### Implementation for User Story 6

- [X] T074 [P] [US6] (texto hecho; **capturas pendientes**: requieren las pantallas reales de Microsoft, ver quickstart Q1) Redactar el contenido del tutorial en `src/envio_correos/gui/tutorial/content.py` (secciones: qué contraseña usar, contraseña de aplicación — marcada como "si tu organización lo permite" hasta confirmar Q1 —, acceso deshabilitado por la organización, valores de seguridad predeterminados, sin internet, advertencia de Windows al abrir el `.exe`) y el texto para TI basado en research R1; capturas en `src/envio_correos/gui/tutorial/img/`
- [X] T075 [US6] Implementar la vista del tutorial en `src/envio_correos/gui/tutorial/view.py` (paso a paso con imágenes, accesible desde el paso Cuenta y desde cada error) y el botón de copiar al portapapeles
- [X] T076 [US6] Integrar en `src/envio_correos/gui/presenters/account.py` y `src/envio_correos/gui/steps/account.py`: errores con enlace a la sección del tutorial, "Recordar mi cuenta"/"Olvidar mi cuenta" con `core/credentials.py`, carga automática de la cuenta recordada, hasta que pase T073

**Checkpoint**: la usuaria puede desbloquearse sola o con un pedido claro a TI

---

## Phase 9: User Story 7 - Recuperación ante cierre inesperado (Priority: P3)

**Goal**: al reabrir, ofrecer continuar la campaña interrumpida sin reenviar a quien ya recibió.

**Independent Test**: matar la app con 10/20 enviados, reabrir, continuar → solo 10 envíos más, 0 duplicados (quickstart B6).

### Tests for User Story 7 ⚠️

- [X] T077 [P] [US7] Test de integración `tests/integration/test_resume.py`: simular cierre (intento `RUNNING` con 10 `SENT`, 1 `SENDING`, 9 `PENDING` y sin proceso vivo) → al iniciar se marca `INTERRUPTED`; el `SENDING` aparece como "No se sabe si se envió", desmarcado; Continuar envía solo los 9 `PENDING` (aiosmtpd recibe exactamente 9); Descartar → `STOPPED` y el reporte incluye pendientes y el "no se sabe"
- [X] T078 [P] [US7] Test de proceso real `tests/integration/test_resume_kill.py`: lanzar un subproceso con el motor contra aiosmtpd, matarlo con `kill()` a mitad, reanudar en el proceso de test y verificar 0 duplicados (SC-004)

### Implementation for User Story 7

- [X] T079 [US7] Extender `src/envio_correos/core/journal.py` con `find_interrupted()` (intentos `RUNNING` al iniciar → `INTERRUPTED`) y `resume_plan(attempt)`
- [X] T080 [US7] Permitir en `src/envio_correos/core/engine.py` iniciar desde un intento existente (solo `PENDING` y los "no se sabe" que la usuaria marque) hasta que pasen T077 y T078
- [X] T081 [US7] Mostrar en `src/envio_correos/gui/steps/start.py` y su presenter el aviso "Hay un envío sin terminar" con cuántos faltan, "Continuar" (va a Revisión con la lista restante) y "Descartar y generar reporte"; recorrer quickstart B6

**Checkpoint**: todas las historias funcionan de forma independiente

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: empaquetado, CI, rendimiento, seguridad y validación final

- [X] T082 Crear `packaging/envio_correos.spec` (PyInstaller onefile `--windowed`, ícono, excluye `envio_correos.devtools` y `aiosmtpd`, `collect_entry_point("keyring.backends")` si el hook no alcanza, metadata de versión)
- [X] T083 [P] Crear `packaging/smoke_test.py` que ejecuta el `.exe` con un flag `--smoke` (abre ventana, verifica backend de keyring de Windows y escritura en `data_dir()`, cierra con exit 0 en < 10 s) y agregar ese flag en `src/envio_correos/__main__.py`
- [X] T084 Completar `.github/workflows/build-windows.yml`: build con el `.spec` en `windows-latest`, smoke test (quickstart P1), tamaño del `.exe` y tiempo de arranque reportados, artefacto descargable
- [X] T085 [P] (script listo y medido en macOS — ver research.md; **falta correrlo en Windows**) Crear `scripts/perf_campaign.py` para quickstart P2/P3 (5.000 filas: tiempo de carga y filtrado; campaña de 5.000 contra fake SMTP con ritmo desactivado midiendo RSS cada 500) y ejecutarlo en Windows; anotar resultados en `specs/001-envio-masivo-correos/research.md`
- [X] T086 [P] Revisión de accesibilidad: navegación completa con teclado (Tab/Enter/Espacio), fuente ≥ 11 pt y contraste en `src/envio_correos/gui/`
- [X] T087 [P] Guía de usuario en `docs/guia-usuario.md` (abrir el `.exe`, advertencia de SmartScreen, flujo completo con capturas, cómo enviar los registros a soporte)
- [X] T088 Revisión de logs (`src/envio_correos/logging_setup.py` y archivos en `log_dir()`): recorrer una campaña completa y verificar en el archivo de log que no hay contraseñas, cuerpos, direcciones completas ni textos completos del servidor, y que todas las líneas de la campaña tienen `track_id`
- [X] T089 Ejecutar `/security-review` (reporte en español) sobre `src/envio_correos/` y `packaging/`, y corregir hallazgos
- [X] T090 (macOS hecho, ver research.md "Resultados de validación"; **P1–P4 en Windows pendientes del CI**) Ejecutar quickstart A, B1–B8 y P1–P4 (`specs/001-envio-masivo-correos/quickstart.md`); registrar resultados en `specs/001-envio-masivo-correos/research.md`
- [ ] T091 Prueba de usabilidad (SC-001, SC-002) con 3–5 personas no técnicas sobre el `.exe` y el SMTP de prueba: tiempo para completar una campaña de 50 y acierto al distinguir los modos; registrar resultados y ajustes en `specs/001-envio-masivo-correos/research.md`
- [ ] T092 Ejecutar quickstart Q1–Q5 con la cuenta de prueba real de Microsoft 365; actualizar `src/envio_correos/core/providers/smtp_errors.py`, el tutorial y `research.md` (cambiar cada `[NO VERIFICADO]` por la evidencia obtenida)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA todas las historias
- **US1 (Phase 3)**: depende de Foundational — es el MVP
- **US2 (Phase 4)**: depende de US1 (necesita campañas terminadas en el journal y el paso Resultado)
- **US3 (Phase 5)**: depende de US2 (lee el Excel de fallidos)
- **US4 (Phase 6)**: depende de US1 (motor y paso Modo); independiente de US2/US3
- **US5 (Phase 7)**: depende de US1; T064 (bloqueo de variables en US4) usa `template.py` de T068 — si US4 va antes que US5, T064 detecta variables con una regex mínima que T068 reemplaza
- **US6 (Phase 8)**: depende de Foundational y del paso Cuenta (T036); independiente del resto
- **US7 (Phase 9)**: depende de US1 (motor + journal); el reporte de "Descartar" usa US2
- **Polish (Phase 10)**: T082–T084 pueden empezar apenas exista el MVP; T090–T092 al final

### Grafo de historias

```text
Setup → Foundational → US1 ─┬─▶ US2 ─▶ US3
                            ├─▶ US4
                            ├─▶ US5
                            ├─▶ US6 (solo necesita T036)
                            └─▶ US7 (reporte vía US2)
```

### Within Each User Story

- Tests primero (deben fallar) → núcleo (`core/`) → presenters → vistas → recorrido de quickstart
- Una historia se cierra con su checkpoint antes de pasar a la siguiente prioridad

### Parallel Opportunities

- Setup: T003–T007 en paralelo tras T001–T002
- Foundational: T009, T010, T012, T014, T015, T019, T021, T024 en paralelo; luego T011, T016→T018, T020
- Cada historia: todas sus tareas de tests [P] juntas; en US1, T031/T033/T034 y los pasos T036/T039/T040 en paralelo
- Tras US1: US4, US5 y US6 pueden avanzar en paralelo con US2→US3

---

## Parallel Example: User Story 1

```bash
# Tests de US1 en paralelo:
Task: "Tests de lectura en tests/unit/test_excel_reader.py"
Task: "Tests de lista en tests/unit/test_recipients.py"
Task: "Tests de dominios en tests/unit/test_domain_check.py"
Task: "Tests de armado en tests/unit/test_message_builder.py"
Task: "Test de integración del motor en tests/integration/test_engine_one_by_one.py"
Task: "Tests de presenters en tests/unit/test_presenters_us1.py"

# Núcleo de US1 en paralelo (archivos distintos):
Task: "Implementar src/envio_correos/core/excel_reader.py"
Task: "Implementar src/envio_correos/core/domain_check.py"
Task: "Implementar src/envio_correos/core/message_builder.py"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 + Phase 2
2. Phase 3 (US1) → **validar** con quickstart B1/B2 contra el SMTP local
3. Primer build de Windows (T082–T084) para detectar temprano problemas de empaquetado/antivirus/keyring
4. Hacer Q1–Q2 (T092 parcial) con la cuenta real **antes** de invertir en US6, porque los textos reales de error definen el tutorial

### Incremental Delivery

1. MVP (US1) → demo interna
2. US2 + US3 (P1 completos) → **primera entrega al cliente**: enviar, reporte y reintento
3. US4 + US5 → modos y personalización
4. US6 → tutorial con los textos ya confirmados en Q1–Q2
5. US7 → robustez ante cierres
6. Polish → release

---

## Notes

- [P] = archivo distinto y sin dependencias pendientes
- Consultar el grafo antes de cada historia (principio VIII): `graphify update .` y `graphify explain <módulo>` sobre los módulos que toca, verificando lo indicado en los archivos reales
- Commit después de cada tarea o grupo lógico (Conventional Commits)
