
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')

# Создаём папку для локальной базы данных
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Config:

    # Секретный ключ Flask
    SECRET_KEY = os.environ.get('SECRET_KEY')

    if not SECRET_KEY:
        SECRET_KEY = 'dev-only-change-this-secret-key'

    # Подключение к базе данных
    DATABASE_URL = os.environ.get('DATABASE_URL')

    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace(
            'postgres://',
            'postgresql://',
            1
        )

    SQLALCHEMY_DATABASE_URI = (
        DATABASE_URL
        or 'sqlite:///' + os.path.join(INSTANCE_DIR, 'quiz.db')
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Режим отладки
    DEBUG = (
        os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    )
