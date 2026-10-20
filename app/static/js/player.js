/**
 * QuizPL14 — player.js
 * JavaScript для участника (join.html + game.html)
 */

// ── Определить страницу ───────────────────────
const isJoinPage = !!document.getElementById('join-form');

if (isJoinPage) {
  initJoinPage();
} else {
  initGamePage();
}

/* ═══════════════════════════════════════════════
   СТРАНИЦА JOIN — Ввод PIN и никнейма
   ═══════════════════════════════════════════════ */
function initJoinPage() {
  const form      = document.getElementById('join-form');
  const pinInput  = document.getElementById('pin-input');
  const nickInput = document.getElementById('nickname-input');
  const joinBtn   = document.getElementById('join-btn');
  const errBox    = document.getElementById('join-error');

  // Форматировать PIN только цифрами
  pinInput.addEventListener('input', () => {
    pinInput.value = pinInput.value.replace(/\D/g, '').slice(0, 6);
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const pin = pinInput.value.trim();
    const nick = nickInput.value.trim();

    if (pin.length !== 6) {
      showError('PIN должен содержать 6 цифр.');
      return;
    }
    if (!nick) {
      showError('Введите никнейм.');
      return;
    }

    // Сохранить данные и перейти на страницу игры
    sessionStorage.setItem('qpin', pin);
    sessionStorage.setItem('qnick', nick);

    joinBtn.disabled = true;
    joinBtn.textContent = 'Подключение...';
    window.location.href = '/game';
  });

  function showError(msg) {
    errBox.textContent = msg;
    errBox.style.display = 'block';
    setTimeout(() => { errBox.style.display = 'none'; }, 4000);
  }
}

/* ═══════════════════════════════════════════════
   СТРАНИЦА GAME — Игровой процесс
   ═══════════════════════════════════════════════ */
function initGamePage() {
  const pin      = sessionStorage.getItem('qpin');
  const nickname = sessionStorage.getItem('qnick');

  // Если нет данных — вернуть на join
  if (!pin || !nickname) {
    window.location.href = '/join';
    return;
  }

  const socket = io();
  let playerId = null;
  let currentPin = pin;
  let currentTimeLimit = 20;
  let timerInterval = null;
  let answered = false;

  // ── Экраны ──────────────────────────────────
  const screens = {
    lobby:       document.getElementById('screen-lobby'),
    question:    document.getElementById('screen-question'),
    result:      document.getElementById('screen-result'),
    leaderboard: document.getElementById('screen-leaderboard'),
    gameover:    document.getElementById('screen-gameover'),
  };

  function showScreen(name) {
    Object.values(screens).forEach(s => s.style.display = 'none');
    if (screens[name]) screens[name].style.display = 'flex';
  }

  // ── DOM ─────────────────────────────────────
  document.getElementById('player-name-display').textContent = nickname;
  const lobbyCount = document.getElementById('lobby-count');

  const qText    = document.getElementById('q-text');
  const qCounter = document.getElementById('q-counter');
  const timerNum = document.getElementById('timer-num');
  const timerRing = document.getElementById('timer-ring');
  const answerBtns = document.querySelectorAll('.answer-btn');

  const resultIcon    = document.getElementById('result-icon');
  const resultVerdict = document.getElementById('result-verdict');
  const resultPoints  = document.getElementById('result-points');
  const resultTotal   = document.getElementById('result-total');

  const playerLbList = document.getElementById('player-lb-list');
  const finalLbList  = document.getElementById('final-lb-list');
  const finalScore   = document.getElementById('final-score');

  // ── Подключение ─────────────────────────────
  socket.on('connect', () => {
    socket.emit('join_room', { pin, nickname });
  });

  socket.on('joined', (data) => {
    playerId = data.player_id;
    lobbyCount.textContent = `${data.player_count} ${pluralPlayers(data.player_count)} в комнате`;
    showScreen('lobby');
  });

  socket.on('player_joined', (data) => {
    lobbyCount.textContent = `${data.player_count} ${pluralPlayers(data.player_count)} в комнате`;
  });

  socket.on('error', (data) => {
    // Если ошибка — показать на join странице
    sessionStorage.removeItem('qpin');
    sessionStorage.removeItem('qnick');
    alert('Ошибка: ' + data.message);
    window.location.href = '/join';
  });

  // ── Вопрос ──────────────────────────────────
  socket.on('question_start', (data) => {
    const q = data.question;
    currentTimeLimit = q.time_limit;
    answered = false;

    qCounter.textContent = `${data.question_index + 1} / ${data.total_questions}`;
    qText.textContent = q.question_text;

    document.getElementById('text-a').textContent = q.option_a;
    document.getElementById('text-b').textContent = q.option_b;
    document.getElementById('text-c').textContent = q.option_c;
    document.getElementById('text-d').textContent = q.option_d;

    // Сбросить кнопки
    answerBtns.forEach(btn => {
      btn.disabled = false;
      btn.classList.remove('answer-btn--correct', 'answer-btn--wrong', 'answer-btn--chosen');
      btn.style.opacity = '';
    });

    startTimer(q.time_limit);
    showScreen('question');
  });

  // ── Нажатие кнопки ответа ───────────────────
  answerBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      if (answered) return;
      answered = true;
      stopTimer();

      const option = btn.dataset.option;
      btn.classList.add('answer-btn--chosen');
      answerBtns.forEach(b => b.disabled = true);

      socket.emit('submit_answer', {
        pin: currentPin,
        player_id: playerId,
        answer: option,
      });
    });
  });

  // ── Результат ответа ────────────────────────
  socket.on('answer_result', (data) => {
    stopTimer();

    if (data.is_correct) {
      resultIcon.textContent = '✅';
      resultVerdict.textContent = 'Верно!';
      resultVerdict.style.color = 'var(--green)';
      resultPoints.textContent = `+${data.points_earned.toLocaleString()}`;
    } else {
      resultIcon.textContent = '❌';
      resultVerdict.textContent = 'Неверно!';
      resultVerdict.style.color = 'var(--red)';
      resultPoints.textContent = '+0';
    }
    resultTotal.textContent = data.total_score.toLocaleString();

    showScreen('result');
  });

  // ── Лидерборд ───────────────────────────────
  socket.on('leaderboard', (data) => {
    renderLeaderboard(playerLbList, data.leaderboard);
    showScreen('leaderboard');
  });

  // ── Конец игры ──────────────────────────────
  socket.on('game_over', (data) => {
    stopTimer();
    renderLeaderboard(finalLbList, data.leaderboard);

    // Показать финальный счёт (найти игрока в лидерборде)
    const me = data.leaderboard.find(p => p.id === playerId);
    if (me) {
      finalScore.textContent = me.score.toLocaleString();
    } else {
      finalScore.textContent = '—';
    }

    showScreen('gameover');
    sessionStorage.removeItem('qpin');
    sessionStorage.removeItem('qnick');
  });

  // ── Таймер (круговой SVG) ───────────────────
  const CIRCUMFERENCE = 2 * Math.PI * 26; // r=26 → ~163.4

  function startTimer(seconds) {
    stopTimer();
    let remaining = seconds;
    timerNum.textContent = remaining;
    timerRing.style.strokeDashoffset = '0';
    timerRing.style.stroke = 'var(--accent)';

    timerInterval = setInterval(() => {
      remaining--;
      timerNum.textContent = remaining;

      const progress = remaining / seconds;
      const offset = CIRCUMFERENCE * (1 - progress);
      timerRing.style.strokeDashoffset = offset;

      if (remaining <= 5) {
        timerRing.style.stroke = 'var(--red)';
        timerNum.style.color   = 'var(--red)';
      } else if (remaining <= 10) {
        timerRing.style.stroke = 'var(--yellow)';
        timerNum.style.color   = 'var(--yellow)';
      }

      if (remaining <= 0) {
        stopTimer();
        if (!answered) {
          // Время вышло, заблокировать кнопки
          answered = true;
          answerBtns.forEach(btn => btn.disabled = true);
        }
      }
    }, 1000);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  // ── Рендер лидерборда ───────────────────────
  function renderLeaderboard(container, players) {
    container.innerHTML = '';
    const medals = ['🥇', '🥈', '🥉'];
    players.forEach((p, i) => {
      const item = document.createElement('div');
      item.className = `lb-item lb-item--${i + 1}`;
      const isMe = p.id === playerId ? ' (Вы)' : '';
      item.innerHTML = `
        <span class="lb-item__rank">${medals[i] || i + 1}</span>
        <span class="lb-item__name">${escapeHtml(p.nickname)}${isMe}</span>
        <span class="lb-item__score">${p.score.toLocaleString()}</span>
      `;
      container.appendChild(item);
    });
  }

  // ── Утилиты ─────────────────────────────────
  function pluralPlayers(n) {
    if (n % 10 === 1 && n % 100 !== 11) return 'игрок';
    if ([2,3,4].includes(n % 10) && ![12,13,14].includes(n % 100)) return 'игрока';
    return 'игроков';
  }

  function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
}
