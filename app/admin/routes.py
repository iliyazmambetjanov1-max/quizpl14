
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session as browser_session
)
from app import db
from app.models import Quiz, Question, GameSession
import secrets

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ==========================================
# ПРОВЕРКА ПРАВ ВЛАДЕЛЬЦА
# ==========================================

def can_manage_quiz(quiz):
    tokens = browser_session.get('quiz_owner_tokens', {})

    token = (
        request.args.get('key')
        or request.form.get('key')
        or request.headers.get('X-Quiz-Owner-Token')
        or tokens.get(str(quiz.id))
    )

    if not token or not secrets.compare_digest(
        str(token),
        str(quiz.owner_token)
    ):
        return False

    tokens[str(quiz.id)] = token
    browser_session['quiz_owner_tokens'] = tokens

    return True


# ==========================================
# ГЛАВНАЯ ПАНЕЛЬ
# ==========================================

@admin_bp.route('/')
def dashboard():
    tokens = browser_session.get('quiz_owner_tokens', {})
    quizzes = []

    if tokens:
        ids = [
            int(quiz_id)
            for quiz_id in tokens.keys()
            if quiz_id.isdigit()
        ]

        if ids:
            found = Quiz.query.filter(
                Quiz.id.in_(ids)
            ).order_by(
                Quiz.created_at.desc()
            ).all()

            quizzes = [
                quiz
                for quiz in found
                if secrets.compare_digest(
                    str(tokens.get(str(quiz.id), '')),
                    str(quiz.owner_token)
                )
            ]

    return render_template(
        'admin/dashboard.html',
        quizzes=quizzes
    )


# ==========================================
# СОЗДАНИЕ ВИКТОРИНЫ
# ==========================================

@admin_bp.route('/quiz/new', methods=['GET', 'POST'])
def quiz_new():

    if request.method == 'POST':

        title = request.form.get(
            'title',
            ''
        ).strip()

        if not title:
            flash(
                'Введите название викторины.',
                'error'
            )

            return render_template(
                'admin/quiz_editor.html',
                quiz=None
            )

        if len(title) > 128:
            flash(
                'Название слишком длинное.',
                'error'
            )

            return render_template(
                'admin/quiz_editor.html',
                quiz=None
            )

        quiz = Quiz(
            title=title,
            creator_id=None,
            owner_token=secrets.token_urlsafe(32)
        )

        db.session.add(quiz)
        db.session.commit()

        tokens = browser_session.get(
            'quiz_owner_tokens',
            {}
        )

        tokens[str(quiz.id)] = quiz.owner_token

        browser_session['quiz_owner_tokens'] = tokens

        flash(
            f'Викторина «{title}» создана!',
            'success'
        )

        return redirect(
            url_for(
                'admin.quiz_edit',
                quiz_id=quiz.id,
                key=quiz.owner_token
            )
        )

    return render_template(
        'admin/quiz_editor.html',
        quiz=None
    )


# ==========================================
# РЕДАКТИРОВАНИЕ ВИКТОРИНЫ
# ==========================================

@admin_bp.route(
    '/quiz/<int:quiz_id>/edit',
    methods=['GET', 'POST']
)
def quiz_edit(quiz_id):

    quiz = db.session.get(
        Quiz,
        quiz_id
    )

    if quiz is None:
        return 'Викторина не найдена', 404

    if not can_manage_quiz(quiz):
        return (
            'Нет доступа. Используйте секретную ссылку владельца.',
            403
        )

    questions = quiz.questions.order_by(
        Question.order_index
    ).all()

    return render_template(
        'admin/quiz_editor.html',
        quiz=quiz,
        questions=questions
    )


# ==========================================
# ДОБАВЛЕНИЕ ВОПРОСА
# ==========================================

@admin_bp.route(
    '/quiz/<int:quiz_id>/question/add',
    methods=['POST']
)
def question_add(quiz_id):

    quiz = db.session.get(
        Quiz,
        quiz_id
    )

    if quiz is None:
        return 'Викторина не найдена', 404

    if not can_manage_quiz(quiz):
        return 'Нет доступа', 403

    q_text = request.form.get(
        'question_text',
        ''
    ).strip()

    opt_a = request.form.get(
        'option_a',
        ''
    ).strip()

    opt_b = request.form.get(
        'option_b',
        ''
    ).strip()

    opt_c = request.form.get(
        'option_c',
        ''
    ).strip()

    opt_d = request.form.get(
        'option_d',
        ''
    ).strip()

    correct = request.form.get(
        'correct_option',
        'a'
    ).lower()

    try:
        time_limit = int(
            request.form.get(
                'time_limit',
                20
            )
        )
    except (ValueError, TypeError):
        flash(
            'Неверное время ответа.',
            'error'
        )

        return redirect(
            url_for(
                'admin.quiz_edit',
                quiz_id=quiz_id,
                key=quiz.owner_token
            )
        )

    if not all([
        q_text,
        opt_a,
        opt_b,
        opt_c,
        opt_d
    ]):
        flash(
            'Заполните все поля вопроса.',
            'error'
        )

        return redirect(
            url_for(
                'admin.quiz_edit',
                quiz_id=quiz_id,
                key=quiz.owner_token
            )
        )

    if correct not in ['a', 'b', 'c', 'd']:
        flash(
            'Выберите правильный вариант ответа.',
            'error'
        )

        return redirect(
            url_for(
                'admin.quiz_edit',
                quiz_id=quiz_id,
                key=quiz.owner_token
            )
        )

    if not 5 <= time_limit <= 120:
        flash(
            'Время должно быть от 5 до 120 секунд.',
            'error'
        )

        return redirect(
            url_for(
                'admin.quiz_edit',
                quiz_id=quiz_id,
                key=quiz.owner_token
            )
        )

    count = quiz.questions.count()

    question = Question(
        quiz_id=quiz_id,
        question_text=q_text,
        option_a=opt_a,
        option_b=opt_b,
        option_c=opt_c,
        option_d=opt_d,
        correct_option=correct,
        time_limit=time_limit,
        order_index=count
    )

    db.session.add(question)
    db.session.commit()

    flash(
        'Вопрос добавлен!',
        'success'
    )

    return redirect(
        url_for(
            'admin.quiz_edit',
            quiz_id=quiz_id,
            key=quiz.owner_token
        )
    )


# ==========================================
# УДАЛЕНИЕ ВОПРОСА
# ==========================================

@admin_bp.route(
    '/quiz/<int:quiz_id>/question/<int:q_id>/delete',
    methods=['POST']
)
def question_delete(quiz_id, q_id):

    quiz = db.session.get(
        Quiz,
        quiz_id
    )

    if quiz is None:
        return 'Викторина не найдена', 404

    if not can_manage_quiz(quiz):
        return 'Нет доступа', 403

    question = db.session.get(
        Question,
        q_id
    )

    if question is None or question.quiz_id != quiz.id:
        return 'Вопрос не найден', 404

    db.session.delete(question)
    db.session.commit()

    flash(
        'Вопрос удалён.',
        'success'
    )

    return redirect(
        url_for(
            'admin.quiz_edit',
            quiz_id=quiz_id,
            key=quiz.owner_token
        )
    )


# ==========================================
# УДАЛЕНИЕ ВИКТОРИНЫ
# ==========================================

@admin_bp.route(
    '/quiz/<int:quiz_id>/delete',
    methods=['POST']
)
def quiz_delete(quiz_id):

    quiz = db.session.get(
        Quiz,
        quiz_id
    )

    if quiz is None:
        return 'Викторина не найдена', 404

    if not can_manage_quiz(quiz):
        return 'Нет доступа', 403

    tokens = browser_session.get(
        'quiz_owner_tokens',
        {}
    )

    tokens.pop(
        str(quiz.id),
        None
    )

    browser_session['quiz_owner_tokens'] = tokens

    db.session.delete(quiz)
    db.session.commit()

    flash(
        'Викторина удалена.',
        'success'
    )

    return redirect(
        url_for('admin.dashboard')
    )


# ==========================================
# ЗАПУСК ИГРЫ
# ==========================================

@admin_bp.route(
    '/quiz/<int:quiz_id>/host'
)
def quiz_host(quiz_id):

    quiz = db.session.get(
        Quiz,
        quiz_id
    )

    if quiz is None:
        return 'Викторина не найдена', 404

    if not can_manage_quiz(quiz):
        return 'Нет доступа', 403

    if quiz.question_count() == 0:
        flash(
            'Добавьте хотя бы один вопрос перед запуском!',
            'error'
        )

        return redirect(
            url_for(
                'admin.quiz_edit',
                quiz_id=quiz_id,
                key=quiz.owner_token
            )
        )

    game_session = GameSession(
        quiz_id=quiz_id,
        pin=GameSession.generate_pin(),
        host_token=secrets.token_urlsafe(32)
    )

    db.session.add(game_session)
    db.session.commit()

    return render_template(
        'admin/host.html',
        quiz=quiz,
        session=game_session,
        host_token=game_session.host_token
    )
