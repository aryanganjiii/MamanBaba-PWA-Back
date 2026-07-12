from flask import jsonify, request

from app.errors import ApiError


def success(data=None, status=200, message=None, meta=None):
    payload = {"data": data if data is not None else {}}
    if message:
        payload["message"] = message
    if meta:
        payload["meta"] = meta
    return jsonify(payload), status


def get_json_payload():
    if not request.is_json:
        raise ApiError("درخواست باید JSON باشد.", 415, "unsupported_media_type")
    return request.get_json(silent=True) or {}


def pagination_params(default_per_page=20, max_per_page=100):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", default_per_page, type=int)
    page = max(page, 1)
    per_page = min(max(per_page, 1), max_per_page)
    return page, per_page


def serialize_pagination(pagination):
    return {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def paginate_query(query, page, per_page):
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page if total else 0
    return items, {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1 and pages > 0,
    }
