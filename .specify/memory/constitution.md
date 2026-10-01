<!--
Sync Impact Report
- Version change: (template sin completar) → 1.0.0
- Principios definidos (nuevos):
  I. El usuario no técnico primero
  II. Portable, sin instalación
  III. Ningún fallo silencioso
  IV. Seguridad y privacidad por defecto
  V. Verificado, no asumido
  VI. Observabilidad con track_id
  VII. Autenticación desacoplada
  VIII. Consultar el grafo de dependencias antes de planificar
- Secciones agregadas: Restricciones técnicas, Flujo de desarrollo, Gobernanza
- Secciones removidas: ninguna
- Templates dependientes: plan-template.md / spec-template.md / tasks-template.md leen
  esta constitución en runtime; no requieren cambios.
- TODOs diferidos: ninguno
-->

# Envío de Correos Constitution

## Core Principles

### I. El usuario no técnico primero

- Toda la interacción MUST ser un flujo guiado paso a paso (asistente), en español, sin jerga
  técnica visible (nada de "SMTP", "puerto", "TLS" en la pantalla principal; si es inevitable,
  va en una sección "Avanzado" con explicación).
- Cada error mostrado MUST decir qué pasó y qué puede hacer el usuario, en lenguaje llano.
  Nunca se muestra un stack trace ni un código crudo sin traducción.
- Las acciones irreversibles (iniciar un envío) MUST pedir confirmación explícita mostrando
  cuántos correos se enviarán y en qué modo.

**Razón**: el usuario final no tiene soporte técnico al lado; si se traba, el producto falló.

### II. Portable, sin instalación

- El entregable MUST ser un ejecutable de Windows que corra con doble clic, sin instalar
  Python, sin permisos de administrador y sin dependencias externas.
- La app MUST funcionar sin conexión a internet salvo para el envío en sí.
- Los archivos generados (configuración, logs, Excel de fallidos) MUST ir a ubicaciones del
  perfil de usuario o a la que el usuario elija, nunca junto al ejecutable si este está en una
  carpeta sin permisos de escritura.

**Razón**: requisito explícito del cliente; el usuario no sabe ni puede instalar software.

### III. Ningún fallo silencioso (NON-NEGOTIABLE)

- Un fallo en un destinatario MUST NOT detener el envío al resto.
- Todo destinatario MUST terminar en exactamente un estado: enviado, fallido (con motivo) u
  omitido (con motivo, p. ej. email inválido o cancelación).
- Los resultados MUST persistirse a disco de forma incremental durante el envío, de modo que un
  cierre inesperado de la app no pierda el registro de qué se envió y qué no.
- La app MUST NOT prometer más de lo que puede detectar: los rebotes asíncronos (que llegan
  después como correo) no son detectables por SMTP y la UI MUST decirlo.

**Razón**: reenviar a quien ya recibió, o creer que llegó algo que no llegó, es el peor resultado
posible para este producto.

### IV. Seguridad y privacidad por defecto

- Las credenciales MUST guardarse solo en el almacén seguro del sistema operativo (Windows
  Credential Manager vía `keyring`) y solo si el usuario lo pide; nunca en texto plano, archivos
  de configuración, logs ni mensajes de error.
- Las conexiones al servidor de correo MUST usar TLS (STARTTLS o SSL implícito) con
  verificación de certificado; nunca se degrada a texto plano.
- En el modo "todos a la vez", los destinatarios MUST ir en copia oculta (CCO) por defecto
  para no exponer las direcciones entre sí.
- Los logs MUST NOT contener contraseñas, contenido del cuerpo ni direcciones completas
  (se enmascaran, p. ej. `ju***@empresa.com`).

**Razón**: la app maneja credenciales corporativas y datos personales (PII) de terceros.

### V. Verificado, no asumido

- Todo comportamiento que dependa de un proveedor externo (límites de envío, métodos de
  autenticación, códigos de error) MUST respaldarse con documentación oficial citada en
  `research.md`, o marcarse explícitamente como "no verificado".
- La lógica de negocio (lectura de Excel, validación, plantillas, motor de envío, reporte)
  MUST vivir en un núcleo sin dependencias de la GUI y tener tests automatizados.
- El envío real MUST probarse contra un servidor SMTP de prueba local en los tests; nunca
  contra destinatarios reales.

**Razón**: el ecosistema de autenticación de Microsoft cambia; suposiciones viejas rompen el
producto en producción.

### VI. Observabilidad con track_id

- Cada campaña de envío MUST tener un `track_id` único que aparezca en todas las líneas de log de
  esa campaña, en el Excel de fallidos y en el resumen final, para correlacionar de punta a punta.
- Se usan niveles explícitos (`INFO`, `WARNING`, `ERROR`) mediante el módulo `logging`; nunca
  `print`. Se loggea solo lo que aporta señal (inicio/fin de campaña, fallos, reintentos).
- El log MUST ser un archivo rotativo local que el usuario pueda adjuntar a un pedido de soporte
  con un botón ("Abrir carpeta de logs").

**Razón**: el soporte será remoto; sin trazabilidad no hay diagnóstico posible.

### VII. Autenticación desacoplada

- El motor de envío MUST depender de una interfaz de "proveedor de envío", no de SMTP con
  contraseña directamente, de modo que agregar OAuth2 (SMTP XOAUTH2 o Microsoft Graph) no
  requiera tocar la GUI, el motor ni el reporte.
- Valores como host, puerto y límites MUST ser configuración/constantes con nombre, no literales
  dispersos en el código.

**Razón**: Microsoft está retirando la autenticación básica de SMTP AUTH en Exchange Online; el
cambio a OAuth es cuestión de tiempo.

### VIII. Consultar el grafo de dependencias antes de planificar

- Antes de planificar un cambio, MUST consultarse el grafo de graphify
  (`graphify explain <nodo>`, `graphify path <A> <B>`) para identificar módulos afectados, y
  verificar lo que indique leyendo los archivos reales.

**Razón**: el grafo es una pista estática; la verificación evita planes basados en supuestos.

## Restricciones técnicas

- Lenguaje: Python 3.12+ (versión exacta a fijar en `plan.md`).
- GUI: toolkit liviano empaquetable (decisión final en `research.md`, candidato CustomTkinter).
- Excel: `openpyxl` (sin `pandas`, para mantener el ejecutable liviano).
- Empaquetado: PyInstaller (o alternativa justificada en `research.md`), compilado en Windows o
  en CI con runner Windows, ya que PyInstaller no hace compilación cruzada.
- Plataforma objetivo: Windows 10 y 11, 64 bits.

## Flujo de desarrollo

- Commits en formato Conventional Commits, validado por hook en el repositorio.
- Todo cambio en el núcleo MUST venir con tests; el gate de tests y CRAP de
  `~/.claude/guardrails` aplica cuando esté configurado para este repo.
- Ningún cambio se da por terminado sin correr la suite completa y, para cambios de GUI, sin
  ejecutar la app y recorrer el flujo afectado.

## Governance

- Esta constitución prevalece sobre cualquier otra práctica del proyecto. Los planes
  (`plan.md`) MUST incluir un "Constitution Check" que verifique cada principio.
- Desviaciones MUST justificarse por escrito en la sección "Complexity Tracking" del plan.
- Enmiendas: se proponen como cambio a este archivo, con Sync Impact Report actualizado y versión
  semántica (MAJOR: se remueve o redefine un principio; MINOR: se agrega uno o se amplía
  materialmente; PATCH: redacción).

**Version**: 1.0.0 | **Ratified**: 2026-09-30 | **Last Amended**: 2026-09-30
