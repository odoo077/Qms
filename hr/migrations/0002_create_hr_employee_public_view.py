from django.db import migrations

CREATE_VIEW = """
CREATE VIEW hr_employee_public AS
SELECT
    e.id               AS id,
    e.name             AS name,
    e.active           AS active,
    e.company_id       AS company_id,
    e.department_id    AS department_id,
    e.job_id           AS job_id,
    e.work_contact_id  AS work_contact_id,
    e.work_email       AS work_email,
    e.work_phone       AS work_phone,
    e.mobile_phone     AS mobile_phone,
    e.manager_id       AS manager_id,
    e.user_id          AS user_id
FROM hr_employee e;
"""

DROP_VIEW = "DROP VIEW IF EXISTS hr_employee_public;"

class Migration(migrations.Migration):
    dependencies = [
        ("hr", "0001_initial"),  # <- update to match your last hr migration
    ]
    operations = [
        migrations.RunSQL(DROP_VIEW),
        migrations.RunSQL(CREATE_VIEW, reverse_sql=DROP_VIEW),
    ]
