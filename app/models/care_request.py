from app.extensions import db
from app.models.base import TimestampMixin


REQUEST_STATUS_LABELS = {
    "active": "در حال بررسی",
    "pending": "در انتظار پرداخت",
    "completed": "تکمیل‌شده",
    "cancelled": "لغوشده",
}


class CareRequest(TimestampMixin, db.Model):
    __tablename__ = "care_requests"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    province = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    neighborhood = db.Column(db.String(120), nullable=False)
    person = db.Column(db.String(80), nullable=False)
    age_range = db.Column(db.String(80), nullable=False)
    gender = db.Column(db.String(30), nullable=False)
    physical_status = db.Column(db.String(200), nullable=False)
    care_notes = db.Column(db.Text, default="", nullable=False)
    presence_type = db.Column(db.String(60), nullable=False)
    recurrence_type = db.Column(db.String(60), nullable=False)
    start_date = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    end_date_mode = db.Column(db.String(60), default="", nullable=False)
    end_date = db.Column(db.String(20), default="", nullable=False)
    full_day_pattern = db.Column(db.String(80), default="", nullable=False)
    full_day_duration_days = db.Column(db.Integer, default=1, nullable=False)
    weekly_duration_mode = db.Column(db.String(80), default="", nullable=False)
    duration_weeks = db.Column(db.Integer, default=0, nullable=False)
    budget_amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="active", nullable=False, index=True)
    title = db.Column(db.String(180), default="", nullable=False)
    service_type = db.Column(db.String(120), default="مراقبت در منزل", nullable=False)

    family_user = db.relationship("User", back_populates="care_requests")
    needs = db.relationship("CareRequestNeed", cascade="all, delete-orphan", back_populates="care_request")
    selected_days = db.relationship(
        "CareRequestSelectedDay", cascade="all, delete-orphan", back_populates="care_request"
    )
    offers = db.relationship("CareOffer", cascade="all, delete-orphan", back_populates="care_request")

    @property
    def status_label(self):
        return REQUEST_STATUS_LABELS.get(self.status, self.status)

    @property
    def location_label(self):
        return "، ".join([part for part in [self.city, self.neighborhood] if part])

    @property
    def time_label(self):
        return f"{self.start_time} تا {self.end_time}"

    @property
    def date_label(self):
        return self.start_date

    def to_card_dict(self):
        return {
            "id": self.id,
            "title": self.title or f"مراقبت {self.presence_type} {self.person}",
            "serviceType": self.service_type,
            "date": self.date_label,
            "time": self.time_label,
            "location": self.location_label,
            "status": self.status,
            "statusLabel": self.status_label,
            "offersCount": len(self.offers),
            **self.timestamps_dict(),
        }

    def to_detail_dict(self):
        data = self.to_card_dict()
        data.update(
            {
                "province": self.province,
                "city": self.city,
                "neighborhood": self.neighborhood,
                "person": self.person,
                "age": self.age_range,
                "gender": self.gender,
                "physicalStatus": self.physical_status,
                "careNeeds": [need.value for need in self.needs],
                "careNotes": self.care_notes,
                "presenceType": self.presence_type,
                "recurrenceType": self.recurrence_type,
                "startDate": self.start_date,
                "startTime": self.start_time,
                "endTime": self.end_time,
                "selectedDays": [day.value for day in self.selected_days],
                "endDateMode": self.end_date_mode,
                "endDate": self.end_date,
                "fullDayPattern": self.full_day_pattern,
                "fullDayDurationDays": self.full_day_duration_days,
                "weeklyDurationMode": self.weekly_duration_mode,
                "durationWeeks": self.duration_weeks,
                "budget": self.budget_amount,
            }
        )
        return data


class CareRequestNeed(TimestampMixin, db.Model):
    __tablename__ = "care_request_needs"

    request_id = db.Column(db.Integer, db.ForeignKey("care_requests.id"), nullable=False, index=True)
    value = db.Column(db.String(180), nullable=False)
    care_request = db.relationship("CareRequest", back_populates="needs")


class CareRequestSelectedDay(TimestampMixin, db.Model):
    __tablename__ = "care_request_selected_days"

    request_id = db.Column(db.Integer, db.ForeignKey("care_requests.id"), nullable=False, index=True)
    value = db.Column(db.String(80), nullable=False)
    care_request = db.relationship("CareRequest", back_populates="selected_days")


class CareOffer(TimestampMixin, db.Model):
    __tablename__ = "care_offers"
    __table_args__ = (db.UniqueConstraint("request_id", "caregiver_id", name="uq_request_caregiver_offer"),)

    request_id = db.Column(db.Integer, db.ForeignKey("care_requests.id"), nullable=True, index=True)
    caregiver_id = db.Column(db.Integer, db.ForeignKey("caregiver_profiles.id"), nullable=False, index=True)
    family_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(30), default="suggested", nullable=False, index=True)
    proposed_rate = db.Column(db.Integer)
    message = db.Column(db.Text, default="", nullable=False)

    care_request = db.relationship("CareRequest", back_populates="offers")
    caregiver = db.relationship("CaregiverProfile")
    family_user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "requestId": self.request_id,
            "status": self.status,
            "proposedRate": self.proposed_rate,
            "message": self.message,
            "caregiver": self.caregiver.to_card_dict(),
            **self.timestamps_dict(),
        }
