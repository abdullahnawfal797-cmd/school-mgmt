from django.db import migrations


TABLE_NAME = "mobile_api_revokedtoken"


def create_revoked_token_table(apps, schema_editor):
    if TABLE_NAME in schema_editor.connection.introspection.table_names():
        return

    revoked_token = apps.get_model("mobile_api", "RevokedToken")
    schema_editor.create_model(revoked_token)


def delete_revoked_token_table(apps, schema_editor):
    if TABLE_NAME not in schema_editor.connection.introspection.table_names():
        return

    revoked_token = apps.get_model("mobile_api", "RevokedToken")
    schema_editor.delete_model(revoked_token)


class Migration(migrations.Migration):
    dependencies = [
        ("mobile_api", "0004_revokedtoken_homeworkassignment_school_and_more"),
    ]

    operations = [
        migrations.RunPython(
            create_revoked_token_table,
            delete_revoked_token_table,
        ),
    ]
