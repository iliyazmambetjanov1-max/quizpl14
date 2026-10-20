from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Quiz, Question, GameSession

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Доступ запрещён.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    quizzes = Quiz.query.filter_by(creator_id=current_user.id).order_by(Quiz.created_at.desc()).all()
    return render_template('admin/dashboard.html', quizzes=quizzes)


@admin_bp.route('/quiz/new', methods=['GET', 'POST'])
@login_required
@admin_required
def quiz_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Введите название викторины.', 'error')
            return render_template('admin/quiz_editor.html', quiz=None)
        quiz = Quiz(title=title, creator_id=current_user.id)
        db.session.add(quiz)
        db.session.commit()
        flash(f'Викторина «{title}» создана!', 'success')
        return redirect(url_for('admin.quiz_edit', quiz_id=quiz.id))
    return render_template('admin/quiz_editor.html', quiz=None)


@admin_bp.route('/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def quiz_edit(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.creator_id != current_user.id:
        flash('Нет доступа к этой викторине.', 'error')
        return redirect(url_for('admin.dashboard'))
    questions = quiz.questions.order_by(Question.order_index).all()
    return render_template('admin/quiz_editor.html', quiz=quiz, questions=questions)


@admin_bp.route('/quiz/<int:quiz_id>/question/add', methods=['POST'])
@login_required
@admin_required
def question_add(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.creator_id != current_user.id:
        return jsonify({'error': 'Нет доступа'}), 403

    q_text = request.form.get('question_text', '').strip()
    opt_a = request.form.get('option_a', '').strip()
    opt_b = request.form.get('option_b', '').strip()
    opt_c = request.form.get('option_c', '').strip()
    opt_d = request.form.get('option_d', '').strip()
    correct = request.form.get('correct_option', 'a')
    time_limit = int(request.form.get('time_limit', 20))

    if not all([q_text, opt_a, opt_b, opt_c, opt_d]):
        flash('Заполните все поля вопроса.', 'error')
        return redirect(url_for('admin.quiz_edit', quiz_id=quiz_id))

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
    flash('Вопрос добавлен!', 'success')
    return redirect(url_for('admin.quiz_edit', quiz_id=quiz_id))


@admin_bp.route('/quiz/<int:quiz_id>/question/<int:q_id>/delete', methods=['POST'])
@login_required
@admin_required
def question_delete(quiz_id, q_id):
    question = Question.query.get_or_404(q_id)
    db.session.delete(question)
    db.session.commit()
    flash('Вопрос удалён.', 'success')
    return redirect(url_for('admin.quiz_edit', quiz_id=quiz_id))


@admin_bp.route('/quiz/<int:quiz_id>/delete', methods=['POST'])
@login_required
@admin_required
def quiz_delete(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.creator_id != current_user.id:
        flash('Нет доступа.', 'error')
        return redirect(url_for('admin.dashboard'))
    db.session.delete(quiz)
    db.session.commit()
    flash('Викторина удалена.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/quiz/<int:quiz_id>/host')
@login_required
@admin_required
def quiz_host(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.creator_id != current_user.id:
        flash('Нет доступа.', 'error')
        return redirect(url_for('admin.dashboard'))
    if quiz.question_count() == 0:
        flash('Добавьте хотя бы один вопрос перед запуском!', 'error')
        return redirect(url_for('admin.quiz_edit', quiz_id=quiz_id))

    # Создаём новую сессию с уникальным PIN
    session = GameSession(quiz_id=quiz_id, pin=GameSession.generate_pin())
    db.session.add(session)
    db.session.commit()
    return render_template('admin/host.html', quiz=quiz, session=session)
