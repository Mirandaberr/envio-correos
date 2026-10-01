# Guía de uso — Envío de correos

Esta aplicación envía un correo desde **tu cuenta de la empresa** a una lista de personas que
tenés en un archivo de Excel. Te guía paso a paso; no hace falta instalar nada.

## Antes de empezar

- Tu área de TI tiene que haber habilitado el envío desde aplicaciones para tu cuenta
  («Authenticated SMTP»). Si no lo hizo, la app te lo va a avisar y te da un mensaje listo para
  enviarles.
- Tené a mano el Excel con los destinatarios: una fila por persona y una columna con el correo.
  La primera fila tiene que tener los títulos (por ejemplo: Nombre, Correo, Ciudad).
- El archivo tiene que ser **.xlsx**. Si es .xls o .csv, abrilo en Excel y usá «Guardar como» →
  «Libro de Excel (.xlsx)».

## Abrir la aplicación

Hacé doble clic en `EnvioCorreos.exe`. La primera vez, Windows puede mostrar «Windows protegió su
PC»: pulsá **Más información** y después **Ejecutar de todas formas**. Solo pasa la primera vez.

## Paso a paso

1. **Cuenta.** Escribí tu correo y tu contraseña y pulsá **Probar conexión**. Si querés que la
   app lo recuerde la próxima vez, marcá «Recordar mi cuenta en este equipo» (se guarda en el
   almacén seguro de Windows). Si algo falla, pulsá **Ver ayuda para este error**.
2. **Destinatarios.** Pulsá **Elegir archivo…** y elegí tu Excel. Vas a ver la lista con una
   casilla por persona:
   - Desmarcá a quien no quieras incluir. Con el **buscador** (🔍) encontrás a alguien rápido.
   - Las filas en gris no se pueden enviar (correo vacío, mal escrito, repetido o con un dominio
     que no existe); la columna «Estado» dice por qué.
   - Abajo ves cuántos correos se van a enviar.
3. **Mensaje.** Escribí el asunto y el texto. Los botones con los nombres de las columnas
   (Nombre, Empresa…) insertan ese dato de cada persona. Con **Agregar adjunto…** sumás archivos.
4. **Modo de envío.** Elegí una de las dos tarjetas:
   - **Uno por uno:** cada persona recibe su propio correo, con sus datos. Nadie ve a los demás.
   - **Todos a la vez:** el mismo correo para todos, en copia oculta. (No se pueden usar los datos
     de cada persona.)
5. **Revisión.** Revisá el resumen y la vista previa (con ◀ ▶ ves cómo le llega a cada persona).
   Con **Enviarme una prueba** te llega a vos primero. Cuando esté todo bien, pulsá **Enviar**.
6. **Envío.** Vas a ver el avance. Microsoft permite unos 30 correos por minuto, así que una
   lista grande puede tardar (por ejemplo, 1.000 correos ≈ 35 minutos). Podés seguir usando la
   computadora; no la apagues. Si hace falta, pulsá **Detener envío**.
7. **Resultado.** Ves cuántos se enviaron y cuántos fallaron, y un **código de campaña**.

## Si algún correo falló

La app guarda un Excel llamado `…_fallidos_<fecha>.xlsx` junto a tu archivo original, con las
mismas columnas y el motivo de cada fallo.

1. Pulsá **Corregir y reintentar**: se abre ese Excel.
2. Corregí las direcciones mal escritas, guardá y cerrá el archivo.
3. Volvé a la app y pulsá **Continuar**. Se envía **solo** a esas filas, con el mismo mensaje.

También podés hacerlo otro día desde la pantalla de inicio con **Reintentar fallidos de una
campaña anterior**.

> Importante: si una dirección no existe, el aviso («rebote») puede llegar más tarde a tu bandeja
> de entrada y no aparece en el resumen de la app.

## Si la app se cerró en medio de un envío

Al abrirla de nuevo vas a ver «Hay un envío sin terminar». Elegí **Continuar el envío** (se envía
solo a quienes faltaban, nadie lo recibe dos veces) o **Descartar y generar reporte**.

## Pedir ayuda

En la pantalla de resultado, **Abrir carpeta de registros** abre la carpeta con el registro de
actividad. Enviala a soporte junto con el **código de campaña**. El registro no contiene tu
contraseña ni el texto de tus correos, y las direcciones aparecen parcialmente ocultas.
