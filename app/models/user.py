from app.extensions import db
from app.models.base import TimestampMixin, utc_now


ACCOUNT_ROLES = {"family", "caregiver", "admin"}


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
    user_roles = db.relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    caregiver_profile = db.relationship(
        "CaregiverProfile",
        back_populates="user",
        uselist=False,
    )
    caregiver_applications = db.relationship(
        "CaregiverApplication",
        back_populates="user",
        order_by="desc(CaregiverApplication.created_at)",
    )

    @property
    def role_names(self):
        roles = {item.role for item in self.user_roles}
        if self.role in ACCOUNT_ROLES:
            roles.add(self.role)
        return sorted(roles)

    def has_role(self, role):
        return role in self.role_names

    def add_role(self, role):
        if role not in ACCOUNT_ROLES:
            raise ValueError(f"Unsupported account role: {role}")
        if any(item.role == role for item in self.user_roles):
            return False
        self.user_roles.append(UserRole(role=role))
        return True

    @property
    def caregiver_status(self):
        if not self.has_role("caregiver"):
            return None
        if self.caregiver_profile:
            if self.caregiver_profile.public_status == "public":
                return "approved"
            return self.caregiver_profile.public_status
        if self.caregiver_applications:
            return self.caregiver_applications[0].status
        return "not_started"

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
            "roles": self.role_names,
            "caregiverStatus": self.caregiver_status,
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


class UserRole(TimestampMixin, db.Model):
    __tablename__ = "user_roles"
    __table_args__ = (
        db.UniqueConstraint("user_id", "role", name="uq_user_role"),
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(30), nullable=False, index=True)

    user = db.relationship("User", back_populates="user_roles")


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
