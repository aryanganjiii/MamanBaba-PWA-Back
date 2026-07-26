from app.extensions import db
from app.models.care_request import CareOffer, CareRequest, CareRequestNeed, CareRequestSelectedDay
from app.models.caregiver import (
    CaregiverAvailableDay,
    CaregiverCollaborationType,
    CaregiverHighlight,
    CaregiverProfile,
    CaregiverReview,
    CaregiverServiceArea,
    CaregiverServiceType,
    CaregiverSkill,
    FavoriteCaregiver,
)
from app.models.communication import Conversation, Message, Notification
from app.models.payment import Payment
from app.models.user import Address, User


def _set_values(model, attr, values):
    setattr(model, attr, [])
    return [value for value in values]


def _add_caregiver(
    slug,
    full_name,
    image_url,
    experience_years,
    hourly_rate,
    response_time,
    rating,
    repeat_hire_count,
    bio,
    skills,
    areas,
    highlights,
    reviews,
):
    caregiver = CaregiverProfile(
        slug=slug,
        full_name=full_name,
        gender="خانم",
        marital_status="سایر",
        province="تهران",
        city="تهران",
        experience_level="۳ تا ۵ سال" if experience_years <= 5 else "بیشتر از ۵ سال",
        experience_years=experience_years,
        hourly_rate=hourly_rate,
        response_time=response_time,
        rating=rating,
        review_count=len(reviews),
        repeat_hire_count=repeat_hire_count,
        bio=bio,
        image_url=image_url,
        verified=True,
        public_status="public",
        can_stay_overnight=True,
        available_on_holidays=False,
    )
    db.session.add(caregiver)
    db.session.flush()

    for value in skills:
        db.session.add(CaregiverSkill(caregiver_id=caregiver.id, value=value))
    for value in ["ساعتی", "روزانه", "شبانه"]:
        db.session.add(CaregiverServiceType(caregiver_id=caregiver.id, value=value))
    for value in ["یک‌باره", "مستمر"]:
        db.session.add(CaregiverCollaborationType(caregiver_id=caregiver.id, value=value))
    for value in ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه"]:
        db.session.add(CaregiverAvailableDay(caregiver_id=caregiver.id, value=value))
    for value in areas:
        db.session.add(CaregiverServiceArea(caregiver_id=caregiver.id, value=value))
    for title, description in highlights:
        db.session.add(CaregiverHighlight(caregiver_id=caregiver.id, title=title, description=description))
    for author, text in reviews:
        db.session.add(
            CaregiverReview(
                caregiver_id=caregiver.id,
                author_name=author,
                rating=5,
                text=text,
                display_date="۲ هفته پیش",
            )
        )
    return caregiver


def seed_database(reset=False):
    if reset:
        db.drop_all()
        db.create_all()

    if User.query.filter_by(phone="09121234567").first():
        return {"seeded": False, "message": "Seed data already exists."}

    family = User(
        phone="09121234567",
        role="family",
        full_name="محمد مطیعیان",
        first_name="محمد",
        city="تهران",
        neighborhood="سعادت‌آباد",
        avatar_url="/images/user-profile.jpg",
        is_verified=True,
    )
    db.session.add(family)
    db.session.flush()
    family.add_role("family")

    db.session.add(
        Address(
            user_id=family.id,
            label="خانه",
            province="تهران",
            city="تهران",
            neighborhood="سعادت‌آباد",
            address_line="تهران، سعادت‌آباد",
            is_default=True,
        )
    )

    caregivers = [
        _add_caregiver(
            "maryam-ahmadi",
            "مریم احمدی",
            "/images/caregivers/maryam.jpg",
            5,
            240000,
            "کمتر از ۱ ساعت",
            4.9,
            5,
            "با صبوری و دلسوزی در کنار سالمندان هستم تا خانواده‌ها با آرامش بیشتری برنامه مراقبت را مدیریت کنند.",
            ["همراهی و هم‌صحبتی", "یادآوری دارو", "کمک در بهداشت فردی", "تهیه غذا", "مراقبت شخصی"],
            ["پاسداران", "دروس", "قلهک", "اختیاریه", "منطقه ۱"],
            [
                ("همکاری مجدد خانواده‌ها", "۵ خانواده برای مراقبت مجدد از ایشان درخواست ثبت کرده‌اند."),
                ("احراز هویت تکمیل‌شده", "اطلاعات هویتی این مراقب توسط تیم بررسی شده است."),
            ],
            [
                ("سارا محمدی", "خانم احمدی بسیار صبور و خوش‌برخورد بودند."),
                ("علی رضایی", "منظم، دلسوز و قابل اعتماد هستند."),
            ],
        ),
        _add_caregiver(
            "fatemeh-karimi",
            "فاطمه کریمی",
            "/images/caregivers/fatemeh.jpg",
            3,
            210000,
            "حدود ۲ ساعت",
            4.8,
            3,
            "تجربه من بیشتر در همراهی سالمندان و انجام امور روزانه است.",
            ["کارهای خانه", "همراهی سالمند", "تهیه غذای سبک", "پیاده‌روی روزانه", "یادآوری دارو"],
            ["ستارخان", "صادقیه", "گیشا", "مرزداران", "منطقه ۲"],
            [("تجربه همراهی روزانه", "مناسب سالمندانی که به همراهی سبک و منظم نیاز دارند.")],
            [("مینا یوسفی", "برای انجام امور روزانه پدرم همکاری خوبی داشتند.")],
        ),
        _add_caregiver(
            "zahra-rahimi",
            "زهرا رحیمی",
            "/images/caregivers/zahra.jpg",
            7,
            280000,
            "کمتر از ۱ ساعت",
            5.0,
            8,
            "در کنار رسیدگی به امور روزانه، حفظ روحیه و استقلال سالمند برای من مهم است.",
            ["مراقبت شخصی", "اندازه‌گیری علائم حیاتی", "همراهی پزشکی", "کمک حرکتی", "یادآوری دارو"],
            ["ونک", "میرداماد", "جردن", "یوسف‌آباد", "منطقه ۳"],
            [("سابقه همکاری بالا", "۸ خانواده برای همکاری مجدد با ایشان درخواست ثبت کرده‌اند.")],
            [("نگار شریفی", "تجربه و آرامش ایشان باعث شد خیال ما راحت باشد.")],
        ),
        _add_caregiver(
            "elham-mousavi",
            "الهام موسوی",
            "/images/caregivers/elham.jpg",
            4,
            225000,
            "حدود ۳ ساعت",
            4.7,
            2,
            "با علاقه در کنار سالمندان هستم و تلاش می‌کنم کارهای روزمره با آرامش انجام شود.",
            ["همراهی روزانه", "خرید منزل", "تهیه غذا", "پیاده‌روی", "هم‌صحبتی"],
            ["شهرک غرب", "سعادت‌آباد", "ایوانک", "فرحزاد", "منطقه ۲"],
            [("مناسب همراهی روزانه", "انتخاب مناسب برای امور روزانه، خرید و همراهی خارج از منزل.")],
            [("رضا منصوری", "خوش‌قول و خوش‌اخلاق بودند.")],
        ),
    ]

    request = CareRequest(
        user_id=family.id,
        province="تهران",
        city="تهران",
        neighborhood="سعادت‌آباد",
        person="مادر",
        age_range="۷۰ تا ۷۹ سال",
        gender="خانم",
        physical_status="به همراهی و کمک سبک نیاز دارد",
        care_notes="نیاز به یادآوری دارو و همراهی روزانه دارد.",
        presence_type="روزانه",
        recurrence_type="مستمر",
        start_date="1405/04/20",
        start_time="09:00",
        end_time="18:00",
        end_date_mode="نامشخص",
        budget_amount=250,
        status="active",
        title="مراقبت روزانه سالمند",
        service_type="مراقبت در منزل",
    )
    db.session.add(request)
    db.session.flush()

    for value in ["کارهای خانه", "مراقبت شخصی", "همراهی و هم‌صحبتی"]:
        db.session.add(CareRequestNeed(request_id=request.id, value=value))
    for value in ["شنبه", "دوشنبه", "چهارشنبه"]:
        db.session.add(CareRequestSelectedDay(request_id=request.id, value=value))
    for caregiver in caregivers[:3]:
        db.session.add(
            CareOffer(
                request_id=request.id,
                caregiver_id=caregiver.id,
                family_user_id=family.id,
                status="suggested",
                proposed_rate=caregiver.hourly_rate,
            )
        )

    db.session.add(
        CareRequest(
            user_id=family.id,
            province="تهران",
            city="تهران",
            neighborhood="ونک",
            person="پدر",
            age_range="۸۰ تا ۸۹ سال",
            gender="آقا",
            physical_status="به کمک منظم نیاز دارد",
            presence_type="ساعتی",
            recurrence_type="یک‌باره",
            start_date="1405/04/21",
            start_time="10:00",
            end_time="13:00",
            budget_amount=300,
            status="pending",
            title="همراهی برای ویزیت پزشک",
            service_type="همراهی بیرون از منزل",
        )
    )

    db.session.add(FavoriteCaregiver(user_id=family.id, caregiver_id=caregivers[0].id))
    db.session.add(FavoriteCaregiver(user_id=family.id, caregiver_id=caregivers[2].id))

    db.session.add_all(
        [
            Notification(
                user_id=family.id,
                title="درخواست شما در حال بررسی است",
                description="۳ مراقب مناسب برای درخواست مراقبت روزانه پیدا شد.",
                time_label="۱۰ دقیقه پیش",
                is_read=False,
                type="request",
            ),
            Notification(
                user_id=family.id,
                title="پیام جدید از مریم احمدی",
                description="مریم احمدی برای درخواست شما پیام ارسال کرده است.",
                time_label="۳۰ دقیقه پیش",
                is_read=False,
                type="message",
            ),
            Notification(
                user_id=family.id,
                title="یادآوری پرداخت",
                description="برای تایید همراهی ویزیت پزشک، پرداخت را تکمیل کنید.",
                time_label="دیروز",
                is_read=True,
                type="payment",
            ),
        ]
    )

    conversation = Conversation(
        family_user_id=family.id,
        caregiver_id=caregivers[0].id,
        type="caregiver",
        role_label="مراقب سالمند",
        unread_for_family=2,
        online=True,
    )
    support = Conversation(
        family_user_id=family.id,
        type="support",
        title="پشتیبانی مامان بابا",
        role_label="پشتیبانی",
        unread_for_family=0,
        online=True,
    )
    db.session.add_all([conversation, support])
    db.session.flush()
    db.session.add_all(
        [
            Message(conversation_id=conversation.id, sender_type="family", body="سلام، وقت بخیر.", time_label="۱۲:۲۰"),
            Message(
                conversation_id=conversation.id,
                sender_type="caregiver",
                body="سلام، من برای درخواست مراقبت روزانه آماده‌ام.",
                time_label="۱۲:۳۰",
            ),
            Message(
                conversation_id=support.id,
                sender_type="support",
                body="درخواست شما با موفقیت ثبت شد. در صورت نیاز با ما در ارتباط باشید.",
                time_label="دیروز",
            ),
        ]
    )

    db.session.add(Payment(user_id=family.id, request_id=request.id, amount=250000, status="initiated"))
    db.session.commit()
    return {"seeded": True, "familyPhone": family.phone, "caregivers": len(caregivers)}
