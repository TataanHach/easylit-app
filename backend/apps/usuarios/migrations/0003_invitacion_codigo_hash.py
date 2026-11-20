"""
El código de invitación deja de guardarse legible: la columna `token` pasa a
llamarse `codigo_hash` y guarda solo un HMAC-SHA256 del código.

Los códigos que ya existían se reemplazan por su huella, para que no quede
ninguno legible en la base. Esos códigos antiguos (largos) ya no sirven para
crear la contraseña: el gerente genera uno nuevo desde la pantalla Equipo.
"""
from django.db import migrations, models
from django.utils.crypto import salted_hmac


def ocultar_codigos_existentes(apps, schema_editor):
    Invitacion = apps.get_model("usuarios", "Invitacion")
    for inv in Invitacion.objects.all().only("id", "codigo_hash"):
        valor = inv.codigo_hash or ""
        if len(valor) == 64 and all(c in "0123456789abcdef" for c in valor):
            continue   # ya es una huella
        inv.codigo_hash = salted_hmac("easylit.invitacion.antiguo", valor, algorithm="sha256").hexdigest()
        inv.save(update_fields=["codigo_hash"])


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0002_usuario_firebase_uid"),
    ]

    operations = [
        migrations.RenameField(model_name="invitacion", old_name="token", new_name="codigo_hash"),
        migrations.RunPython(ocultar_codigos_existentes, migrations.RunPython.noop),
    ]
