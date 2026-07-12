from app.extensions import db
from app.models.base import TimestampMixin, utc_now


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    role = db.Column(db.String(30), default="family", nullable=False, index=True)
    full_name = db.Column(db.String(160), default="", nullable=False)
    first_name = db.Column(db.String(80), default="", nullable=False)
    city = db.Column(db.String(80), default="", nullable=False)
    neighborhood = db.Column(db.String(120), default="", nullable=False)
    avatar_url = db.Column(db.String(500), default="", nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))

    care_requests = db.relationship("CareRequest", back_populates="family_user")
    notifications = db.relationship("Notification", back_populates="user")
    favorites = db.relationship("FavoriteCaregiver", back_populates="user")
    addresses = db.relationship("Address", back_populates="user", cascade="all, delete-orphan")

    def display_first_name(self):
        if self.first_name:
            return self.first_name
        return (self.full_name or "").strip().split(" ")[0] if self.full_name else ""

    def to_dict(self, include_stats=False):
        data = {
            "id": self.id,
            "fullName": self.full_name,
            "firstName": self.display_first_name(),
            "phone": self.phone,
            "city": self.city,
            "neighborhood": self.neighborhood,
            "avatar": self.avatar_url,
            "avatarUrl": self.avatar_url,
            "role": self.role,
            "isVerified": self.is_verified,
            **self.timestamps_dict(),
        }
        if include_stats:
            from app.models.caregiver import FavoriteCaregiver
            from app.models.communication import Conversation

            unread_messages = (
                db.session.query(db.func.coalesce(db.func.sum(Conversation.unread_for_family), 0))
                .filter(Conversation.family_user_id == self.id)
                .scalar()
            )
            data["stats"] = {
                "requests": len(self.care_requests),
                "favoriteCaregivers": FavoriteCaregiver.query.filter_by(user_id=self.id).count(),
                "unreadMessages": int(unread_messages or 0),
            }
        return data


class OtpCode(TimestampMixin, db.Model):
    __tablename__ = "otp_codes"

    phone = db.Column(db.String(20), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(40), default="login", nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True))

    @property
    def is_consumed(self):
        return self.consumed_at is not None

    @property
    def is_expired(self):
        return utc_now() > self.expires_at


class Address(TimestampMixin, db.Model):
    __tablename__ = "addresses"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    label = db.Column(db.String(80), default="خانه", nullable=False)
    province = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    neighborhood = db.Column(db.String(120), default="", nullable=False)
    address_line = db.Column(db.String(500), default="", nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="addresses")

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "province": self.province,
            "city": self.city,
            "neighborhood": self.neighborhood,
            "addressLine": self.address_line,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "isDefault": self.is_default,
            **self.timestamps_dict(),
        }
