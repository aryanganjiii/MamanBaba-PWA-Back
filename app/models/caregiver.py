from app.extensions import db
from app.models.base import TimestampMixin


class CaregiverProfile(TimestampMixin, db.Model):
    __tablename__ = "caregiver_profiles"

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    national_code = db.Column(db.String(20), unique=True)
    birth_date = db.Column(db.String(20), default="", nullable=False)
    gender = db.Column(db.String(30), default="", nullable=False)
    marital_status = db.Column(db.String(40), default="", nullable=False)
    province = db.Column(db.String(80), default="", nullable=False)
    city = db.Column(db.String(80), default="", nullable=False)
    experience_level = db.Column(db.String(80), default="", nullable=False)
    experience_years = db.Column(db.Integer, default=0, nullable=False)
    hourly_rate = db.Column(db.Integer, default=0, nullable=False)
    response_time = db.Column(db.String(80), default="حدود ۲ ساعت", nullable=False)
    rating = db.Column(db.Float, default=0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)
    repeat_hire_count = db.Column(db.Integer, default=0, nullable=False)
    bio = db.Column(db.Text, default="", nullable=False)
    image_url = db.Column(db.String(500), default="", nullable=False)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    public_status = db.Column(db.String(30), default="public", nullable=False, index=True)
    start_time = db.Column(db.String(10), default="08:00", nullable=False)
    end_time = db.Column(db.String(10), default="16:00", nullable=False)
    can_stay_overnight = db.Column(db.Boolean, default=False, nullable=False)
    available_on_holidays = db.Column(db.Boolean, default=False, nullable=False)
    expectation_notes = db.Column(db.Text, default="", nullable=False)

    user = db.relationship("User", back_populates="caregiver_profile")
    skills = db.relationship("CaregiverSkill", cascade="all, delete-orphan", back_populates="caregiver")
    certificates = db.relationship(
        "CaregiverCertificate", cascade="all, delete-orphan", back_populates="caregiver"
    )
    service_types = db.relationship(
        "CaregiverServiceType", cascade="all, delete-orphan", back_populates="caregiver"
    )
    collaboration_types = db.relationship(
        "CaregiverCollaborationType", cascade="all, delete-orphan", back_populates="caregiver"
    )
    available_days = db.relationship(
        "CaregiverAvailableDay", cascade="all, delete-orphan", back_populates="caregiver"
    )
    service_areas = db.relationship(
        "CaregiverServiceArea", cascade="all, delete-orphan", back_populates="caregiver"
    )
    highlights = db.relationship(
        "CaregiverHighlight", cascade="all, delete-orphan", back_populates="caregiver"
    )
    reviews = db.relationship(
        "CaregiverReview",
        cascade="all, delete-orphan",
        back_populates="caregiver",
        order_by="desc(CaregiverReview.created_at)",
    )

    def list_values(self, relationship_name):
        return [item.value for item in getattr(self, relationship_name)]

    def to_card_dict(self):
        return {
            "id": self.slug,
            "slug": self.slug,
            "name": self.full_name,
            "image": self.image_url or None,
            "experienceYears": self.experience_years,
            "hourlyRate": self.hourly_rate,
            "responseTime": self.response_time,
            "rating": self.rating,
            "reviewCount": self.review_count,
            "verified": self.verified,
            "repeatHireCount": self.repeat_hire_count,
            "skills": self.list_values("skills"),
            "serviceAreas": self.list_values("service_areas"),
        }

    def to_family_card_dict(self, favorite=False):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.full_name,
            "role": "مراقب سالمند",
            "location": "، ".join([part for part in [self.city, self.service_areas[0].value if self.service_areas else ""] if part]),
            "price": f"{self.hourly_rate:,}",
            "rating": f"{self.rating:.1f}",
            "image": self.image_url,
            "isFavorite": favorite,
        }

    def to_detail_dict(self, favorite=False):
        data = self.to_card_dict()
        data.update(
            {
                "bio": self.bio,
                "gender": self.gender,
                "province": self.province,
                "city": self.city,
                "experienceLevel": self.experience_level,
                "serviceTypes": self.list_values("service_types"),
                "collaborationTypes": self.list_values("collaboration_types"),
                "availableDays": self.list_values("available_days"),
                "startTime": self.start_time,
                "endTime": self.end_time,
                "canStayOvernight": self.can_stay_overnight,
                "availableOnHolidays": self.available_on_holidays,
                "expectationNotes": self.expectation_notes,
                "highlights": [item.to_dict() for item in self.highlights],
                "reviews": [item.to_dict() for item in self.reviews],
                "isFavorite": favorite,
                **self.timestamps_dict(),
            }
        )
        return data

    def refresh_rating(self):
        if not self.reviews:
            self.rating = 0
            self.review_count = 0
            return
        self.review_count = len(self.reviews)
        self.rating = round(sum(review.rating for review in self.reviews) / self.review_count, 1)


class _CaregiverValue(TimestampMixin):
    __abstract__ = True

    caregiver_id = db.Column(db.Integer, db.ForeignKey("caregiver_profiles.id"), nullable=False, index=True)
    value = db.Column(db.String(180), nullable=False)

    def to_dict(self):
        return {"id": self.id, "value": self.value}


class CaregiverSkill(_CaregiverValue, db.Model):
    __tablename__ = "caregiver_skills"
    caregiver = db.relationship("CaregiverProfile", back_populates="skills")


class CaregiverCertificate(_CaregiverValue, db.Model):
    __tablename__ = "caregiver_certificates"
    caregiver = db.relationship("CaregiverProfile", back_populates="certificates")


class CaregiverServiceType(_CaregiverValue, db.Model):
    __tablename__ = "caregiver_service_types"
    caregiver = db.relationship("CaregiverProfile", back_populates="service_types")


class CaregiverCollaborationType(_CaregiverValue, db.Model):
    __tablename__ = "caregiver_collaboration_types"
    caregiver = db.relationship("CaregiverProfile", back_populates="collaboration_types")


class CaregiverAvailableDay(_CaregiverValue, db.Model):
    __tablename__ = "caregiver_available_days"
    caregiver = db.relationship("CaregiverProfile", back_populates="available_days")


class CaregiverServiceArea(_CaregiverValue, db.Model):
    __tablename__ = "caregiver_service_areas"
    caregiver = db.relationship("CaregiverProfile", back_populates="service_areas")


class CaregiverHighlight(TimestampMixin, db.Model):
    __tablename__ = "caregiver_highlights"

    caregiver_id = db.Column(db.Integer, db.ForeignKey("caregiver_profiles.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)

    caregiver = db.relationship("CaregiverProfile", back_populates="highlights")

    def to_dict(self):
        return {"title": self.title, "description": self.description}


class CaregiverReview(TimestampMixin, db.Model):
    __tablename__ = "caregiver_reviews"

    caregiver_id = db.Column(db.Integer, db.ForeignKey("caregiver_profiles.id"), nullable=False, index=True)
    author_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    author_name = db.Column(db.String(160), nullable=False)
    rating = db.Column(db.Integer, default=5, nullable=False)
    text = db.Column(db.Text, nullable=False)
    display_date = db.Column(db.String(80), default="همین حالا", nullable=False)

    caregiver = db.relationship("CaregiverProfile", back_populates="reviews")
    author_user = db.relationship("User")

    def to_dict(self):
        return {
            "id": str(self.id),
            "author": self.author_name,
            "rating": self.rating,
            "text": self.text,
            "date": self.display_date,
            **self.timestamps_dict(),
        }


class FavoriteCaregiver(TimestampMixin, db.Model):
    __tablename__ = "favorite_caregivers"
    __table_args__ = (db.UniqueConstraint("user_id", "caregiver_id", name="uq_user_caregiver_favorite"),)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    caregiver_id = db.Column(db.Integer, db.ForeignKey("caregiver_profiles.id"), nullable=False, index=True)

    user = db.relationship("User", back_populates="favorites")
    caregiver = db.relationship("CaregiverProfile")


class CaregiverApplication(TimestampMixin, db.Model):
    __tablename__ = "caregiver_applications"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    national_code = db.Column(db.String(20), nullable=False, index=True)
    birth_date = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.String(30), nullable=False)
    marital_status = db.Column(db.String(40), nullable=False)
    province = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    experience_level = db.Column(db.String(80), nullable=False)
    start_time = db.Column(db.String(10), default="08:00", nullable=False)
    end_time = db.Column(db.String(10), default="16:00", nullable=False)
    can_stay_overnight = db.Column(db.Boolean, default=False, nullable=False)
    available_on_holidays = db.Column(db.Boolean, default=False, nullable=False)
    hourly_rate = db.Column(db.Integer, nullable=False)
    expectation_notes = db.Column(db.Text, default="", nullable=False)
    about_me = db.Column(db.Text, nullable=False)
    profile_image_url = db.Column(db.String(500), default="", nullable=False)
    profile_image_reminder_skipped = db.Column(db.Boolean, default=False, nullable=False)
    accepted_terms = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(30), default="pending_review", nullable=False, index=True)

    user = db.relationship("User", back_populates="caregiver_applications")
    items = db.relationship(
        "CaregiverApplicationItem", cascade="all, delete-orphan", back_populates="application"
    )
    files = db.relationship(
        "CaregiverApplicationFile", cascade="all, delete-orphan", back_populates="application"
    )

    def grouped_items(self):
        result = {
            "skills": [],
            "certificates": [],
            "serviceTypes": [],
            "collaborationTypes": [],
            "availableDays": [],
            "serviceAreas": [],
        }
        category_map = {
            "skills": "skills",
            "certificates": "certificates",
            "service_types": "serviceTypes",
            "collaboration_types": "collaborationTypes",
            "available_days": "availableDays",
            "service_areas": "serviceAreas",
        }
        for item in self.items:
            key = category_map.get(item.category)
            if key:
                result[key].append(item.value)
        return result

    def to_dict(self):
        data = {
            "id": self.id,
            "userId": self.user_id,
            "fullName": self.full_name,
            "nationalCode": self.national_code,
            "birthDate": self.birth_date,
            "gender": self.gender,
            "maritalStatus": self.marital_status,
            "province": self.province,
            "city": self.city,
            "experienceLevel": self.experience_level,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "canStayOvernight": self.can_stay_overnight,
            "availableOnHolidays": self.available_on_holidays,
            "hourlyRate": self.hourly_rate,
            "expectationNotes": self.expectation_notes,
            "aboutMe": self.about_me,
            "profileImageUrl": self.profile_image_url,
            "profileImageReminderSkipped": self.profile_image_reminder_skipped,
            "acceptedTerms": self.accepted_terms,
            "status": self.status,
            "files": [file.to_dict() for file in self.files],
            **self.grouped_items(),
            **self.timestamps_dict(),
        }
        return data


class CaregiverApplicationItem(TimestampMixin, db.Model):
    __tablename__ = "caregiver_application_items"

    application_id = db.Column(
        db.Integer, db.ForeignKey("caregiver_applications.id"), nullable=False, index=True
    )
    category = db.Column(db.String(60), nullable=False, index=True)
    value = db.Column(db.String(180), nullable=False)

    application = db.relationship("CaregiverApplication", back_populates="items")


class CaregiverApplicationFile(TimestampMixin, db.Model):
    __tablename__ = "caregiver_application_files"

    application_id = db.Column(
        db.Integer, db.ForeignKey("caregiver_applications.id"), nullable=False, index=True
    )
    file_type = db.Column(db.String(40), default="certificate", nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)

    application = db.relationship("CaregiverApplication", back_populates="files")

    def to_dict(self):
        return {
            "id": self.id,
            "fileType": self.file_type,
            "originalName": self.original_name,
            "url": self.url,
        }
