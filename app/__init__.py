
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager

from config import Config


db = SQLAlchemy()
socketio = SocketIO()
login_manager = LoginManager()


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    # База данных
    db.init_app(app)

    # Socket.IO
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode="threading"
    )

    # Совместимость с моделями Flask-Login
    login_manager.init_app(app)

    # Регистрация маршрутов
    from app.admin.routes import admin_bp
    from app.game.routes import game_bp
    from app.api.routes import api_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(game_bp)
    app.register_blueprint(api_bp)

    # Socket.IO события
    from app.sockets import events  # noqa: F401

    # Создание таблиц базы данных
    with app.app_context():
        db.create_all()

    return app
