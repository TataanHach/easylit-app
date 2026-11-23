# Registro de cambios · EasyLit

Cada cambio en la funcionalidad del sistema sube la versión (2.5 → 2.6 → 2.7…).
El número se cambia en un solo lugar, `frontend/src/lib/version.ts`, y aquí se
anota qué cambió. La versión más nueva va primero.

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
