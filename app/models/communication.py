from app.extensions import db
from app.models.base import TimestampMixin


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    time_label = db.Column(db.String(80), default="همین حالا", nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    type = db.Column(db.String(40), default="request", nullable=False, index=True)

    user = db.relationship("User", back_populates="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "time": self.time_label,
            "isRead": self.is_read,
            "type": self.type,
            **self.timestamps_dict(),
        }


class Conversation(TimestampMixin, db.Model):
    __tablename__ = "conversations"

    family_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    caregiver_id = db.Column(db.Integer, db.ForeignKey("caregiver_profiles.id"), nullable=True, index=True)
    type = db.Column(db.String(30), default="caregiver", nullable=False, index=True)
    title = db.Column(db.String(160), default="", nullable=False)
    role_label = db.Column(db.String(120), default="", nullable=False)
    unread_for_family = db.Column(db.Integer, default=0, nullable=False)
    online = db.Column(db.Boolean, default=False, nullable=False)

    family_user = db.relationship("User")
    caregiver = db.relationship("CaregiverProfile")
    messages = db.relationship(
        "Message",
        cascade="all, delete-orphan",
        back_populates="conversation",
        order_by="Message.created_at",
    )

    def latest_message(self):
        return self.messages[-1] if self.messages else None

    def to_dict(self):
        latest = self.latest_message()
        name = self.title or (self.caregiver.full_name if self.caregiver else "پشتیبانی مامان بابا")
        role = self.role_label or ("پشتیبانی" if self.type == "support" else "مراقب سالمند")
        return {
            "id": self.id,
            "name": name,
            "role": role,
            "message": latest.body if latest else "",
            "time": latest.time_label if latest else "",
            "unread": self.unread_for_family,
            "type": self.type,
            "online": self.online,
            **self.timestamps_dict(),
        }


class Message(TimestampMixin, db.Model):
    __tablename__ = "messages"

    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    sender_type = db.Column(db.String(30), nullable=False)
    body = db.Column(db.Text, nullable=False)
    time_label = db.Column(db.String(80), default="الان", nullable=False)
    read_at = db.Column(db.DateTime(timezone=True))

    conversation = db.relationship("Conversation", back_populates="messages")
    sender_user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.body,
            "time": self.time_label,
            "sender": "me" if self.sender_type == "family" else "other",
            "senderType": self.sender_type,
            **self.timestamps_dict(),
        }
