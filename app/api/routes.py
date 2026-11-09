import secrets

from flask import Blueprint, jsonify, request

from app import db
from app.models import Quiz, Question


api_bp = Blueprint("api", __name__, url_prefix="/api")


def api_error(message, status):
    return jsonify({"error": message}), status


def get_owner_token():
    return request.headers.get("X-Quiz-Owner-Token", "").strip()


def can_manage_quiz(quiz):
    token = get_owner_token()

    if not token or not quiz.owner_token:
        return False

    return secrets.compare_digest(token, quiz.owner_token)


def require_quiz_owner(quiz):
    if not can_manage_quiz(quiz):
        return api_error("Нет доступа к этой викторине", 403)

    return None


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "QuizPL14 API"
    })


@api_bp.route("/quizzes", methods=["POST"])
def create_quiz():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return api_error("Ожидается JSON-объект", 400)

    title = data.get("title")

    if not isinstance(title, str) or not title.strip():
        return api_error("Укажите название викторины", 400)

    title = title.strip()

    if len(title) > 128:
        return api_error(
            "Название не должно превышать 128 символов",
            400
        )

    quiz = Quiz(
        title=title,
        creator_id=None
    )

    db.session.add(quiz)
    db.session.commit()

    return jsonify({
        "message": "Викторина создана",
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "question_count": 0
        },
        "owner_token": quiz.owner_token
    }), 201


@api_bp.route("/quizzes/<int:quiz_id>", methods=["GET"])
def get_quiz(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)

    if quiz is None:
        return api_error("Викторина не найдена", 404)

    error = require_quiz_owner(quiz)

    if error:
        return error

    questions = (
        quiz.questions
        .order_by(Question.order_index)
        .all()
    )

    return jsonify({
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "questions": [
                question.to_dict(reveal=False)
                for question in questions
            ]
        }
    })


@api_bp.route(
    "/quizzes/<int:quiz_id>/questions",
    methods=["POST"]
)
def create_question(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)

    if quiz is None:
        return api_error("Викторина не найдена", 404)

    error = require_quiz_owner(quiz)

    if error:
        return error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return api_error("Ожидается JSON-объект", 400)

    question_text = data.get("question_text")

    options = [
        data.get("option_a"),
        data.get("option_b"),
        data.get("option_c"),
        data.get("option_d")
    ]

    correct_option = data.get("correct_option")

    if not isinstance(question_text, str) or not question_text.strip():
        return api_error("Введите текст вопроса", 400)

    if not all(
        isinstance(option, str) and option.strip()
        for option in options
    ):
        return api_error(
            "Заполните все четыре варианта ответа",
            400
        )

    if correct_option not in ["a", "b", "c", "d"]:
        return api_error(
            "Правильный ответ должен быть a, b, c или d",
            400
        )

    try:
        time_limit = int(data.get("time_limit", 20))
    except (ValueError, TypeError):
        return api_error("Неверное время ответа", 400)

    if not 5 <= time_limit <= 120:
        return api_error(
            "Время должно быть от 5 до 120 секунд",
            400
        )

    last_order = (
        db.session.query(db.func.max(Question.order_index))
        .filter_by(quiz_id=quiz.id)
        .scalar()
    )

    question = Question(
        quiz_id=quiz.id,
        question_text=question_text.strip(),
        option_a=options[0].strip(),
        option_b=options[1].strip(),
        option_c=options[2].strip(),
        option_d=options[3].strip(),
        correct_option=correct_option,
        time_limit=time_limit,
        order_index=(
            last_order + 1
            if last_order is not None
            else 0
        )
    )

    db.session.add(question)
    db.session.commit()

    return jsonify({
        "message": "Вопрос успешно добавлен",
        "question": {
            "id": question.id,
            "question_text": question.question_text,
            "correct_option": question.correct_option,
            "time_limit": question.time_limit
        }
    }), 201


@api_bp.route(
    "/questions/<int:question_id>",
    methods=["PUT"]
)
def update_question(question_id):
    question = db.session.get(Question, question_id)

    if question is None:
        return api_error("Вопрос не найден", 404)

    quiz = db.session.get(Quiz, question.quiz_id)

    if quiz is None:
        return api_error("Викторина не найдена", 404)

    error = require_quiz_owner(quiz)

    if error:
        return error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return api_error("Ожидается JSON-объект", 400)

    text = data.get("question_text", question.question_text)

    if not isinstance(text, str) or not text.strip():
        return api_error(
            "Текст вопроса не может быть пустым",
            400
        )

    question.question_text = text.strip()

    for key in [
        "option_a",
        "option_b",
        "option_c",
        "option_d"
    ]:
        value = data.get(key, getattr(question, key))

        if not isinstance(value, str) or not value.strip():
            return api_error(
                "Все варианты ответа должны быть заполнены",
                400
            )

        setattr(question, key, value.strip())

    correct = data.get(
        "correct_option",
        question.correct_option
    )

    if correct not in ["a", "b", "c", "d"]:
        return api_error("Неверный правильный ответ", 400)

    question.correct_option = correct

    try:
        time_limit = int(
            data.get("time_limit", question.time_limit)
        )
    except (ValueError, TypeError):
        return api_error("Неверное время ответа", 400)

    if not 5 <= time_limit <= 120:
        return api_error(
            "Время должно быть от 5 до 120 секунд",
            400
        )

    question.time_limit = time_limit

    db.session.commit()

    return jsonify({
        "message": "Вопрос обновлён"
    })


@api_bp.route(
    "/questions/<int:question_id>",
    methods=["DELETE"]
)
def delete_question(question_id):
    question = db.session.get(Question, question_id)

    if question is None:
        return api_error("Вопрос не найден", 404)

    quiz = db.session.get(Quiz, question.quiz_id)

    if quiz is None:
        return api_error("Викторина не найдена", 404)

    error = require_quiz_owner(quiz)

    if error:
        return error

    db.session.delete(question)
    db.session.commit()

    return jsonify({
        "message": "Вопрос удалён"
    })