from sqlalchemy import inspect, text

from app.extensions import db


def _has_index(inspector, table_name, index_name):
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade_schema():
    db.create_all()
    inspector = inspect(db.engine)
    changes = []

    application_columns = {
        column["name"] for column in inspector.get_columns("caregiver_applications")
    }
    if "user_id" not in application_columns:
        db.session.execute(
            text(
                "ALTER TABLE caregiver_applications "
                "ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
        )
        db.session.commit()
        changes.append("caregiver_applications.user_id")
        inspector = inspect(db.engine)

    db.session.execute(
        text(
            """
            INSERT INTO user_roles (user_id, role, created_at, updated_at)
            SELECT users.id, users.role, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM users
            WHERE users.role IN ('family', 'caregiver', 'admin')
              AND NOT EXISTS (
                SELECT 1
                FROM user_roles
                WHERE user_roles.user_id = users.id
                  AND user_roles.role = users.role
              )
            """
        )
    )
    db.session.commit()

    if not _has_index(inspector, "caregiver_applications", "ix_caregiver_applications_user_id"):
        db.session.execute(
            text(
                "CREATE INDEX ix_caregiver_applications_user_id "
                "ON caregiver_applications (user_id)"
            )
        )
        db.session.commit()
        changes.append("ix_caregiver_applications_user_id")

    return {
        "upgraded": True,
        "changes": changes,
        "legacyApplicationsWithoutUser": db.session.execute(
            text(
                "SELECT COUNT(*) FROM caregiver_applications "
                "WHERE user_id IS NULL"
            )
        ).scalar_one(),
    }
