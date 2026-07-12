import os
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


def save_upload(file_storage, folder_name):
    if not file_storage or not file_storage.filename:
        return None

    upload_root = current_app.config["UPLOAD_FOLDER"]
    target_dir = os.path.abspath(os.path.join(upload_root, folder_name))
    os.makedirs(target_dir, exist_ok=True)

    original_name = secure_filename(file_storage.filename) or "upload.bin"
    stored_name = f"{uuid4().hex}_{original_name}"
    path = os.path.join(target_dir, stored_name)
    file_storage.save(path)

    return {
        "original_name": file_storage.filename,
        "stored_name": stored_name,
        "url": f"/uploads/{folder_name}/{stored_name}",
    }
