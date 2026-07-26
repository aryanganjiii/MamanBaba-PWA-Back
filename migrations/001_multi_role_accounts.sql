-- Compatibility migration for existing SQLite deployments.
-- Prefer `flask upgrade-db`, which is idempotent and also backfills existing roles.

CREATE TABLE IF NOT EXISTS user_roles (
    id INTEGER NOT NULL PRIMARY KEY,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL REFERENCES users(id),
    role VARCHAR(30) NOT NULL,
    CONSTRAINT uq_user_role UNIQUE (user_id, role)
);

CREATE INDEX IF NOT EXISTS ix_user_roles_user_id ON user_roles (user_id);
CREATE INDEX IF NOT EXISTS ix_user_roles_role ON user_roles (role);

INSERT OR IGNORE INTO user_roles (user_id, role, created_at, updated_at)
SELECT id, role, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM users
WHERE role IN ('family', 'caregiver', 'admin');

-- Run this statement only when caregiver_applications.user_id does not exist:
-- ALTER TABLE caregiver_applications ADD COLUMN user_id INTEGER REFERENCES users(id);
-- CREATE INDEX ix_caregiver_applications_user_id ON caregiver_applications (user_id);
