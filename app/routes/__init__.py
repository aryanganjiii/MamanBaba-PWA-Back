from flask import Blueprint

from app.routes.auth import bp as auth_bp
from app.routes.care_requests import bp as care_requests_bp
from app.routes.caregiver_applications import bp as caregiver_applications_bp
from app.routes.caregivers import bp as caregivers_bp
from app.routes.catalog import bp as catalog_bp
from app.routes.conversations import bp as conversations_bp
from app.routes.family import bp as family_bp
from app.routes.notifications import bp as notifications_bp
from app.routes.payments import bp as payments_bp

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

api_bp.register_blueprint(auth_bp)
api_bp.register_blueprint(catalog_bp)
api_bp.register_blueprint(family_bp)
api_bp.register_blueprint(care_requests_bp)
api_bp.register_blueprint(caregivers_bp)
api_bp.register_blueprint(caregiver_applications_bp)
api_bp.register_blueprint(notifications_bp)
api_bp.register_blueprint(conversations_bp)
api_bp.register_blueprint(payments_bp)
