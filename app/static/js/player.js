
/**
 * QuizPL14 — player.js
 * JavaScript для участника
 */

const isJoinPage = !!document.getElementById('join-form');

if (isJoinPage) {
    initJoinPage();
} else {
    initGamePage();
}


/* ─────────────────────────────────────────
   СТРАНИЦА ВХОДА
───────────────────────────────────────── */

function initJoinPage() {
    const form = document.getElementById('join-form');
    const pinInput = document.getElementById('pin-input');
    const nickInput = document.getElementById('nickname-input');
    const joinBtn = document.getElementById('join-btn');
    const errBox = document.getElementById('join-error');

    pinInput.addEventListener('input', () => {
        pinInput.value = pinInput.value.replace(/\D/g, '').slice(0, 6);
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();

        const pin = pinInput.value.trim();
        const nickname = nickInput.value.trim();

        if (pin.length !== 6) {
            showError('PIN должен содержать 6 цифр.');
            return;
        }

        if (!nickname) {
            showError('Введите никнейм.');
            return;
        }

        sessionStorage.setItem('qpin', pin);
        sessionStorage.setItem('qnick', nickname);

        joinBtn.disabled = true;
        joinBtn.textContent = 'Подключение...';

        window.location.href = '/game';
    });

    function showError(message) {
        errBox.textContent = message;
        errBox.style.display = 'block';

        setTimeout(() => {
            errBox.style.display = 'none';
        }, 4000);
    }
}


/* ─────────────────────────────────────────
   ИГРОВАЯ СТРАНИЦА
───────────────────────────────────────── */

function initGamePage() {
    const pin = sessionStorage.getItem('qpin');
    const nickname = sessionStorage.getItem('qnick');

    if (!pin || !nickname) {
        window.location.href = '/join';
        return;
    }

    const socket = io();

    let playerId = null;
    let answered = false;
    let timerInterval = null;
    let currentQuestion = null;

    const screens = {
        lobby: document.getElementById('screen-lobby'),
        question: document.getElementById('screen-question'),
        result: document.getElementById('screen-result'),
        leaderboard: document.getElementById('screen-leaderboard'),
        gameover: document.getElementById('screen-gameover')
    };

    const playerName = document.getElementById('player-name-display');
    const lobbyCount = document.getElementById('lobby-count');

    const qText = document.getElementById('q-text');
    const qCounter = document.getElementById('q-counter');

    const timerNum = document.getElementById('timer-num');
    const timerRing = document.getElementById('timer-ring');

    const answerBtns = document.querySelectorAll('.answer-btn');

    const resultIcon = document.getElementById('result-icon');
    const resultVerdict = document.getElementById('result-verdict');
    const resultPoints = document.getElementById('result-points');
    const resultTotal = document.getElementById('result-total');

    const playerLbList = document.getElementById('player-lb-list');
    const finalLbList = document.getElementById('final-lb-list');
    const finalScore = document.getElementById('final-score');

    playerName.textContent = nickname;


    /* Переключение экранов */

    function showScreen(name) {
        Object.values(screens).forEach(screen => {
            if (screen) {
                screen.style.display = 'none';
            }
        });

        if (screens[name]) {
            screens[name].style.display = 'flex';
        }
    }


    /* Подключение к комнате */

    socket.on('connect', () => {
        socket.emit('join_room', {
            pin: pin,
            nickname: nickname
        });
    });

    socket.on('joined', (data) => {
        playerId = data.player_id;

        lobbyCount.textContent =
            `${data.player_count} ${pluralPlayers(data.player_count)} в комнате`;

        if (data.session_state === 'lobby') {
            showScreen('lobby');
        }
    });

    socket.on('player_joined', (data) => {
        lobbyCount.textContent =
            `${data.player_count} ${pluralPlayers(data.player_count)} в комнате`;
    });

    socket.on('error', (data) => {
        sessionStorage.removeItem('qpin');
        sessionStorage.removeItem('qnick');

        alert('Ошибка: ' + data.message);
        window.location.href = '/join';
    });


    /* Начало и восстановление вопроса */

    socket.on('question_start', (data) => {
        const question = data.question;

        currentQuestion = question;
        answered = false;

        qCounter.textContent =
            `${data.question_index + 1} / ${data.total_questions}`;

        qText.textContent = question.question_text;

        document.getElementById('text-a').textContent = question.option_a;
        document.getElementById('text-b').textContent = question.option_b;
        document.getElementById('text-c').textContent = question.option_c;
        document.getElementById('text-d').textContent = question.option_d;

        answerBtns.forEach(btn => {
            btn.disabled = false;

            btn.classList.remove(
                'answer-btn--correct',
                'answer-btn--wrong',
                'answer-btn--chosen'
            );

            btn.style.opacity = '';
        });

        const remaining = data.remaining_time ?? question.time_limit;

        startTimer(remaining);
        showScreen('question');
    });


    /* Отправка ответа */

    answerBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            if (answered || !playerId) {
                return;
            }

            answered = true;
            stopTimer();

            const option = btn.dataset.option;

            btn.classList.add('answer-btn--chosen');

            answerBtns.forEach(button => {
                button.disabled = true;
            });

            socket.emit('submit_answer', {
                pin: pin,
                player_id: playerId,
                answer: option
            });
        });
    });


    /* Результат ответа */

    socket.on('answer_result', (data) => {
        answered = true;
        stopTimer();

        if (data.already_answered) {
            resultIcon.textContent = '✓';
            resultVerdict.textContent = 'Ваш ответ уже принят!';
            resultVerdict.style.color = 'var(--green)';
            resultPoints.textContent = '+0';

        } else if (data.timed_out) {
            resultIcon.textContent = '⏰';
            resultVerdict.textContent = 'Время вышло!';
            resultVerdict.style.color = 'var(--red)';
            resultPoints.textContent = '+0';

        } else if (data.is_correct) {
            resultIcon.textContent = '✅';
            resultVerdict.textContent = 'Верно!';
            resultVerdict.style.color = 'var(--green)';
            resultPoints.textContent =
                `+${Number(data.points_earned || 0).toLocaleString()}`;

        } else {
            resultIcon.textContent = '❌';
            resultVerdict.textContent = 'Неверно!';
            resultVerdict.style.color = 'var(--red)';
            resultPoints.textContent = '+0';
        }

        resultTotal.textContent =
            Number(data.total_score || 0).toLocaleString();

        // Подсветка правильного ответа
        answerBtns.forEach(btn => {
            const option = btn.dataset.option;

            btn.classList.remove(
                'answer-btn--correct',
                'answer-btn--wrong'
            );

            if (option === data.correct_option) {
                btn.classList.add('answer-btn--correct');
            }
        });

        showScreen('result');
    });


    /* Завершение времени вопроса */

    socket.on('question_timeout', () => {
        answered = true;
        stopTimer();

        answerBtns.forEach(btn => {
            btn.disabled = true;
        });

        resultIcon.textContent = '⏰';
        resultVerdict.textContent = 'Время вышло!';
        resultVerdict.style.color = 'var(--red)';
        resultPoints.textContent = '+0';

        showScreen('result');
    });


    /* Таблица лидеров */

    socket.on('leaderboard', (data) => {
        stopTimer();

        renderLeaderboard(playerLbList, data.leaderboard || []);

        showScreen('leaderboard');
    });


    /* Завершение игры */

    socket.on('game_over', (data) => {
        stopTimer();

        const leaderboard = data.leaderboard || [];

        renderLeaderboard(finalLbList, leaderboard);

        const me = leaderboard.find(
            player => player.id === playerId
        );

        finalScore.textContent = me
            ? Number(me.score).toLocaleString()
            : '—';

        showScreen('gameover');

        sessionStorage.removeItem('qpin');
        sessionStorage.removeItem('qnick');
    });


    /* Таймер */

    const CIRCUMFERENCE = 2 * Math.PI * 26;

    function startTimer(seconds) {
        stopTimer();

        const totalSeconds = Math.max(0, Math.ceil(seconds));
        let remaining = totalSeconds;

        timerNum.textContent = remaining;
        timerRing.style.strokeDashoffset = '0';
        timerRing.style.stroke = 'var(--accent)';
        timerNum.style.color = '';

        if (remaining <= 0) {
            timeExpired();
            return;
        }

        timerInterval = setInterval(() => {
            remaining--;

            timerNum.textContent = Math.max(0, remaining);

            const progress = totalSeconds > 0
                ? remaining / totalSeconds
                : 0;

            timerRing.style.strokeDashoffset =
                CIRCUMFERENCE * (1 - progress);

            if (remaining <= 5) {
                timerRing.style.stroke = 'var(--red)';
                timerNum.style.color = 'var(--red)';
            } else if (remaining <= 10) {
                timerRing.style.stroke = 'var(--yellow)';
                timerNum.style.color = 'var(--yellow)';
            }

            if (remaining <= 0) {
                stopTimer();
                timeExpired();
            }
        }, 1000);
    }

    function timeExpired() {
        if (answered) {
            return;
        }

        answered = true;

        answerBtns.forEach(btn => {
            btn.disabled = true;
        });

        // Сервер сам завершит вопрос и отправит результат.
    }

    function stopTimer() {
        if (timerInterval !== null) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }


    /* Рендер таблицы лидеров */

    function renderLeaderboard(container, players) {
        if (!container) {
            return;
        }

        container.innerHTML = '';

        const medals = ['🥇', '🥈', '🥉'];

        players.forEach((player, index) => {
            const item = document.createElement('div');

            item.className = `lb-item lb-item--${index + 1}`;

            const isMe = player.id === playerId ? ' (Вы)' : '';

            const rank = document.createElement('span');
            rank.className = 'lb-item__rank';
            rank.textContent = medals[index] || index + 1;

            const name = document.createElement('span');
            name.className = 'lb-item__name';
            name.textContent = `${player.nickname}${isMe}`;

            const score = document.createElement('span');
            score.className = 'lb-item__score';
            score.textContent =
                Number(player.score || 0).toLocaleString();

            item.appendChild(rank);
            item.appendChild(name);
            item.appendChild(score);

            container.appendChild(item);
        });
    }


    /* Вспомогательные функции */

    function pluralPlayers(number) {
        if (number % 10 === 1 && number % 100 !== 11) {
            return 'игрок';
        }

        if (
            [2, 3, 4].includes(number % 10) &&
            ![12, 13, 14].includes(number % 100)
        ) {
            return 'игрока';
        }

        return 'игроков';
    }
}
