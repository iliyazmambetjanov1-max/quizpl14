#!/usr/bin/env bash
# Render build script
pip install -r requirements.txt

# Initialize database and create admin user
python -c "
from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash
import os
app = create_app()
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        pwd = os.environ.get('ADMIN_PASSWORD', 'admin123')
        admin = User(username='admin', password_hash=generate_password_hash(pwd), role='admin')
        db.session.add(admin)
        db.session.commit()
        print('Admin user created')
    else:
        print('Admin user exists')
"
