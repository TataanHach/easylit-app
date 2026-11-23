# Registro de cambios · EasyLit

Cada cambio en la funcionalidad del sistema sube la versión (2.5 → 2.6 → 2.7…).
El número se cambia en un solo lugar, `frontend/src/lib/version.ts`, y aquí se
anota qué cambió. La versión más nueva va primero.

## v2.8 · 23 de noviembre de 2026

**Códigos de invitación desde el panel de Django**
- Al crear un usuario en `/admin/` se elige «Cómo entrará»: **con código de
  invitación** (por defecto) o con contraseña. Con código, al guardar el panel
  muestra el código una sola vez, igual que la pantalla Equipo. Así el
  superadministrador da de alta a un gerente sin correr comandos.
- Nueva acción en la lista de usuarios: **«Generar código de invitación»**, para
  quien lo perdió, lo tiene vencido o se creó sin código. Omite (y avisa) a quien
  ya tiene acceso, está desactivado o es superadministrador.
- El formulario del panel valida el correo y el nombre (sin símbolos), el RUT y
  que un gerente o trabajador tenga organización. Un superadministrador creado
  ahí queda con acceso al panel (`is_staff` y `is_superuser`).
- Ya no se pueden crear invitaciones a mano en «Invitaciones» (no servían: el
  código solo existe al crearlo).
- 6 pruebas automáticas nuevas (78 en total).

**Casilla del código de invitación**
- En «Crea tu contraseña», la casilla del código acepta como máximo los 8
  caracteres del código: solo letras y números, en mayúsculas, y el guion se pone
  solo (escribir o pegar «k7m2 qx9p» deja «K7M2-QX9P»; lo que sobra se corta).
- Si el código está incompleto, avisa antes de enviar cuántos caracteres se
  escribieron, en vez de esperar la respuesta del servidor.

**Columnas de tablas: emparejamiento por nombre corregido**
- Antes bastaba una palabra en común, aunque fuera «de»: «Formato de venta»
  terminaba en «Código de licitación», «Correo de contacto», «Fecha de
  presentación», etc., y esas columnas no se le preguntaban a la IA.
- Ahora se ignoran palabras como «de», «del», «la», «y», «o», y solo se empareja
  por nombre con el mismo nombre, 2 palabras en común o un nombre de una palabra
  contenido en el otro (se aceptan abreviaturas: «Cant.» / «Cantidad»). Cada
  columna del origen se usa una sola vez. Lo demás lo sugiere la IA.
- 2 pruebas automáticas nuevas (80 en total).

**Confianza de las tablas**
- La confianza de una columna de tabla sugerida por la IA ahora es la que dio la
  IA (antes se cortaba en 60): con todo bien emparejado salía 61% y ahora sale
  91%. Una pareja por nombre parecido cuenta 90 (antes 70); igual, 100. Las de la
  IA siguen marcadas con ✦ en la vista previa para revisarlas.
- 1 prueba automática nueva (81 en total).

## v2.7 · 23 de noviembre de 2026

**Aviso de confianza baja al generar**
- Si la confianza de la transformación es menor a 50%, «Generar documento» abre
  una ventana: «La confianza de esta transformación es baja», con el porcentaje,
  y los botones «Cancelar» y «Sí, generar igual». Con 50% o más se genera directo.
- Es la misma confianza que muestra el historial (promedio que calcula EasyLit
  al procesar el archivo).

## v2.6 · 23 de noviembre de 2026

**Permisos del historial**
- El trabajador solo ve y abre sus propias transformaciones. Su historial ya no
  tiene las pestañas «Equipo» y «Todas» ni el filtro de autor.
- El gerente ve, descarga y elimina las transformaciones de todo su equipo (antes
  la API no lo dejaba abrir ni borrar las de sus colaboradores).
- Al intentar abrir una transformación ajena aparece «No tienes permiso para ver
  esta transformación…», en vez del mensaje en inglés «No Transformacion matches
  the given query». Un trabajador tampoco puede editar el mapeo de otra persona.
- Cualquier otro error «no encontrado» de la API sale en español.

**Validación de textos**
- El nombre de la plantilla, el mandante y el sector no aceptan símbolos como
  `" # $ @`. Se permiten letras, números, espacios y `. , - ( ) / & ' °`.
- Al invitar a un colaborador, el nombre solo acepta letras, espacios y `. ' -`,
  y el correo solo letras, números y `. _ - +` antes de la @.
- La regla se aplica en la pantalla y en la API.

**Pruebas**
- 8 pruebas automáticas nuevas (72 en total) para los permisos y la validación.

## v2.5 · 20 de noviembre de 2026

- Términos y condiciones con casilla de aceptación al crear la contraseña.
- Equipo: «Invitar colaborador», código de invitación de 8 caracteres que se ve
  una sola vez (en la base solo queda su huella) y que no viaja en el enlace.
- Límites de intentos en el login, la revisión del correo y crear contraseña.
- Burbuja «¿Necesitas soporte?» y footer con términos, secciones y contacto.
- Logos nuevos e ícono de la pestaña; textos del login renovados.
- Integración continua con las pruebas automáticas en cada push.
