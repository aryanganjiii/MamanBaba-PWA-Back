from datetime import UTC, datetime

from app.extensions import db


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    @staticmethod
    def _iso(value):
        return value.isoformat() if value else None

    def timestamps_dict(self):
        return {
            "createdAt": self._iso(self.created_at),
            "updatedAt": self._iso(self.updated_at),
        }
