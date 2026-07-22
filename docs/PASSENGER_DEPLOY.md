# Passenger / cPanel deploy

Use this file as the application startup file:

```text
passenger_wsgi.py
```

The file must import the Flask app from `wsgi.py`:

```python
import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from wsgi import app as application
```

Do not load `passenger_wsgi.py` from inside itself. This pattern is wrong and causes recursive imports:

```python
wsgi = load_source("wsgi", "passenger_wsgi.py")
```

After uploading changes:

```bash
pip install -r requirements.txt
python -m flask --app wsgi init-db
python -m flask --app wsgi seed-db
```

Make sure `.env` is saved as UTF-8 without BOM. The app also reads `.env` with `utf-8-sig`, so a BOM at the beginning of the file will be ignored safely.
