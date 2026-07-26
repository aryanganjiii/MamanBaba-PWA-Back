from flask import Blueprint, g

from app.errors import ApiError
from app.extensions import db
from app.models.care_request import CareRequest
from app.models.payment import Payment
from app.services.auth import role_required
from app.utils.http import get_json_payload, success

bp = Blueprint("payments", __name__, url_prefix="/payments")


@bp.get("")
@role_required("family")
def list_payments():
    items = Payment.query.filter_by(user_id=g.current_user.id).order_by(Payment.created_at.desc()).all()
    return success({"items": [item.to_dict() for item in items]})


@bp.post("")
@role_required("family")
def create_payment():
    payload = get_json_payload()
    request_id = payload.get("requestId")
    amount = int(payload.get("amount") or 0)
    if not amount:
        raise ApiError("مبلغ پرداخت الزامی است.", 422, "missing_amount")
    if request_id:
        care_request = CareRequest.query.filter_by(id=request_id, user_id=g.current_user.id).first()
        if not care_request:
            raise ApiError("درخواست مراقبت پیدا نشد.", 404, "care_request_not_found")
    payment = Payment(
        user_id=g.current_user.id,
        request_id=request_id,
        amount=amount,
        status="initiated",
        provider=payload.get("provider", "manual"),
    )
    db.session.add(payment)
    db.session.commit()
    return success(payment.to_dict(), status=201)


@bp.post("/<int:payment_id>/mark-paid")
@role_required("family")
def mark_paid(payment_id):
    payment = Payment.query.filter_by(id=payment_id, user_id=g.current_user.id).first()
    if not payment:
        raise ApiError("پرداخت پیدا نشد.", 404, "payment_not_found")
    payment.status = "paid"
    payment.reference_id = (get_json_payload() or {}).get("referenceId", payment.reference_id)
    if payment.care_request and payment.care_request.status == "pending":
        payment.care_request.status = "active"
    db.session.commit()
    return success(payment.to_dict())
