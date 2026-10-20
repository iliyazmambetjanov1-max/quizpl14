
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')

# Создаём папку для базы данных, если её ещё нет
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'quizpl14-super-secret-key-change-in-prod'

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or 'sqlite:///' + os.path.join(INSTANCE_DIR, 'quiz.db')
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
