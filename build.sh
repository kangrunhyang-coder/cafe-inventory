#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python -c "
from app import app, init_db
with app.app_context():
    init_db()
"
