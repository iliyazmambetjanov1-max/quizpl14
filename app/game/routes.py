from flask import Blueprint, render_template, redirect, url_for

game_bp = Blueprint('game', __name__, url_prefix='/')


@game_bp.route('/')
def index():
    return redirect(url_for('game.join'))


@game_bp.route('/join')
def join():
    return render_template('player/join.html')


@game_bp.route('/lobby')
def lobby():
    return render_template('player/lobby.html')


@game_bp.route('/game')
def game():
    return render_template('player/game.html')


@game_bp.route('/results')
def results():
    return render_template('player/results.html')
