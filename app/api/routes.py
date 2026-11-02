
from flask import Blueprint, jsonify, request
from flask_login import current_user
from app import db
from app.models import Quiz, Question

api_bp = Blueprint("api", __name__, url_prefix="/api")


def api_error(message, status):
    return jsonify({"error": message}), status


def require_admin():
    if not current_user.is_authenticated:
        return api_error("Требуется авторизация", 401)

    if current_user.role != "admin":
        return api_error("Недостаточно прав", 403)

    return None


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "QuizPL14 API"
    })


@api_bp.route("/quizzes", methods=["GET"])
def list_quizzes():
    error = require_admin()
    if error:
        return error

    quizzes = (
        Quiz.query
        .filter_by(creator_id=current_user.id)
        .order_by(Quiz.created_at.desc())
        .all()
    )

    return jsonify({
        "quizzes": [
            {
                "id": quiz.id,
                "title": quiz.title,
                "question_count": quiz.question_count(),
                "created_at": (
                    quiz.created_at.isoformat()
                    if quiz.created_at else None
                )
            }
            for quiz in quizzes
        ]
    })


@api_bp.route("/quizzes", methods=["POST"])
def create_quiz():
    error = require_admin()
    if error:
        return error

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return api_error("Ожидается JSON-объект", 400)

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return api_error("Укажите название викторины", 400)

    title = title.strip()
    if len(title) > 128:
        return api_error("Название не должно превышать 128 символов", 400)

    quiz = Quiz(
        title=title,
        creator_id=current_user.id
    )

    db.session.add(quiz)
    db.session.commit()

    return jsonify({
        "message": "Викторина создана",
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "question_count": 0
        }
    }), 201


@api_bp.route("/quizzes/<int:quiz_id>", methods=["GET"])
def get_quiz(quiz_id):
    error = require_admin()
    if error:
        return error

    quiz = db.session.get(Quiz, quiz_id)
    if quiz is None:
        return api_error("Викторина не найдена", 404)

    if quiz.creator_id != current_user.id:
        return api_error("Нет доступа к этой викторине", 403)

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


@api_bp.route("/quizzes/<int:quiz_id>/questions", methods=["POST"])
def create_question(quiz_id):
    error = require_admin()
    if error:
        return error

    quiz = db.session.get(Quiz, quiz_id)

    if quiz is None:
        return api_error("Викторина не найдена", 404)

    if quiz.creator_id != current_user.id:
        return api_error("Нет доступа", 403)

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return api_error("Ожидается JSON-объект", 400)

    question_text = data.get("question_text")
    option_a = data.get("option_a")
    option_b = data.get("option_b")
    option_c = data.get("option_c")
    option_d = data.get("option_d")
    correct_option = data.get("correct_option")

    if not isinstance(question_text, str) or not question_text.strip():
        return api_error("Введите текст вопроса", 400)

    options = [option_a, option_b, option_c, option_d]

    if not all(isinstance(option, str) and option.strip() for option in options):
        return api_error("Заполните все четыре варианта ответа", 400)

    if correct_option not in ["a", "b", "c", "d"]:
        return api_error("Правильный ответ должен быть a, b, c или d", 400)

    try:
        time_limit = int(data.get("time_limit", 20))
    except (ValueError, TypeError):
        return api_error("Неверное время ответа", 400)

    if not 5 <= time_limit <= 120:
        return api_error("Время должно быть от 5 до 120 секунд", 400)

    last_order = (
        db.session.query(db.func.max(Question.order_index))
        .filter_by(quiz_id=quiz.id)
        .scalar()
    )

    question = Question(
        quiz_id=quiz.id,
        question_text=question_text.strip(),
        option_a=option_a.strip(),
        option_b=option_b.strip(),
        option_c=option_c.strip(),
        option_d=option_d.strip(),
        correct_option=correct_option,
        time_limit=time_limit,
        order_index=(last_order + 1) if last_order is not None else 0
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


@api_bp.route("/questions/<int:question_id>", methods=["PUT"])
def update_question(question_id):
    error = require_admin()
    if error:
        return error

    question = db.session.get(Question, question_id)

    if question is None:
        return api_error("Вопрос не найден", 404)

    quiz = db.session.get(Quiz, question.quiz_id)

    if quiz is None or quiz.creator_id != current_user.id:
        return api_error("Нет доступа", 403)

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return api_error("Ожидается JSON-объект", 400)

    text = data.get("question_text", question.question_text)

    if not isinstance(text, str) or not text.strip():
        return api_error("Текст вопроса не может быть пустым", 400)

    question.question_text = text.strip()

    for key in ["option_a", "option_b", "option_c", "option_d"]:
        value = data.get(key, getattr(question, key))

        if not isinstance(value, str) or not value.strip():
            return api_error("Все варианты ответа должны быть заполнены", 400)

        setattr(question, key, value.strip())

    correct = data.get("correct_option", question.correct_option)

    if correct not in ["a", "b", "c", "d"]:
        return api_error("Неверный правильный ответ", 400)

    question.correct_option = correct

    try:
        time_limit = int(data.get("time_limit", question.time_limit))
    except (ValueError, TypeError):
        return api_error("Неверное время ответа", 400)

    if not 5 <= time_limit <= 120:
        return api_error("Время должно быть от 5 до 120 секунд", 400)

    question.time_limit = time_limit

    db.session.commit()

    return jsonify({"message": "Вопрос обновлён"})


@api_bp.route("/questions/<int:question_id>", methods=["DELETE"])
def delete_question(question_id):
    error = require_admin()
    if error:
        return error

    question = db.session.get(Question, question_id)

    if question is None:
        return api_error("Вопрос не найден", 404)

    quiz = db.session.get(Quiz, question.quiz_id)

    if quiz is None or quiz.creator_id != current_user.id:
        return api_error("Нет доступа", 403)

    db.session.delete(question)
    db.session.commit()

    return jsonify({"message": "Вопрос удалён"})
