# Research: Envío masivo de correos guiado

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Fecha**: 2026-09-30

Convención (constitución, principio V): cada hallazgo indica su **evidencia** — `[DOC]` documentación
oficial leída en esta fecha, `[BENCH]` medición propia reproducible (scripts en la sección final),
`[NO VERIFICADO]` supuesto pendiente de confirmar, con el paso que lo confirmará.

---

## R1. Canal de envío y parámetros de conexión (Microsoft 365)

**Decision**: SMTP client submission (SMTP AUTH) a `smtp.office365.com:587`, STARTTLS obligatorio con
TLS ≥ 1.2 y verificación de certificado; autenticación `AUTH LOGIN` con correo + contraseña (o
contraseña de aplicación), detrás de la interfaz `SendProvider` (ver
[contracts/send-provider.md](./contracts/send-provider.md)).

**Evidencia**:
- `[DOC]` Servidor `smtp.office365.com`, puerto 587 (recomendado), "TLS/StartTLS Enabled (TLS 1.3
  or TLS 1.2)"; no usar IP; el puerto 465 no es compatible. —
  [How to set up a multifunction device or application to send email using Microsoft 365](https://learn.microsoft.com/en-us/exchange/mail-flow-best-practices/how-to-set-up-a-multifunction-device-or-application-to-send-email-using-microsoft-365-or-office-365)
- `[DOC]` Mismo artículo: "Client SMTP submission using Basic authentication in Exchange Online is
  scheduled for deprecation" y "isn't compatible with Security defaults in Microsoft Entra ID".
- `[DOC]` "SMTP AUTH is disabled for organizations created after January 2020 but you can enable it
  per-mailbox"; se habilita por buzón en Microsoft 365 admin center → Users → Active users → Mail →
  Manage email apps → **Authenticated SMTP**, o `Set-CASMailbox -Identity <buzón>
  -SmtpClientAuthenticationDisabled $false`. —
  [Enable or disable SMTP AUTH in Exchange Online](https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/authenticated-client-smtp-submission)
- `[DOC]` Retiro de Basic auth para SMTP AUTH: anunciado para mar–abr 2026, postergado a "2027 o
  más adelante", bloqueando primero tenants nuevos. —
  [Exchange Team Blog](https://techcommunity.microsoft.com/blog/exchange/exchange-online-to-retire-basic-auth-for-client-submission-smtp-auth/4114750),
  [anuncio de postergación](https://techcommunity.microsoft.com/discussions/exchange_general/microsoft-delays-retirement-of-basic-authentication-for-smtp-auth/4490414)
- `[NO VERIFICADO]` Contraseñas de aplicación en M365: según hilos de Microsoft Q&A, solo existen con
  MFA "por usuario" (legacy) habilitado por TI y también dependen de Basic auth
  ([ejemplo](https://learn.microsoft.com/en-us/answers/questions/4734492/will-app-password-with-smtp-auth-still-work-after)).
  Son respuestas de comunidad, no documentación oficial. **Se confirma** en la prueba con la cuenta
  real del cliente (quickstart, escenario Q1).

**Rationale**: decisión del cliente (2026-09-30), aceptando el riesgo R-1 de la spec.

**Alternatives considered**:
- OAuth2 + Microsoft Graph `sendMail` o SMTP XOAUTH2: recomendado por Microsoft y a prueba del retiro;
  requiere registrar la app en Entra ID y posible consentimiento de admin. Rechazado para v1 por
  decisión del cliente; la interfaz `SendProvider` lo deja como un proveedor más (v2).
- High Volume Email (HVE): solo destinatarios internos → no sirve.
- Azure Communication Services Email: requiere suscripción Azure y dominio verificado → fuera del
  alcance de un usuario no técnico.

## R2. Límites de envío y tamaño

**Decision** (todos como constantes configurables en `config.py`, no literales dispersos):

| Constante | Valor por defecto | Evidencia |
|---|---|---|
| `MESSAGES_PER_MINUTE` | 30 → intervalo mínimo entre envíos `2.1 s` (margen 5%) | `[DOC]` "Message rate limit: 30 messages per minute" |
| `RECIPIENTS_PER_24H` | 10.000 (ventana deslizante de 24 h por buzón) | `[DOC]` "Recipient rate limit: 10,000 recipients per day" + nota de ventana de 24 h |
| `MAX_RECIPIENTS_PER_MESSAGE` | 100 (modo "todos a la vez"), con división adaptativa a la mitad si el servidor rechaza por exceso | `[DOC]` "Customizable up to 1000 recipients". El valor por defecto del tenant `[NO VERIFICADO]` → se elige 100, conservador |
| `MAX_MESSAGE_BYTES` | 35 MB (tamaño **codificado**) | `[DOC]` "The default maximum message size for Microsoft mailboxes is 35 MB for sending" |
| `MAX_ATTACHMENTS_RAW_BYTES` | 25 MB (suma de adjuntos sin codificar) | `[BENCH]` un adjunto de 3,00 MB produce un mensaje de 4,11 MB (+37% por base64/MIME) → 35 / 1,37 ≈ 25,5 MB |

Fuente de los `[DOC]`: [Exchange Online limits — Receiving and sending limits](https://learn.microsoft.com/en-us/office365/servicedescriptions/exchange-online-service-description/exchange-online-limits)
(actualizado 2026-09-09). Mismo documento: "Exchange Online isn't suited to accommodate bulk-mailing
scenarios" y existe además un límite por tenant de destinatarios externos (TERRL) que depende de las
licencias → riesgo R-4 de la spec.

**Rationale**: a 30 msg/min, 5.000 correos uno por uno toman ≈ 2 h 50 min; la UI muestra esa
estimación antes de confirmar. El contador de 24 h se calcula desde el journal (R6), sumando
destinatarios enviados por esa cuenta en las últimas 24 h, incluidos los de "todos a la vez".

## R3. Clasificación de errores SMTP

**Decision**: clasificar por clase de respuesta y por códigos conocidos, mapeando cada uno a un
mensaje en español (tabla en [contracts/send-provider.md](./contracts/send-provider.md)):

- `4xx` → **transitorio**: reintentar con backoff (2 reintentos: 30 s, 120 s). Si persiste, el
  destinatario queda **pendiente** (no fallido) y la campaña se pausa.
- `5xx` en `RCPT TO` para un destinatario → **fallido permanente** de ese destinatario, se continúa.
- `535 5.7.139` (autenticación) → error de cuenta; el texto del servidor distingue variantes
  (credenciales incorrectas, SmtpClientAuthentication deshabilitado para buzón/tenant, bloqueado por
  security defaults) — `[NO VERIFICADO]` en docs oficiales; observado en hilos de Microsoft Q&A
  ([1](https://learn.microsoft.com/en-us/answers/questions/308811/535-5-7-139-authentication-unsuccessful-smtpclient),
  [2](https://learn.microsoft.com/en-us/answers/questions/2260193/535-b5-7-139-authentication-unsuccessful-user-is-l)).
  La app clasifica por subcadenas del texto y, si no reconoce, muestra "error de cuenta
  desconocido" + código, para no adivinar. **Se confirma** con la cuenta real (quickstart Q1–Q2).
- `5.7.60` "Client doesn't have permissions to send as this sender" `[DOC]` (artículo R1) → el
  remitente visible no coincide con la cuenta; la app siempre usa la dirección autenticada como
  `From` y solo permite cambiar el **nombre** visible (FR-014).
- Límite diario/ritmo superado: la doc dice que el exceso de ritmo "will be throttled and carried
  over" `[DOC]`; el código exacto de rechazo por cuota diaria `[NO VERIFICADO]` → se trata como
  transitorio que pausa la campaña con mensaje "Se alcanzó el límite de envío de tu cuenta".

## R4. Fallos asíncronos y verificación de dominio

**Decision**: antes de enviar, validar sintaxis y además resolver el registro **MX** (o A/AAAA como
respaldo, RFC 5321 §5.1) de cada **dominio único** con `dnspython`, timeout 3 s por dominio, en un
hilo de fondo para no bloquear la UI. NXDOMAIN o sin MX/A → inválido con motivo. Sin red → se omite
y se avisa (FR-026).

**Evidencia**: `[BENCH]` (bench 5) `empresa.con` → NXDOMAIN en 0,08 s; `gmail.com` → MX en 0,03 s.
`[NO VERIFICADO]` que Exchange Online acepte en `RCPT TO` destinatarios externos inexistentes y los
rebote después; es el comportamiento habitual de un MSA (no verifica buzones remotos antes de
aceptar) pero se confirma en quickstart Q3.

**Rationale**: el caso de uso de reintento del cliente es el typo; los typos de dominio son
detectables antes de enviar a costo casi nulo. Los typos en la parte local (`jaun@empresa.com`) no
son detectables sin leer rebotes → v2 (requiere acceso a la bandeja, ideal con OAuth).

**Alternatives considered**: `email-validator` con `check_deliverability=True` (usa dnspython por
debajo): agrega una dependencia más sin ganar control sobre la caché por dominio ni el timeout
global; se usa validación sintáctica propia y simple + dnspython directo.

## R5. GUI: toolkit y tabla de destinatarios

**Decision**: CustomTkinter 6.0.0 para ventanas, botones, tarjetas y formularios; `ttk.Treeview`
(de la biblioteca estándar) para la tabla de destinatarios, con una columna de casilla (`☑/☐`)
que se alterna con clic/espacio. La búsqueda filtra con `detach`/`reattach` sobre los ítems ya
creados (no se recrean).

**Evidencia**:
- `[DOC]` CustomTkinter 6.0.0 publicado el 2026-06-24 ([PyPI](https://pypi.org/project/customtkinter/)).
  CustomTkinter no incluye un widget de tabla, por eso se usa `ttk.Treeview`.
- `[BENCH]` (bench 2, 5.000 filas × 8 columnas, macOS, Tk 9.0): insertar todas = 0,03 s; filtrar
  = ≤ 0,09 s en el peor caso (todas coinciden), 0,002 s con 111 coincidencias. Cumple SC-010
  (< 0,5 s) con margen amplio. `[NO VERIFICADO]` en Windows → se mide en quickstart P2.

**Alternatives considered**: PySide6/Qt (más pesado, más de 100 MB empaquetado `[NO VERIFICADO]`), web
UI con `pywebview` (depende de WebView2 instalado en el equipo); Tkinter puro (aspecto anticuado
para usuario no técnico).

## R6. Persistencia del estado de campaña (journal) y reintentos

**Decision**: SQLite (biblioteca estándar) en `%LOCALAPPDATA%\EnvioCorreos\campaigns.db`, modo WAL,
**un commit por destinatario procesado**: `pending` → `sending` → `sent | failed | skipped`. Se
marca `sending` y se hace commit *antes* de enviar, y el resultado *después*, para que un cierre
inesperado deje ver qué estaba en vuelo. Al reanudar, un `sending` sin resultado se muestra como
"No se sabe si se envió" y queda **desmarcado** por defecto (evita duplicados, SC-004). Se guardan
los valores originales de cada fila (JSON) para poder generar el Excel de fallidos aunque el archivo
de origen haya cambiado. Retención: 30 días (FR-065), purga al iniciar la app y botón "Borrar
historial".

**Rationale**: un archivo append-only (JSONL) también sería incremental, pero el reintento requiere
consultas ("¿esta dirección ya se envió en esta campaña?", "destinatarios de las últimas 24 h") que
en SQLite son índices y no lecturas completas del archivo en memoria.

**Privacidad**: el journal contiene datos personales que ya estaban en el Excel del usuario, dentro
de su perfil de Windows; se limita a 30 días y se puede borrar. No contiene credenciales ni el
cuerpo renderizado (sí la plantilla, necesaria para el reintento).

**Vínculo reintento ↔ campaña**: el Excel de fallidos lleva la columna "Código de campaña"
(p. ej. `C-7F3A`) y una hoja oculta `_meta` con `campaign_id` y el número de intento. Si la usuaria
borra o renombra la columna o la hoja, la app intenta usar la otra; si no encuentra ninguna, ofrece
redactar el mensaje de nuevo (edge case de la spec).

## R7. Rendimiento y memoria ("no sobrecargar la caché")

**Decisions** (cada una con su evidencia):

1. **Leer el Excel en `read_only=True`** y materializar las filas como **tuplas** (no objetos ni
   dicts por fila). `[BENCH]` (bench 1, 5.000 filas): pico 3,8 MB vs 16,7 MB en modo normal, mismo
   tiempo (1,5 s). `[DOC]` el workbook en read-only "must be explicitly closed" → se cierra en un
   `finally`. Las celdas combinadas, los estilos y las fórmulas no se leen (`data_only=True` toma
   el último valor calculado).
2. **Escribir el reporte en `write_only=True`**. `[DOC]` openpyxl: memoria "< 10 MB" sin importar
   el tamaño; solo `append()`; "can only be saved once". —
   [openpyxl optimized modes](https://openpyxl.readthedocs.io/en/stable/optimized.html)
3. **Índice de búsqueda**: una cadena normalizada por fila (casefold + sin tildes), calculada una
   vez al cargar. `[BENCH]` 0,9 MB y 0,27 s para 5.000 filas. Es la única "caché" de la lista; su
   tamaño es lineal en el tamaño del archivo y se libera al cambiar de archivo (FR-076).
4. **Mensajes**: se arma cada mensaje justo antes de enviarlo y se descarta después; no hay cola de
   mensajes pre-armados. `[BENCH]` (bench 3, 2.000 envíos con adjunto de 3 MB): RSS estable en
   ~51 MB de principio a fin (un pico aislado de 88 MB que volvió a 51) → sin fuga.
5. **Adjuntos**: se leen **una vez por campaña** como bytes crudos (acotado por
   `MAX_ATTACHMENTS_RAW_BYTES` = 25 MB) y se liberan al terminar. Razón principal: **consistencia**
   (si el archivo cambia en disco a mitad de campaña, todos reciben la misma versión). **No** se
   cachea la parte MIME ya codificada: `[BENCH]` (bench 4) lo haría pasar de 240 a 121 ms por
   mensaje, pero el límite de 30 msg/min impone 2.000 ms entre envíos, así que el ahorro no
   cambia el tiempo total y sí sumaría una segunda copia (+37%) en memoria.
6. **Caché de dominios verificados** (R4): dict `dominio → resultado`, acotado por la cantidad de
   dominios únicos de la lista; se libera junto con la lista.
7. **UI ↔ motor**: el motor corre en un hilo y publica eventos en una `queue.Queue`; la UI la vacía
   cada 100 ms con `after()`. Tk no es thread-safe, así que el hilo nunca toca widgets. La cola
   se drena entera en cada tick, así que no acumula (como mucho, un evento por destinatario).
8. **Logs**: `RotatingFileHandler` 1 MB × 5 archivos (≤ 6 MB); journal con purga a 30 días
   (FR-077).

**Objetivo medible para SC-011**: RSS < 200 MB durante una campaña de 5.000 destinatarios con 25 MB
de adjuntos, sin crecimiento sostenido entre el 10% inicial y el final. Margen: el bench 3 dio
~51 MB con 3 MB de adjunto; se suma la tabla Tk y el adjunto máximo. `[NO VERIFICADO]` en Windows →
quickstart P3.

## R8. Empaquetado sin instalación

**Decision**: PyInstaller 6.22.3, modo `--onefile --windowed`, compilado en GitHub Actions con
runner `windows-latest` (PyInstaller no hace compilación cruzada). Datos del usuario en
`%LOCALAPPDATA%\EnvioCorreos` vía `platformdirs`, nunca junto al `.exe`.

**Evidencia**:
- `[DOC]` PyInstaller 6.22.3 (2026-09-12) soporta Python `>=3.8, <3.16`
  ([PyPI](https://pypi.org/project/pyinstaller/)).
- `[DOC]` En onefile el bootloader extrae a una carpeta temporal `_MEIxxxxxx`, "a little slower to
  start", y la carpeta "is not removed if the program crashes or is killed" —
  [PyInstaller operating mode](https://pyinstaller.org/en/stable/operating-mode.html). Mitigación:
  al iniciar, la app borra carpetas `_MEI*` huérfanas propias con más de 1 día de antigüedad.
- **Contradicción resuelta con evidencia**: la doc de CustomTkinter dice que `--onefile` **no**
  funciona ([packaging](https://customtkinter.tomschimansky.com/documentation/packaging)).
  `[BENCH]` (bench 6, macOS): `pyinstaller --onefile` sin `--add-data` produjo un binario de
  12,9 MB que abrió la ventana y terminó OK, porque `pyinstaller-hooks-contrib` ya incluye
  `hook-customtkinter.py`, que recolecta los datos. La doc de CustomTkinter está desactualizada en
  este punto. `[NO VERIFICADO]` en Windows → el CI ejecuta un smoke test del `.exe` (quickstart P1).
- `[DOC]` keyring usa "Windows Credential Locker" como backend en Windows
  ([PyPI](https://pypi.org/project/keyring/)); `pyinstaller-hooks-contrib` tiene hook para keyring
  que recolecta la metadata necesaria para descubrir backends
  ([changelog](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/CHANGELOG.rst)).
  `[NO VERIFICADO]` en el `.exe` de Windows → quickstart P1.
- `[NO VERIFICADO]` Falsos positivos de antivirus con onefile sin firmar: riesgo conocido en la
  comunidad. Plan B, sin cambiar el código: `--onedir` distribuido como `.zip` (sigue siendo "sin
  instalación"). **Activarlo requiere enmendar antes FR-080** ("único archivo ejecutable") con
  acuerdo del cliente.

**Python**: 3.13 (`[BENCH]` 3.13.15 con Tk 9.0 instalado por `uv` — la de Homebrew no trae
`_tkinter`). `aiosmtpd` declara soporte hasta 3.12 en PyPI pero `[BENCH]` funcionó en 3.13.15 en
los bench 3; es solo dependencia de tests.

## R9. Pruebas

**Decision**: `pytest` + `pytest-cov`. El envío se prueba contra `aiosmtpd.controller.Controller`
local (constitución V: nunca destinatarios reales), con un handler programable que rechaza
direcciones concretas (550), devuelve 4xx transitorios o corta la conexión, para cubrir FR-055/056.
La GUI se prueba con tests de "presenter" sin Tk (la lógica de cada paso vive fuera de los widgets)
más el recorrido manual del quickstart.

---

## Benchmarks (reproducibles)

Entorno: macOS (Darwin 25.6), Python 3.13.15 (uv), Tk 9.0, openpyxl 3.1.5, customtkinter 6.0.0,
PyInstaller 6.22.3, aiosmtpd 1.4.6, dnspython 2.8.0. Scripts en [`bench/`](./bench/)
(b1–b4 y `app_ctk.py` para el 6; el 5 fue un snippet de `dns.resolver` con `lifetime=3`), para
repetirlos en Windows.

| # | Qué | Resultado |
|---|---|---|
| 1 | openpyxl 5.000×8, normal vs read-only | 1,57 s / 16,7 MB pico vs 1,51 s / 3,8 MB pico |
| 2 | Treeview 5.000 filas: insertar / filtrar | 0,034 s / ≤ 0,091 s |
| 3 | 2.000 envíos con adjunto de 3 MB a SMTP local, RSS cada 200 | 75, 51, 50, 51, 51, 88, 51, 51, 51, 51 MB |
| 4 | Armar+serializar mensaje con adjunto de 3 MB | releer+codificar 240 ms, parte pre-codificada 121 ms |
| 5 | Resolución MX | `empresa.con` NXDOMAIN 0,08 s; `gmail.com` MX 0,03 s |
| 6 | PyInstaller onefile con CustomTkinter | 12,9 MB, abre y cierra OK (macOS) |

---

## R10. Revisión de seguridad (T089, 2026-09-30)

La skill `/security-review` no pudo ejecutarse (requiere un diff contra `origin/HEAD` y el repo aún
no tiene remoto ni commits); se hizo la revisión manual sobre `src/` y `packaging/`. Cada hallazgo
se **confirmó empíricamente** antes de corregirlo y quedó cubierto por un test.

| # | Hallazgo | Severidad | Evidencia | Corrección | Test |
|---|---|---|---|---|---|
| S1 | Inyección de fórmulas en el Excel de fallidos: openpyxl guarda como fórmula cualquier texto que empiece con `=`; un texto del Excel original (`=HYPERLINK(...)`) volvía activo | Media | Celda leída con `data_type == "f"` | Se fuerza `data_type="s"` (`report._safe`) | `test_textos_que_parecen_formula_quedan_como_texto` |
| S2 | Direcciones completas en tracebacks del log (el filtro solo enmascaraba el mensaje) | Baja (PII local) | Traceback con `juan.perez@empresa.com` | El filtro formatea y enmascara `exc_text`/`stack_info` | `test_enmascara_correos_en_tracebacks` |
| S3 | XML malicioso en `.xlsx` (entidades anidadas): openpyxl solo usa `defusedxml` si está instalado, y no lo estaba | Media (DoS) | `ModuleNotFoundError: defusedxml` | Dependencia `defusedxml` + import forzado en el `.spec` + chequeo en `--smoke` | `test_xml_malicioso_se_rechaza_sin_colgarse` |
| S4 | Asunto con salto de línea (variable con celda multilínea) lanzaba `ValueError` y pausaba toda la campaña (no hay inyección de cabeceras: la biblioteca lo impide) | Baja (robustez) | `ValueError: Header values may not contain linefeed…` | `single_line()` al armar el asunto | `test_asunto_con_saltos_de_linea_queda_en_una_linea` |

Revisado sin hallazgos: TLS obligatorio con verificación y TLS ≥ 1.2 (`m365_smtp`); credenciales
solo en keyring y nunca en `repr`/logs; modo dev ignorado en el ejecutable; consultas SQLite
parametrizadas; plantillas sin `str.format` (no exponen atributos); `subprocess` sin shell; el
servidor de pruebas queda excluido del `.exe`.

## Resultados de validación (T090, 2026-09-30, macOS)

| Escenario | Cómo se validó | Resultado |
|---|---|---|
| A | `uv run pytest` (unit, contract, integration, GUI) | 265 tests en verde |
| B1, B2 | `tests/gui/test_wizard_e2e.py::test_recorrido_completo_uno_por_uno` (GUI real) | OK |
| B3 | `…::test_rechazo_y_dominio_invalido_generan_excel_de_fallidos` | OK |
| B4, B5 | `…::test_corregir_y_reintentar_desde_el_resultado` | OK |
| B6 | `tests/integration/test_resume_kill.py` (proceso matado de verdad) + `tests/gui/test_start_view.py` | OK, 0 duplicados |
| B7 | `tests/unit/test_presenters_us4.py::test_variables_bloquean_todos_a_la_vez` | OK |
| B8 | `tests/unit/test_presenters_us5.py::test_adjuntos_agregar_quitar_y_limite` | OK |
| P1 | `packaging/smoke_test.py` sobre el onefile de macOS | OK (keyring, dns, XML, datos, excel, ventana) |
| P2 | `scripts/perf_campaign.py` | carga 5.000 filas 0,26 s; búsqueda < 1 ms |
| P3 | ídem | 5.000 envíos, RSS 72–78 MB estable |
| P4 | `smoke_test.py` | arranque 4,7 s; 16,7 MB |
| Q1–Q5 | **Pendiente**: requiere cuenta Microsoft 365 de prueba | — |
| P1–P4 en Windows | **Pendiente**: correrá el job `build` del CI | — |
| Usabilidad (SC-001, SC-002) | **Pendiente**: requiere personas | — |
