
import os
import click
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from config import Config

db = SQLAlchemy()
socketio = SocketIO()
login_manager = LoginManager()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему.'
login_manager.login_message_category = 'warning'


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='threading'
    )
    login_manager.init_app(app)

    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.game.routes import game_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(game_bp)

    from app.sockets import events  # noqa: F401

    @app.cli.command('create-admin')
    @click.option(
        '--username',
        default='admin',
        prompt='Логин администратора'
    )
    @click.option(
        '--password',
        prompt='Пароль',
        hide_input=True,
        confirmation_prompt=True
    )
    def create_admin(username, password):
        """Создать администратора."""
        from app.models import User

        with app.app_context():
            db.create_all()

            if User.query.filter_by(username=username).first():
                click.echo(
                    f'Пользователь "{username}" уже существует.'
                )
                return

            admin = User(
                username=username,
                password_hash=generate_password_hash(password),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            click.echo(f'Администратор "{username}" создан!')

    with app.app_context():
        db.create_all()

        username = os.environ.get('BOOTSTRAP_ADMIN_USERNAME')
        password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')

        if username and password:
            from app.models import User

            user = User.query.filter_by(username=username).first()

            if not user:
                user = User(
                    username=username,
                    password_hash=generate_password_hash(password),
                    role='admin'
                )
                db.session.add(user)
                db.session.commit()

    return app
