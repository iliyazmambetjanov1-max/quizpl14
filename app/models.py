from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random
import string


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), default='admin')
    quizzes = db.relationship('Quiz', backref='creator', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', backref='quiz', lazy='dynamic', cascade='all, delete-orphan')
    sessions = db.relationship('GameSession', backref='quiz', lazy='dynamic', cascade='all, delete-orphan')

    def question_count(self):
        return self.questions.count()

    def __repr__(self):
        return f'<Quiz {self.title}>'


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    question_text = db.Column(db.String(512), nullable=False)
    option_a = db.Column(db.String(256), nullable=False)
    option_b = db.Column(db.String(256), nullable=False)
    option_c = db.Column(db.String(256), nullable=False)
    option_d = db.Column(db.String(256), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)  # 'a', 'b', 'c', 'd'
    time_limit = db.Column(db.Integer, default=20)  # секунды
    order_index = db.Column(db.Integer, default=0)

    def to_dict(self, reveal=False):
        data = {
            'id': self.id,
            'question_text': self.question_text,
            'option_a': self.option_a,
            'option_b': self.option_b,
            'option_c': self.option_c,
            'option_d': self.option_d,
            'time_limit': self.time_limit,
        }
        if reveal:
            data['correct_option'] = self.correct_option
        return data

    def __repr__(self):
        return f'<Question {self.id}: {self.question_text[:30]}>'


class GameSession(db.Model):
    __tablename__ = 'game_sessions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    pin = db.Column(db.String(6), unique=True, nullable=False)
    state = db.Column(db.String(16), default='lobby')  # lobby / active / finished
    current_question_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    players = db.relationship('Player', backref='session', lazy='dynamic', cascade='all, delete-orphan')

    @staticmethod
    def generate_pin():
        while True:
            pin = ''.join(random.choices(string.digits, k=6))
            if not GameSession.query.filter_by(pin=pin).first():
                return pin

    def get_leaderboard(self, top=5):
        return (Player.query
                .filter_by(session_id=self.id)
                .order_by(Player.score.desc())
                .limit(top)
                .all())

    def __repr__(self):
        return f'<GameSession PIN={self.pin} state={self.state}>'


class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('game_sessions.id'), nullable=False)
    nickname = db.Column(db.String(64), nullable=False)
    score = db.Column(db.Integer, default=0)
    socket_id = db.Column(db.String(128))
    answered_current = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'score': self.score,
        }

    def __repr__(self):
        return f'<Player {self.nickname} score={self.score}>'
