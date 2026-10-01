# Feature Specification: Envío masivo de correos guiado

**Feature Branch**: `001-envio-masivo-correos`

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: "Software para automatizar el envío de correos, usado por un usuario no
técnico. Guiar el proceso para definir remitente, asunto, cuerpo y demás. Iniciar sesión con el
correo o tutorial de contraseña de terceros. Lista de destinatarios desde Excel con preview. Opción
claramente distinguible entre envío 1 a 1 o a todos al mismo tiempo. Si algún destinatario falla,
continuar y generar un Excel similar al de origen con los fallidos. Interfaz ligera que funcione sin
instalación."

**Decisiones ya tomadas con el cliente** (2026-09-30):

- Plataforma: solo Windows.
- Proveedor: Outlook corporativo (Microsoft 365).
- Autenticación v1: correo + contraseña (o contraseña de aplicación) sobre el servidor de envío de
  Microsoft 365, con tutorial. El cliente aceptó el riesgo documentado en *Riesgos*.
- Cuerpo: texto con variables tomadas de columnas del Excel, y adjuntos. Sin formato enriquecido
  en v1.
- (Ronda 2) Reintento de fallidos tras corrección manual del archivo; desmarcar destinatarios en la
  preview; buscador por texto en la preview; uso de memoria acotado (no sobrecargar caché).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enviar una campaña uno a uno desde un Excel (Priority: P1)

La usuaria abre la aplicación, conecta su cuenta de correo corporativa, carga el Excel con los
destinatarios, revisa la lista, escribe asunto y cuerpo, elige "Uno por uno", confirma y ve cómo
avanza el envío hasta un resumen final.

**Why this priority**: es el flujo completo de punta a punta; sin él no hay producto.

**Independent Test**: con una cuenta de prueba y un Excel de 5 filas, completar el asistente y
verificar que llegan 5 correos individuales, cada uno con un único destinatario visible.

**Acceptance Scenarios**:

1. **Given** la app recién abierta, **When** la usuaria ingresa su correo y contraseña válidos y
   pulsa "Probar conexión", **Then** ve un mensaje de éxito y puede avanzar al siguiente paso.
2. **Given** un Excel con una columna de correos, **When** lo selecciona, **Then** ve una tabla
   con las filas del archivo, la columna de correo detectada (o la elige ella) y un contador de
   destinatarios válidos, inválidos y duplicados.
3. **Given** la preview de destinatarios, **When** desmarca la casilla de una o varias filas,
   **Then** esas filas no recibirán el correo, el contador "Se enviará a N" se actualiza al
   instante y en el resumen final se cuentan como "Excluido por el usuario" (no van al Excel
   de fallidos, FR-061).
4. **Given** la preview, **When** escribe un texto en el buscador (p. ej. parte de un nombre o
   correo), **Then** la tabla muestra solo las filas que contienen ese texto en cualquier columna,
   sin distinguir mayúsculas ni tildes, y puede marcar/desmarcar sobre ese resultado.
5. **Given** asunto y cuerpo escritos y el modo "Uno por uno" elegido, **When** pulsa "Enviar",
   **Then** ve una confirmación con la cantidad exacta de correos y el modo, y solo tras aceptar
   comienza el envío.
6. **Given** un envío en curso, **When** avanza, **Then** ve una barra de progreso con enviados,
   fallidos y restantes, y un botón para detener.
7. **Given** el envío terminado, **When** ve el resumen, **Then** ve cuántos se enviaron, cuántos
   fallaron, cuántos se omitieron y un código de referencia de la campaña.

---

### User Story 2 - Reporte de fallidos en Excel (Priority: P1)

Si algún destinatario falla, el envío continúa con el resto y, al final, se genera un Excel con la
misma estructura que el original, que contiene solo las filas a corregir (fallidas al enviar,
inválidas y pendientes; ver FR-061) y columnas adicionales con el estado y el motivo en lenguaje
claro.

**Why this priority**: requisito explícito; permite corregir y reintentar solo los fallidos.

**Independent Test**: enviar a un Excel donde 2 de 6 direcciones son rechazadas por el servidor y
verificar que 4 se envían y el Excel de fallidos tiene exactamente 2 filas con todas sus columnas
originales más el motivo.

**Acceptance Scenarios**:

1. **Given** una lista donde el destinatario 3 es rechazado, **When** el envío llega a él,
   **Then** se registra como fallido y el envío continúa con el destinatario 4.
2. **Given** un envío terminado con fallos, **When** se muestra el resumen, **Then** hay un botón
   "Abrir Excel de fallidos" y el archivo tiene las mismas columnas y el mismo orden de columnas que
   el original, más "Estado", "Motivo" y "Código de campaña".
3. **Given** el Excel de fallidos, **When** la usuaria lo carga como fuente de una nueva campaña,
   **Then** la app lo acepta sin pasos extra (las columnas agregadas por la app se ignoran como
   datos del destinatario).
4. **Given** un envío sin fallos, **When** termina, **Then** no se genera Excel de fallidos y el
   resumen lo indica.

---

### User Story 3 - Reintentar solo los fallidos tras corregirlos (Priority: P1)

Al terminar una campaña con fallidos, la usuaria pulsa "Corregir y reintentar". La app abre el Excel
de fallidos; ella corrige a mano los correos con error (p. ej. un typo), guarda y vuelve a la app,
que relee el archivo y le muestra la preview solo con esas filas. Al confirmar, se envía solo a
ellas, con el mismo mensaje, adjuntos y modo de la campaña original, sin tener que redactar de nuevo.
También puede retomar este reintento otro día desde la pantalla de inicio ("Reintentar fallidos de
una campaña anterior") eligiendo el Excel de fallidos.

**Why this priority**: sin reintento, la usuaria tendría que rehacer la campaña entera o arriesgarse
a reenviar a quien ya recibió.

**Independent Test**: campaña de 5 destinatarios con 1 typo (`juan@empresa.con`); corregirlo en el
Excel de fallidos, reintentar y verificar que solo se envía 1 correo, a la dirección corregida, con
el mismo asunto, cuerpo y adjuntos.

**Acceptance Scenarios**:

1. **Given** una campaña terminada con fallidos, **When** pulsa "Corregir y reintentar", **Then** se
   abre el Excel de fallidos en su programa de hojas de cálculo y la app espera con un mensaje
   "Corregí el archivo, guardalo y pulsá Continuar".
2. **Given** el archivo corregido y guardado, **When** pulsa "Continuar", **Then** la app lo relee,
   vuelve a validar las direcciones y muestra la preview (con casillas y buscador) solo con esas
   filas, ya con el mensaje de la campaña original precargado.
3. **Given** una fila del reintento cuya dirección ya recibió el correo en esa misma campaña,
   **When** se arma la lista, **Then** se marca como "Ya enviado" y queda desmarcada por defecto
   (la usuaria puede marcarla si realmente quiere reenviar).
4. **Given** un reintento terminado con nuevos fallos, **When** ve el resultado, **Then** puede
   volver a "Corregir y reintentar" tantas veces como quiera; cada reintento conserva el código de
   la campaña original con un sufijo de intento (p. ej. `C-7F3A-R2`).
5. **Given** que alguno de los adjuntos originales ya no existe en su ubicación, **When** inicia el
   reintento, **Then** la app lo avisa y le pide volver a seleccionarlo o quitarlo.

---

### User Story 4 - Envío "Todos a la vez" (Priority: P2)

La usuaria elige, en una pantalla con dos opciones grandes y visualmente distintas, "Todos a la vez"
en lugar de "Uno por uno". Se envía un único correo a todos los destinatarios, que van en copia
oculta por defecto.

**Why this priority**: requisito explícito, pero el flujo uno a uno ya entrega valor por sí solo.

**Independent Test**: enviar en modo "Todos a la vez" a 3 direcciones de prueba y verificar que
cada una recibe el correo sin ver las direcciones de las otras.

**Acceptance Scenarios**:

1. **Given** el paso de modo de envío, **When** la usuaria lo ve, **Then** hay dos opciones
   claramente distintas (ícono, título y descripción de una línea con ejemplo) y ninguna está
   preseleccionada.
2. **Given** el modo "Todos a la vez", **When** el cuerpo contiene variables, **Then** la app
   advierte que las variables no se pueden personalizar en este modo y no deja avanzar hasta que
   se quiten o se cambie de modo.
3. **Given** el modo "Todos a la vez", **When** la usuaria activa la opción "Mostrar los
   destinatarios entre sí", **Then** ve una advertencia de privacidad antes de confirmar.
4. **Given** una lista más grande que el máximo de destinatarios por mensaje que admite el
   servidor, **When** se envía, **Then** la app divide el envío en tantos mensajes como haga falta
   y lo informa en la confirmación.

---

### User Story 5 - Personalizar con variables y adjuntar archivos (Priority: P2)

Al redactar, la usuaria ve las columnas del Excel como botones (p. ej. "Nombre", "Empresa"); al
pulsarlos se insertan en el asunto o cuerpo. Puede adjuntar uno o varios archivos. Antes de enviar,
ve una vista previa del correo tal como lo recibirá un destinatario concreto y puede enviarse una
prueba a sí misma.

**Why this priority**: aumenta el valor del envío uno a uno, pero no bloquea el flujo básico.

**Independent Test**: con un Excel con columna "Nombre", redactar "Hola {Nombre}", previsualizar la
fila 2 y verificar que se muestra el nombre de esa fila; enviarse una prueba y recibirla.

**Acceptance Scenarios**:

1. **Given** el paso de redacción, **When** pulsa el botón de una columna, **Then** se inserta la
   variable en la posición del cursor.
2. **Given** una variable cuyo valor está vacío en alguna fila, **When** pasa a la revisión,
   **Then** la app indica cuántas filas tienen ese valor vacío y las deja ver.
3. **Given** el paso de revisión, **When** navega entre destinatarios con "anterior/siguiente",
   **Then** ve el asunto y cuerpo ya personalizados para cada uno.
4. **Given** el botón "Enviarme una prueba", **When** lo pulsa, **Then** recibe en su propia
   casilla el correo personalizado con la primera fila y sus adjuntos.
5. **Given** adjuntos que en total superan el tamaño máximo permitido por el servidor, **When**
   intenta avanzar, **Then** la app lo impide y le dice cuánto debe reducir.

---

### User Story 6 - Tutorial de conexión de la cuenta (Priority: P2)

Si la conexión falla, o si la usuaria pulsa "¿Cómo conecto mi cuenta?", ve un tutorial paso a paso
con capturas que explica qué contraseña usar y, si su organización bloquea el acceso, qué pedirle
exactamente a su área de TI (con un texto listo para copiar y enviar).

**Why this priority**: en cuentas corporativas, el acceso suele depender de TI; sin guía la usuaria
queda bloqueada en el primer paso.

**Independent Test**: provocar cada tipo de fallo de conexión (contraseña incorrecta, acceso
deshabilitado por la organización, sin internet) y verificar que cada uno muestra un mensaje
distinto con el paso del tutorial correspondiente.

**Acceptance Scenarios**:

1. **Given** una contraseña incorrecta, **When** prueba la conexión, **Then** ve "La contraseña no
   es correcta" y un enlace al tutorial de contraseña.
2. **Given** una cuenta cuya organización tiene deshabilitado este tipo de acceso, **When** prueba
   la conexión, **Then** ve un mensaje que lo explica y un botón "Copiar mensaje para TI".
3. **Given** que la usuaria marcó "Recordar mi cuenta", **When** vuelve a abrir la app, **Then** la
   cuenta aparece conectada sin volver a escribir la contraseña.

---

### User Story 7 - Recuperación ante cierre inesperado (Priority: P3)

Si la app se cierra durante un envío (corte de luz, cierre accidental), al volver a abrirla ofrece
continuar la campaña desde donde quedó, sin reenviar a quien ya recibió.

**Why this priority**: evita duplicados y pérdida de registro; es poco frecuente pero muy costoso.

**Independent Test**: cerrar la app a la fuerza con 10 de 20 enviados, reabrirla y verificar que
ofrece continuar y que solo se envían los 10 restantes.

**Acceptance Scenarios**:

1. **Given** una campaña interrumpida, **When** se abre la app, **Then** ve "Hay un envío sin
   terminar" con cuántos faltan y las opciones "Continuar" o "Descartar y generar reporte".
2. **Given** "Descartar y generar reporte", **When** lo elige, **Then** se genera el Excel con los
   pendientes y fallidos.

---

### Edge Cases

- Excel con varias hojas: la usuaria elige la hoja; por defecto, la primera con datos.
- Excel sin fila de encabezados, con celdas combinadas, filas vacías intercaladas o columnas sin
  nombre: se ignoran filas totalmente vacías; columnas sin nombre se muestran como "Columna C".
- Más de una columna que parece contener correos: la app propone una y deja elegir.
- Correo con espacios, mayúsculas o varias direcciones en una celda (separadas por `;` o `,`):
  se recortan espacios; varias direcciones en una celda se marcan como inválidas con motivo
  claro (en v1 no se separan).
- Direcciones duplicadas: se envía una sola vez; las repeticiones aparecen en la preview como
  "Duplicado" y en el reporte final como omitidas.
- Archivo abierto en Excel al momento de cargarlo o de escribir el reporte: mensaje claro pidiendo
  cerrarlo, o guardar el reporte con otro nombre.
- Archivo `.xls` (formato antiguo), `.csv` o protegido con contraseña: mensaje explicando cómo
  guardarlo como `.xlsx`.
- Pérdida de conexión a internet a mitad del envío: el envío se pausa, reintenta y, si no vuelve,
  los restantes quedan como pendientes, no como fallidos.
- La sesión con el servidor caduca o el límite de envío del proveedor se alcanza a mitad de
  campaña: el envío se pausa con mensaje claro; los restantes quedan pendientes y se puede
  continuar luego.
- La usuaria pulsa "Detener": termina el correo en curso, el resto queda como "Omitido (detenido
  por el usuario)" y se genera el reporte.
- Lista vacía o sin ningún correo válido: no se puede avanzar del paso de destinatarios.
- Asunto vacío: se advierte pero se permite continuar tras confirmar.
- Excel muy grande (p. ej. 5.000 filas): la preview, la búsqueda y el marcado/desmarcado se
  mantienen fluidos y el uso de memoria no crece con cada búsqueda o cada correo enviado.
- La usuaria desmarca todos los destinatarios: no se puede avanzar y se le explica por qué.
- Buscador sin resultados: mensaje "No hay destinatarios que coincidan" y botón para limpiar.
- Desmarcar sobre un resultado filtrado y luego limpiar la búsqueda: las filas desmarcadas siguen
  desmarcadas (la búsqueda no altera la selección).
- En el reintento, la usuaria borra filas o agrega filas nuevas al Excel de fallidos: se respeta lo
  que haya en el archivo; las filas nuevas se tratan como destinatarios normales.
- En el reintento, la usuaria renombra o borra las columnas agregadas por la app: el reintento
  sigue funcionando con las columnas originales; si no encuentra la campaña asociada, ofrece
  redactar el mensaje de nuevo.
- La usuaria corrige el correo en el Excel **original** en vez del de fallidos: la app, al cargar
  el original como nueva campaña, no puede saber qué ya se envió; el tutorial y la pantalla de
  resultado indican que la corrección se hace en el Excel de fallidos.

## Requirements *(mandatory)*

### Functional Requirements

**Asistente y experiencia**

- **FR-001**: La app MUST guiar el proceso como un asistente de pasos secuenciales: 1) Cuenta,
  2) Destinatarios, 3) Mensaje, 4) Modo de envío, 5) Revisión, 6) Envío, 7) Resultado. Debe verse
  en todo momento en qué paso se está y permitir volver a pasos anteriores sin perder lo ingresado
  (salvo durante el envío).
- **FR-002**: Todos los textos de la interfaz MUST estar en español y sin jerga técnica en el flujo
  principal; parámetros técnicos de conexión solo en una sección "Avanzado" plegada.
- **FR-003**: Cada mensaje de error MUST indicar qué pasó y qué acción puede tomar la usuaria.

**Cuenta**

- **FR-010**: La usuaria MUST poder conectar su cuenta corporativa de Microsoft 365 ingresando su
  correo y contraseña (o contraseña de aplicación), con los parámetros del servidor completados
  automáticamente.
- **FR-011**: La app MUST ofrecer "Probar conexión" que valide las credenciales sin enviar correos,
  y distinguir al menos: credenciales incorrectas, acceso deshabilitado por la organización, sin
  conexión a internet, y error desconocido.
- **FR-012**: La app MUST incluir un tutorial integrado, con capturas, accesible desde el paso de
  cuenta y desde cada error de conexión, incluyendo un texto copiable para pedir a TI que habilite
  el acceso.
- **FR-013**: La usuaria MUST poder elegir "Recordar mi cuenta"; si lo elige, la contraseña se
  guarda solo en el almacén seguro de credenciales del sistema operativo. Debe existir "Olvidar mi
  cuenta".
- **FR-014**: La usuaria MUST poder definir el nombre visible del remitente (por defecto, el de la
  cuenta).

**Destinatarios**

- **FR-020**: La usuaria MUST poder cargar un archivo `.xlsx` y elegir la hoja.
- **FR-021**: La app MUST detectar automáticamente la columna de correo (por nombre de encabezado o
  por contenido) y permitir cambiarla.
- **FR-022**: La app MUST mostrar una preview en tabla de todas las filas, con un indicador por fila
  (válido, inválido con motivo, duplicado) y totales de cada tipo, con filtro por estado.
- **FR-023**: Solo las filas válidas, no duplicadas y marcadas MUST considerarse destinatarios;
  inválidas, duplicadas y desmarcadas se cuentan como omitidas en el resumen final, cada una con
  su motivo (cuáles van además al Excel de fallidos lo define FR-061).
- **FR-024**: Cada fila de la preview MUST tener una casilla para incluirla o excluirla, marcada por
  defecto si es válida y no duplicada; debe haber "Marcar todos" y "Desmarcar todos" que actúen
  sobre las filas visibles (respetando la búsqueda activa). El total "Se enviará a N" MUST
  actualizarse al instante.
- **FR-025**: La preview MUST ofrecer un buscador de texto libre que filtre las filas que contengan
  el texto en cualquier columna, sin distinguir mayúsculas ni tildes, actualizándose mientras se
  escribe. La búsqueda MUST NOT modificar la selección.
- **FR-026**: Con conexión a internet, la app MUST verificar que el dominio de cada dirección
  (lo que va después de la `@`) existe y puede recibir correo, y marcar como inválidas con motivo
  "El dominio no existe o no recibe correos" las que no pasen (p. ej. `empresa.con`). Sin conexión,
  la verificación se omite y se avisa. Esto detecta antes de enviar los typos de dominio, que el
  servidor suele aceptar y rechazar más tarde con un rebote.

**Mensaje**

- **FR-030**: La usuaria MUST poder escribir asunto y cuerpo en texto plano.
- **FR-031**: La app MUST ofrecer las columnas del Excel como variables insertables en asunto y
  cuerpo, reemplazadas por el valor de cada fila al enviar en modo uno a uno.
- **FR-032**: La usuaria MUST poder adjuntar uno o más archivos, ver la lista con tamaños y
  quitarlos; la app MUST impedir superar el tamaño máximo de mensaje del servidor.
- **FR-033**: La app MUST conservar como borrador el último asunto, cuerpo y adjuntos usados, para
  no perder el trabajo al cerrar la aplicación.

**Modo de envío**

- **FR-040**: La app MUST presentar dos opciones visualmente distintas y mutuamente excluyentes:
  "Uno por uno" (cada destinatario recibe su propio correo, puede personalizarse) y "Todos a la
  vez" (un mismo correo a todos), sin opción preseleccionada.
- **FR-041**: En "Todos a la vez", los destinatarios MUST ir en copia oculta por defecto; mostrarlos
  entre sí requiere activar una opción explícita con advertencia de privacidad.
- **FR-042**: En "Todos a la vez", la app MUST impedir el uso de variables y dividir el envío en
  varios mensajes si la lista supera el máximo de destinatarios por mensaje del servidor.

**Revisión y envío**

- **FR-050**: Antes de enviar, la app MUST mostrar una vista previa del correo personalizado
  navegable por destinatario, y un resumen (cantidad, modo, adjuntos, remitente).
- **FR-051**: La app MUST ofrecer "Enviarme una prueba" a la propia cuenta, sin contarlo en la
  campaña.
- **FR-052**: Iniciar el envío MUST requerir una confirmación explícita que muestre cantidad de
  correos y modo.
- **FR-053**: Durante el envío, la app MUST mostrar progreso (enviados, fallidos, restantes, tiempo
  estimado) y permitir detenerlo; la interfaz MUST seguir respondiendo.
- **FR-054**: La app MUST espaciar los envíos para mantenerse dentro de los límites de envío del
  proveedor y avisar antes de empezar si la campaña supera el límite diario estimado.
- **FR-055**: Un fallo en un destinatario MUST NOT detener el envío al resto. Errores permanentes
  (dirección rechazada) marcan a ese destinatario como fallido y se continúa, sin reintentar.
  Errores transitorios (conexión, límite temporal, rechazo temporal) MUST reintentarse un número
  limitado de veces; si persisten, el envío se **pausa** con un mensaje claro y ese destinatario y
  los restantes quedan **pendientes** (no fallidos) para continuar más tarde.
- **FR-056**: El estado de cada destinatario MUST guardarse a disco a medida que se procesa, para
  poder retomar la campaña tras un cierre inesperado sin reenviar a quien ya recibió (User Story 7).

**Resultado y reporte**

- **FR-060**: Al terminar, la app MUST mostrar el resumen con enviados, fallidos, omitidos y el
  código de campaña.
- **FR-061**: Si hubo filas a corregir, la app MUST generar un `.xlsx` con las mismas columnas y
  orden que el original, solo con esas filas, más las columnas "Estado", "Motivo" (en lenguaje
  claro) y "Código de campaña"; se guarda junto al Excel original con nombre
  `<original>_fallidos_<fecha-hora>.xlsx` (o en otra carpeta si la usuaria lo elige o no hay
  permisos de escritura). Filas a corregir = fallidas al enviar, inválidas, y pendientes por
  detención o interrupción. Las excluidas por la usuaria y las duplicadas NO se incluyen (no son
  errores y no deben reaparecer en un reintento); sí se cuentan en el resumen.
- **FR-062**: La app MUST informar en el resumen que los rebotes que lleguen más tarde a la bandeja
  de entrada no se reflejan en el reporte.
- **FR-063**: La app MUST ofrecer "Corregir y reintentar" en la pantalla de resultado y "Reintentar
  fallidos de una campaña anterior" en la pantalla de inicio. Ambos releen el Excel de fallidos
  (posiblemente editado a mano), lo validan de nuevo y llevan a la preview con casillas y
  buscador, con el mensaje, adjuntos y modo de la campaña original precargados y editables.
- **FR-064**: El reintento MUST enviar solo a las filas del Excel de fallidos que la usuaria deje
  marcadas, y MUST desmarcar por defecto las direcciones que ya figuren como enviadas en esa
  campaña, para evitar duplicados.
- **FR-065**: La app MUST conservar localmente los datos de cada campaña necesarios para reintentar
  (mensaje, rutas de adjuntos, modo, estados por destinatario) durante un período limitado, y
  permitir borrarlos. Por defecto se conservan 30 días.

**Soporte y trazabilidad**

- **FR-070**: Cada campaña MUST tener un código único visible para la usuaria, presente en el
  reporte y en todos los registros internos de esa campaña.
- **FR-071**: La app MUST mantener un registro local de actividad sin contraseñas, sin cuerpo del
  mensaje y con direcciones enmascaradas, y ofrecer "Abrir carpeta de registros" para enviarlo a
  soporte.

**Rendimiento y uso de memoria**

- **FR-075**: El uso de memoria de la app MUST mantenerse acotado y no crecer con el número de
  correos enviados, de búsquedas realizadas ni de reintentos: los datos temporales de cada correo
  (mensaje armado, adjuntos codificados) MUST liberarse una vez enviado, y no se mantienen copias
  completas duplicadas de la lista de destinatarios.
- **FR-076**: Cualquier caché que la app use (p. ej. para acelerar la búsqueda o el armado de
  correos) MUST tener tamaño acotado y conocido, y liberarse al cerrar la lista o terminar la
  campaña.
- **FR-077**: Los archivos locales que la app genera (registros, estado de campañas) MUST tener
  límite de tamaño o de antigüedad, para no llenar el disco con el uso.

**Distribución**

- **FR-080**: La app MUST entregarse como un único archivo ejecutable para Windows 10/11 que funcione
  con doble clic, sin instalar nada y sin permisos de administrador.

### Key Entities

- **Cuenta remitente**: correo, nombre visible, credencial (guardada solo en el almacén seguro si se
  eligió recordar), estado de conexión.
- **Lista de destinatarios**: archivo de origen, hoja, columnas (en orden), columna de correo y las
  filas con sus valores originales.
- **Destinatario**: referencia a su fila original, dirección normalizada, estado de validación
  (válido, inválido, duplicado), si está marcado para envío, y estado de envío (pendiente, enviado,
  fallido, omitido) con motivo.
- **Mensaje**: asunto y cuerpo (con variables), adjuntos, nombre del remitente.
- **Campaña**: código único, cuenta, lista, mensaje, modo (uno por uno / todos a la vez, con o sin
  CCO), fecha de inicio y fin, contadores y estado (en curso, detenida, interrumpida, terminada).
- **Reporte de fallidos**: archivo generado a partir de la campaña con las filas a corregir; es
  también la fuente de un reintento.
- **Intento**: cada ejecución de envío de una campaña (el original y cada reintento), con su propio
  sufijo de código, lista de destinatarios y resultados.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona sin conocimientos técnicos, con cuenta ya habilitada, completa su primera
  campaña de 50 destinatarios en menos de 10 minutos, sin ayuda externa, en al menos 4 de cada 5
  pruebas con usuarios.
- **SC-002**: En pruebas de usabilidad, el 100% de los participantes identifica correctamente cuál
  opción envía "uno por uno" y cuál "a todos a la vez" antes de confirmar.
- **SC-003**: El 100% de los destinatarios de una campaña termina con un estado registrado (enviado,
  fallido u omitido); ninguno se pierde, incluso tras un cierre forzado de la app.
- **SC-004**: Tras un cierre forzado y reanudación, ningún destinatario recibe el correo dos veces.
- **SC-005**: El Excel de fallidos conserva el 100% de las columnas y valores originales de las filas
  fallidas y puede reutilizarse directamente como fuente de una nueva campaña.
- **SC-006**: La app abre y queda lista para usarse en menos de 10 segundos en un equipo Windows de
  oficina típico, sin instalación previa.
- **SC-007**: La preview de un Excel de 5.000 filas se muestra en menos de 5 segundos y se desplaza
  sin trabas.
- **SC-008**: Cada error de conexión de la lista FR-011 produce un mensaje distinto y accionable,
  verificable en pruebas.
- **SC-009**: Corregir un typo en el Excel de fallidos y reintentar lleva menos de 2 minutos y envía
  solo a las filas corregidas; ningún destinatario ya enviado recibe un duplicado salvo que la
  usuaria lo marque explícitamente.
- **SC-010**: Con 5.000 filas, el buscador muestra resultados en menos de medio segundo después de
  dejar de escribir, y marcar/desmarcar se refleja de inmediato.
- **SC-011**: Durante una campaña de 5.000 correos uno por uno, el uso de memoria de la app se
  mantiene estable (sin crecimiento sostenido entre el primer y el último 10% del envío) y por
  debajo de un tope que se fija en el plan.

## Assumptions

- La usuaria tiene una cuenta corporativa de Microsoft 365 y su organización permite (o puede
  habilitar) el envío autenticado desde aplicaciones externas con usuario y contraseña. Si la
  organización exige verificación en dos pasos, se asume que se puede usar una contraseña de
  aplicación o que TI habilita el acceso; esto se verifica en la fase de investigación.
- Volumen esperado por campaña: de decenas a pocos miles de destinatarios. Los límites del
  proveedor (por minuto, por día, destinatarios por mensaje, tamaño de mensaje) están verificados
  en documentación oficial en `research.md` (R2) y se configuran como valores, no se asumen.
- El cuerpo es texto plano en v1; formato enriquecido (negrita, enlaces, imágenes en línea) queda
  fuera de alcance.
- Solo `.xlsx` en v1; `.xls`, `.csv` y Google Sheets quedan fuera de alcance (con mensaje de ayuda).
- Solo Microsoft 365 en v1; Gmail, Outlook personal y otros servidores quedan fuera de alcance,
  aunque el diseño debe permitir agregarlos.
- "Iniciar sesión con Microsoft" (sin contraseña, con la pantalla de Microsoft) queda fuera de v1
  pero el diseño debe permitir agregarlo sin rehacer la app (ver *Riesgos*).
- Programar envíos para más tarde, seguimiento de aperturas y detección de rebotes asíncronos quedan
  fuera de alcance.
- Una sola usuaria por equipo; sin sincronización entre equipos.
- Se acepta que Windows muestre una advertencia la primera vez que se abre un ejecutable no firmado;
  el tutorial lo explica. La firma de código queda como decisión posterior.

## Riesgos

- **R-1 (alto) — Retiro de la autenticación con contraseña en Microsoft 365**: Microsoft anunció el
  retiro de la autenticación básica para el envío autenticado (SMTP AUTH) en Exchange Online, con
  rechazos previstos inicialmente para marzo–abril de 2026, y luego postergado a 2027 o más
  adelante, empezando por organizaciones nuevas. Fuentes:
  [Exchange Team Blog](https://techcommunity.microsoft.com/blog/exchange/exchange-online-to-retire-basic-auth-for-client-submission-smtp-auth/4114750),
  [anuncio de postergación](https://techcommunity.microsoft.com/discussions/exchange_general/microsoft-delays-retirement-of-basic-authentication-for-smtp-auth/4490414).
  **Mitigación**: el modo de autenticación queda desacoplado (constitución, principio VII) para
  agregar "Iniciar sesión con Microsoft" en una versión 2; la fecha de retiro definitiva se revisa
  antes de cada release.
- **R-2 (alto) — Acceso deshabilitado por la organización**: según Microsoft, este acceso viene
  deshabilitado en organizaciones creadas desde enero de 2020 y es incompatible con los "valores
  predeterminados de seguridad" de Entra ID; TI debe habilitarlo para el buzón. **Mitigación**:
  diagnóstico claro y texto para TI (FR-011, FR-012). Ver `research.md`.
- **R-4 (medio) — Microsoft no recomienda este canal para envíos masivos**: la documentación de
  límites indica que Exchange Online no está pensado para escenarios de envío masivo (límite de
  30 mensajes por minuto y 10.000 destinatarios por día). **Mitigación**: el ritmo de envío y el
  aviso de límite diario (FR-054); 5.000 correos uno por uno toman ~3 horas.
- **R-5 (medio) — Fallos que el servidor reporta tarde**: direcciones inexistentes pueden ser
  aceptadas al enviar y rebotar después por correo, sin quedar en el Excel de fallidos.
  **Mitigación**: verificación de dominio (FR-026) y aviso explícito (FR-062); leer rebotes
  automáticamente queda para v2 (requiere acceso a la bandeja).
- **R-3 (bajo) — Advertencia de Windows por ejecutable no firmado**: puede asustar a la usuaria.
  **Mitigación**: tutorial; evaluar firma de código.
