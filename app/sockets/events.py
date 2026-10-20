from flask import request
from flask_socketio import emit, join_room, leave_room
from app import socketio, db
from app.models import GameSession, Player, Question
import time

# Словарь для отслеживания таймеров вопросов: {session_id: start_time}
question_start_times = {}


# ─────────────────────────────────────────────
#  УЧАСТНИК: Подключение к комнате по PIN
# ─────────────────────────────────────────────
@socketio.on('join_room')
def handle_join_room(data):
    """
    data: { pin: '123456', nickname: 'Игрок1' }
    """
    pin = data.get('pin', '').strip()
    nickname = data.get('nickname', '').strip()

    if not pin or not nickname:
        emit('error', {'message': 'PIN и никнейм обязательны.'})
        return

    session = GameSession.query.filter_by(pin=pin).first()
    if not session:
        emit('error', {'message': 'Комната с таким PIN не найдена.'})
        return

    if session.state == 'finished':
        emit('error', {'message': 'Игра уже завершена.'})
        return

    # Проверка на дублирующийся никнейм
    existing = Player.query.filter_by(session_id=session.id, nickname=nickname).first()
    if existing:
        # Обновим socket_id, если тот же игрок переподключился
        existing.socket_id = request.sid
        db.session.commit()
        join_room(pin)
        emit('joined', {
            'player_id': existing.id,
            'nickname': existing.nickname,
            'session_state': session.state,
            'player_count': session.players.count()
        })
        return

    player = Player(
        session_id=session.id,
        nickname=nickname,
        socket_id=request.sid,
        score=0
    )
    db.session.add(player)
    db.session.commit()

    join_room(pin)

    # Подтверждение участнику
    emit('joined', {
        'player_id': player.id,
        'nickname': player.nickname,
        'session_state': session.state,
        'player_count': session.players.count()
    })

    # Уведомить всех в лобби о новом игроке
    player_count = session.players.count()
    emit('player_joined', {
        'nickname': nickname,
        'player_count': player_count
    }, to=pin)


# ─────────────────────────────────────────────
#  ВЕДУЩИЙ: Подключение к комнате как ведущий
# ─────────────────────────────────────────────
@socketio.on('host_join')
def handle_host_join(data):
    """
    data: { pin: '123456' }
    """
    pin = data.get('pin', '').strip()
    session = GameSession.query.filter_by(pin=pin).first()
    if not session:
        emit('error', {'message': 'Сессия не найдена.'})
        return
    join_room(pin)
    emit('host_joined', {
        'pin': pin,
        'player_count': session.players.count(),
        'quiz_title': session.quiz.title
    })


# ─────────────────────────────────────────────
#  ВЕДУЩИЙ: Запуск игры
# ─────────────────────────────────────────────
@socketio.on('start_game')
def handle_start_game(data):
    """
    data: { pin: '123456' }
    """
    pin = data.get('pin', '').strip()
    session = GameSession.query.filter_by(pin=pin).first()
    if not session or session.state != 'lobby':
        return

    session.state = 'active'
    session.current_question_index = 0
    db.session.commit()

    _send_question(session, pin)


# ─────────────────────────────────────────────
#  ВЕДУЩИЙ: Следующий вопрос
# ─────────────────────────────────────────────
@socketio.on('next_question')
def handle_next_question(data):
    pin = data.get('pin', '').strip()
    session = GameSession.query.filter_by(pin=pin).first()
    if not session or session.state != 'active':
        return

    session.current_question_index += 1
    db.session.commit()

    questions = session.quiz.questions.order_by(Question.order_index).all()
    if session.current_question_index >= len(questions):
        # Игра окончена
        session.state = 'finished'
        db.session.commit()
        leaderboard = [p.to_dict() for p in session.get_leaderboard(top=10)]
        emit('game_over', {'leaderboard': leaderboard}, to=pin)
    else:
        # Сбросить флаги "ответил"
        Player.query.filter_by(session_id=session.id).update({'answered_current': False})
        db.session.commit()
        _send_question(session, pin)


# ─────────────────────────────────────────────
#  УЧАСТНИК: Отправка ответа
# ─────────────────────────────────────────────
@socketio.on('submit_answer')
def handle_submit_answer(data):
    """
    data: { pin, player_id, answer: 'a'/'b'/'c'/'d' }
    """
    pin = data.get('pin', '').strip()
    player_id = data.get('player_id')
    answer = data.get('answer', '').lower()

    session = GameSession.query.filter_by(pin=pin).first()
    if not session or session.state != 'active':
        return

    player = Player.query.get(player_id)
    if not player or player.answered_current:
        return  # Уже ответил

    questions = session.quiz.questions.order_by(Question.order_index).all()
    if session.current_question_index >= len(questions):
        return

    question = questions[session.current_question_index]
    is_correct = (answer == question.correct_option)

    # Подсчёт очков по скорости ответа
    start_time = question_start_times.get(session.id, time.time())
    elapsed_ms = (time.time() - start_time) * 1000
    time_limit_ms = question.time_limit * 1000

    if is_correct:
        ratio = min(elapsed_ms / time_limit_ms, 1.0)
        points = int(max(500, 1000 - ratio * 500))
    else:
        points = 0

    player.score += points
    player.answered_current = True
    db.session.commit()

    # Ответ только отправившему игроку
    emit('answer_result', {
        'is_correct': is_correct,
        'correct_option': question.correct_option,
        'points_earned': points,
        'total_score': player.score,
    })

    # Уведомить ведущего о прогрессе
    answered_count = Player.query.filter_by(session_id=session.id, answered_current=True).count()
    total_count = session.players.count()

    emit('answer_progress', {
        'answered': answered_count,
        'total': total_count
    }, to=pin)

    # Если все ответили — отправить лидерборд автоматически
    if answered_count >= total_count:
        _send_leaderboard(session, pin, question)


# ─────────────────────────────────────────────
#  ВЕДУЩИЙ: Принудительно показать лидерборд
# ─────────────────────────────────────────────
@socketio.on('show_leaderboard')
def handle_show_leaderboard(data):
    pin = data.get('pin', '').strip()
    session = GameSession.query.filter_by(pin=pin).first()
    if not session:
        return

    questions = session.quiz.questions.order_by(Question.order_index).all()
    if session.current_question_index < len(questions):
        question = questions[session.current_question_index]
        _send_leaderboard(session, pin, question)


# ─────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────
def _send_question(session, pin):
    questions = session.quiz.questions.order_by(Question.order_index).all()
    idx = session.current_question_index
    question = questions[idx]

    question_start_times[session.id] = time.time()

    emit('question_start', {
        'question_index': idx,
        'total_questions': len(questions),
        'question': question.to_dict(reveal=False),
    }, to=pin)


def _send_leaderboard(session, pin, question):
    leaderboard = [p.to_dict() for p in session.get_leaderboard(top=5)]
    emit('leaderboard', {
        'leaderboard': leaderboard,
        'correct_option': question.correct_option,
        'question_index': session.current_question_index,
    }, to=pin)
