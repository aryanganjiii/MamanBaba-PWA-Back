from app.extensions import db
from app.models.base import TimestampMixin


class Payment(TimestampMixin, db.Model):
    __tablename__ = "payments"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey("care_requests.id"), nullable=True, index=True)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="initiated", nullable=False, index=True)
    provider = db.Column(db.String(80), default="manual", nullable=False)
    reference_id = db.Column(db.String(120), default="", nullable=False)

    user = db.relationship("User")
    care_request = db.relationship("CareRequest")

    def to_dict(self):
        return {
            "id": self.id,
            "requestId": self.request_id,
            "amount": self.amount,
            "status": self.status,
            "provider": self.provider,
            "referenceId": self.reference_id,
            **self.timestamps_dict(),
        }
