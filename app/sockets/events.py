
from flask import request, current_app
from flask_socketio import emit, join_room
from app import socketio, db
from app.models import GameSession, Player, Question
import time
import secrets
import threading


question_start_times = {}
host_connections = {}

# Защита от повторного завершения одного вопроса.
completed_questions = set()
completion_lock = threading.Lock()


def question_key(game_session):
    return (
        game_session.id,
        game_session.current_question_index
    )


def mark_question_completed(game_session):
    key = question_key(game_session)

    with completion_lock:
        if key in completed_questions:
            return False

        completed_questions.add(key)
        return True


def is_question_completed(game_session):
    with completion_lock:
        return question_key(game_session) in completed_questions


def get_authorized_host(data):
    if not isinstance(data, dict):
        emit('error', {'message': 'Некорректный запрос.'})
        return None

    pin = str(data.get('pin', '')).strip()
    game_session = GameSession.query.filter_by(pin=pin).first()

    if not game_session:
        emit('error', {'message': 'Сессия не найдена.'})
        return None

    if host_connections.get(request.sid) != game_session.id:
        emit('error', {'message': 'Нет прав ведущего.'})
        return None

    return game_session


def get_questions(game_session):
    return game_session.quiz.questions.order_by(
        Question.order_index
    ).all()


def get_current_question(game_session):
    questions = get_questions(game_session)
    index = game_session.current_question_index

    if 0 <= index < len(questions):
        return questions[index]

    return None


def finish_question(game_session):
    question = get_current_question(game_session)

    if question is None:
        return False

    if not mark_question_completed(game_session):
        return False

    players = Player.query.filter_by(
        session_id=game_session.id
    ).all()

    for player in players:
        if not player.answered_current:
            player.answered_current = True

            if player.socket_id:
                socketio.emit('answer_result', {
                    'is_correct': False,
                    'correct_option': question.correct_option,
                    'points_earned': 0,
                    'total_score': player.score,
                    'timed_out': True
                }, to=player.socket_id)

    db.session.commit()

    socketio.emit('answer_progress', {
        'answered': len(players),
        'total': len(players)
    }, to=game_session.pin)

    _send_leaderboard(game_session, question)

    return True


def _question_timer(
    app,
    session_id,
    question_index,
    start_time,
    pin,
    time_limit
):
    remaining = max(
        0,
        time_limit - (time.time() - start_time)
    )

    socketio.sleep(remaining)

    with app.app_context():
        game_session = db.session.get(
            GameSession,
            session_id
        )

        if not game_session:
            return

        if game_session.state != 'active':
            return

        if game_session.current_question_index != question_index:
            return

        if is_question_completed(game_session):
            return

        if question_start_times.get(session_id) != start_time:
            return

        finish_question(game_session)


@socketio.on('join_room')
def handle_join_room(data):
    if not isinstance(data, dict):
        emit('error', {'message': 'Некорректный запрос.'})
        return

    pin = str(data.get('pin', '')).strip()
    nickname = str(data.get('nickname', '')).strip()

    if not pin or not nickname:
        emit('error', {'message': 'PIN и никнейм обязательны.'})
        return

    if len(nickname) > 64:
        emit('error', {'message': 'Никнейм слишком длинный.'})
        return

    game_session = GameSession.query.filter_by(pin=pin).first()

    if not game_session:
        emit('error', {'message': 'Комната не найдена.'})
        return

    if game_session.state == 'finished':
        emit('error', {'message': 'Игра уже завершена.'})
        return

    existing = Player.query.filter_by(
        session_id=game_session.id,
        nickname=nickname
    ).first()

    if existing:
        existing.socket_id = request.sid
        db.session.commit()
        player = existing
    else:
        player = Player(
            session_id=game_session.id,
            nickname=nickname,
            socket_id=request.sid,
            score=0
        )

        db.session.add(player)
        db.session.commit()

    join_room(pin)

    emit('joined', {
        'player_id': player.id,
        'nickname': player.nickname,
        'session_state': game_session.state,
        'player_count': game_session.players.count(),
        'answered_current': player.answered_current
    })

    if game_session.state == 'active':
        question = get_current_question(game_session)

        if question:
            start_time = question_start_times.get(
                game_session.id
            )

            remaining = None

            if start_time is not None:
                remaining = max(
                    0,
                    question.time_limit - (
                        time.time() - start_time
                    )
                )

            if player.answered_current:
                emit('answer_result', {
                    'is_correct': False,
                    'correct_option': question.correct_option,
                    'points_earned': 0,
                    'total_score': player.score,
                    'already_answered': True
                })
            elif is_question_completed(game_session):
                emit('question_timeout', {
                    'correct_option': question.correct_option
                })
            else:
                emit('question_start', {
                    'question_index': game_session.current_question_index,
                    'total_questions': len(get_questions(game_session)),
                    'question': question.to_dict(reveal=False),
                    'remaining_time': remaining
                })

    if not existing:
        emit('player_joined', {
            'nickname': nickname,
            'player_count': game_session.players.count()
        }, to=pin)


@socketio.on('host_join')
def handle_host_join(data):
    if not isinstance(data, dict):
        emit('error', {'message': 'Некорректный запрос.'})
        return

    pin = str(data.get('pin', '')).strip()
    host_token = str(data.get('host_token', '')).strip()

    game_session = GameSession.query.filter_by(pin=pin).first()

    if not game_session:
        emit('error', {'message': 'Сессия не найдена.'})
        return

    if not host_token or not secrets.compare_digest(
        host_token,
        game_session.host_token
    ):
        emit('error', {'message': 'Неверный ключ ведущего.'})
        return

    host_connections[request.sid] = game_session.id
    join_room(pin)

    response = {
        'pin': pin,
        'player_count': game_session.players.count(),
        'quiz_title': game_session.quiz.title,
        'state': game_session.state
    }

    if game_session.state == 'active':
        question = get_current_question(game_session)

        if question:
            start_time = question_start_times.get(
                game_session.id
            )

            if (
                start_time is None
                and not is_question_completed(game_session)
            ):
                _send_question(game_session)
                start_time = question_start_times.get(
                    game_session.id
                )

            remaining = None

            if start_time is not None:
                remaining = max(
                    0,
                    question.time_limit - (
                        time.time() - start_time
                    )
                )

            response['question'] = question.to_dict(
                reveal=False
            )
            response['question_index'] = (
                game_session.current_question_index
            )
            response['total_questions'] = len(
                get_questions(game_session)
            )
            response['remaining_time'] = remaining
            response['question_completed'] = (
                is_question_completed(game_session)
            )

            if response['question_completed']:
                response['leaderboard'] = [
                    player.to_dict()
                    for player in game_session.get_leaderboard(top=5)
                ]

                response['correct_option'] = question.correct_option

    emit('host_joined', response)


@socketio.on('start_game')
def handle_start_game(data):
    game_session = get_authorized_host(data)

    if not game_session or game_session.state != 'lobby':
        return

    questions = get_questions(game_session)

    if not questions:
        emit('error', {
            'message': 'В викторине нет вопросов.'
        })
        return

    game_session.state = 'active'
    game_session.current_question_index = 0

    Player.query.filter_by(
        session_id=game_session.id
    ).update({'answered_current': False})

    db.session.commit()

    _send_question(game_session)


@socketio.on('next_question')
def handle_next_question(data):
    game_session = get_authorized_host(data)

    if not game_session or game_session.state != 'active':
        return

    question = get_current_question(game_session)

    if question is None:
        return

    start_time = question_start_times.get(
        game_session.id
    )

    answered = Player.query.filter_by(
        session_id=game_session.id,
        answered_current=True
    ).count()

    total = game_session.players.count()

    time_finished = (
        start_time is not None
        and time.time() - start_time >= question.time_limit
    )

    if answered < total and not time_finished:
        emit('error', {
            'message': 'Дождитесь ответов игроков или окончания времени.'
        })
        return

    if time_finished:
        finish_question(game_session)
    else:
        mark_question_completed(game_session)

    game_session.current_question_index += 1

    questions = get_questions(game_session)

    if game_session.current_question_index >= len(questions):
        game_session.state = 'finished'
        db.session.commit()

        question_start_times.pop(game_session.id, None)

        leaderboard = [
            player.to_dict()
            for player in game_session.get_leaderboard(top=10)
        ]

        socketio.emit('game_over', {
            'leaderboard': leaderboard
        }, to=game_session.pin)

        return

    Player.query.filter_by(
        session_id=game_session.id
    ).update({'answered_current': False})

    db.session.commit()

    _send_question(game_session)


@socketio.on('submit_answer')
def handle_submit_answer(data):
    if not isinstance(data, dict):
        return

    pin = str(data.get('pin', '')).strip()
    answer = str(data.get('answer', '')).lower().strip()

    if answer not in ['a', 'b', 'c', 'd']:
        return

    game_session = GameSession.query.filter_by(pin=pin).first()

    if not game_session or game_session.state != 'active':
        return

    try:
        player_id = int(data.get('player_id'))
    except (ValueError, TypeError):
        return

    player = db.session.get(Player, player_id)

    if (
        not player
        or player.session_id != game_session.id
        or player.socket_id != request.sid
        or player.answered_current
    ):
        return

    question = get_current_question(game_session)

    if not question:
        return

    if is_question_completed(game_session):
        return

    start_time = question_start_times.get(
        game_session.id
    )

    if start_time is None:
        return

    elapsed = time.time() - start_time

    if elapsed >= question.time_limit:
        finish_question(game_session)
        return

    is_correct = answer == question.correct_option

    ratio = min(
        elapsed / question.time_limit,
        1.0
    )

    points = (
        int(max(500, 1000 - ratio * 500))
        if is_correct else 0
    )

    player.score += points
    player.answered_current = True

    db.session.commit()

    emit('answer_result', {
        'is_correct': is_correct,
        'correct_option': question.correct_option,
        'points_earned': points,
        'total_score': player.score,
        'timed_out': False
    }, to=request.sid)

    answered_count = Player.query.filter_by(
        session_id=game_session.id,
        answered_current=True
    ).count()

    total_count = game_session.players.count()

    emit('answer_progress', {
        'answered': answered_count,
        'total': total_count
    }, to=game_session.pin)

    if total_count > 0 and answered_count >= total_count:
        if mark_question_completed(game_session):
            _send_leaderboard(game_session, question)


@socketio.on('show_leaderboard')
def handle_show_leaderboard(data):
    game_session = get_authorized_host(data)

    if not game_session or game_session.state != 'active':
        return

    question = get_current_question(game_session)

    if not question:
        return

    if is_question_completed(game_session):
        return

    start_time = question_start_times.get(
        game_session.id
    )

    answered = Player.query.filter_by(
        session_id=game_session.id,
        answered_current=True
    ).count()

    total = game_session.players.count()

    time_finished = (
        start_time is not None
        and time.time() - start_time >= question.time_limit
    )

    if time_finished:
        finish_question(game_session)
    elif answered >= total and total > 0:
        if mark_question_completed(game_session):
            _send_leaderboard(game_session, question)
    else:
        emit('error', {
            'message': 'Дождитесь ответов игроков или окончания времени.'
        })


@socketio.on('disconnect')
def handle_disconnect():
    host_connections.pop(request.sid, None)


def _send_question(game_session):
    questions = get_questions(game_session)
    index = game_session.current_question_index

    if not 0 <= index < len(questions):
        return

    question = questions[index]

    question_start_times[game_session.id] = time.time()

    with completion_lock:
        completed_questions.discard(
            (game_session.id, index)
        )

    socketio.emit('question_start', {
        'question_index': index,
        'total_questions': len(questions),
        'question': question.to_dict(reveal=False),
        'remaining_time': question.time_limit
    }, to=game_session.pin)

    app = current_app._get_current_object()

    socketio.start_background_task(
        _question_timer,
        app,
        game_session.id,
        index,
        question_start_times[game_session.id],
        game_session.pin,
        question.time_limit
    )


def _send_leaderboard(game_session, question):
    leaderboard = [
        player.to_dict()
        for player in game_session.get_leaderboard(top=5)
    ]

    socketio.emit('leaderboard', {
        'leaderboard': leaderboard,
        'correct_option': question.correct_option,
        'question_index': game_session.current_question_index
    }, to=game_session.pin)
