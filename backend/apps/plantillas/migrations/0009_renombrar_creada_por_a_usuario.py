"""plantilla.creada_por_id pasa a llamarse plantilla.usuario_id (mismo dato, sin perder nada)."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("plantillas", "0008_quitar_campos_sin_uso"),
    ]

    operations = [
        migrations.RenameField(
            model_name="plantilla",
            old_name="creada_por",
            new_name="usuario",
        ),
    ]
