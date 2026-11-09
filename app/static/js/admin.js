 
/**
 * QuizPL14 — admin.js
 * Панель ведущего
 */

const socket = io();

// Экраны
const screens = {
  lobby: document.getElementById('screen-lobby'),
  question: document.getElementById('screen-question'),
  leaderboard: document.getElementById('screen-leaderboard'),
  gameover: document.getElementById('screen-gameover'),
};

// Основные элементы
const playerCount = document.getElementById('player-count');
const answeredCount = document.getElementById('answered-count');
const lobbyList = document.getElementById('lobby-player-list');

const startBtn = document.getElementById('start-btn');
const nextBtn = document.getElementById('next-btn');
const lbBtn = document.getElementById('leaderboard-btn');

// Вопрос
const qProgress = document.getElementById('q-progress');
const qText = document.getElementById('q-text');

const optA = document.getElementById('opt-a');
const optB = document.getElementById('opt-b');
const optC = document.getElementById('opt-c');
const optD = document.getElementById('opt-d');

const timerBar = document.getElementById('timer-bar');
const timerVal = document.getElementById('timer-val');

// Таблицы результатов
const lbList = document.getElementById('leaderboard-list');
const finalLb = document.getElementById('final-leaderboard');

let timerInterval = null;
let currentTimeLimit = 20;


// Показ экрана
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


// Подключение ведущего
socket.on('connect', () => {
  socket.emit('host_join', {
    pin: PIN,
    host_token: HOST_TOKEN
  });
});


// Восстановление состояния после подключения
socket.on('host_joined', (data) => {
  playerCount.textContent = data.player_count;

  if (data.state === 'lobby') {
    showScreen('lobby');

    startBtn.style.display = 'block';
    startBtn.disabled = false;
    startBtn.textContent = 'Начать игру';

    return;
  }

  if (data.state === 'active' && data.question) {
    startBtn.style.display = 'none';

    // Если вопрос ещё не завершён — восстанавливаем его.
    if (!data.question_completed) {
      showQuestion({
        question: data.question,
        question_index: data.question_index,
        total_questions: data.total_questions,
        remaining_time: data.remaining_time
      });

      return;
    }

    // Если вопрос завершён, сервер должен прислать
    // leaderboard и correct_option.
    if (
      data.leaderboard &&
      data.correct_option
    ) {
      showLeaderboard({
        leaderboard: data.leaderboard,
        correct_option: data.correct_option
      });

      return;
    }

    // Временный экран до получения результатов.
    showScreen('question');
    qText.textContent = 'Вопрос завершён. Загружаем результаты...';

    stopTimer();
    timerVal.textContent = '0';
    timerBar.style.width = '0%';

    nextBtn.style.display = 'none';
    lbBtn.style.display = 'none';

    return;
  }

  if (data.state === 'finished') {
    showScreen('gameover');
  }
});


// Новый участник
socket.on('player_joined', (data) => {
  playerCount.textContent = data.player_count;

  const tag = document.createElement('div');
  tag.className = 'lobby-player-tag';
  tag.textContent = data.nickname;

  lobbyList.appendChild(tag);
});


// Начать игру
startBtn.addEventListener('click', () => {
  socket.emit('start_game', {
    pin: PIN,
    host_token: HOST_TOKEN
  });

  startBtn.disabled = true;
  startBtn.textContent = 'Загрузка...';
});


// Получен новый вопрос
socket.on('question_start', (data) => {
  showQuestion(data);
});


// Отображение вопроса
function showQuestion(data) {
  const q = data.question;

  if (!q) return;

  currentTimeLimit = q.time_limit;

  qProgress.textContent =
    `Вопрос ${data.question_index + 1} из ${data.total_questions}`;

  qText.textContent = q.question_text;

  optA.textContent = q.option_a;
  optB.textContent = q.option_b;
  optC.textContent = q.option_c;
  optD.textContent = q.option_d;

  answeredCount.textContent = '0';

  const remaining = data.remaining_time ?? q.time_limit;

  startTimer(remaining, q.time_limit);

  showScreen('question');

  startBtn.style.display = 'none';
  nextBtn.style.display = 'none';
  lbBtn.style.display = 'none';

  document.querySelectorAll('.host-answer').forEach(el => {
    el.style.opacity = '';
    el.style.outline = '';
  });
}


// Прогресс ответов
socket.on('answer_progress', (data) => {
  answeredCount.textContent = data.answered;
  playerCount.textContent = data.total;
});


// Получена таблица результатов
socket.on('leaderboard', (data) => {
  showLeaderboard(data);
});


// Отображение таблицы результатов
function showLeaderboard(data) {
  stopTimer();

  renderLeaderboard(lbList, data.leaderboard);

  const correctMap = {
    a: optA,
    b: optB,
    c: optC,
    d: optD
  };

  document.querySelectorAll('.host-answer').forEach(el => {
    el.style.opacity = '0.4';
    el.style.outline = '';
  });

  const correctParent =
    correctMap[data.correct_option]?.closest('.host-answer');

  if (correctParent) {
    correctParent.style.opacity = '1';
    correctParent.style.outline = '3px solid #fff';
  }

  showScreen('leaderboard');

  nextBtn.style.display = 'block';
  lbBtn.style.display = 'none';
}


// Следующий вопрос
nextBtn.addEventListener('click', () => {
  socket.emit('next_question', {
    pin: PIN,
    host_token: HOST_TOKEN
  });

  nextBtn.disabled = true;
  nextBtn.style.display = 'none';
});


// Показать лидеров
lbBtn.addEventListener('click', () => {
  socket.emit('show_leaderboard', {
    pin: PIN,
    host_token: HOST_TOKEN
  });
});


// Конец игры
socket.on('game_over', (data) => {
  stopTimer();

  renderLeaderboard(finalLb, data.leaderboard);

  showScreen('gameover');

  nextBtn.style.display = 'none';
  lbBtn.style.display = 'none';
});


// Ошибки
socket.on('error', (data) => {
  alert('Ошибка: ' + data.message);

  startBtn.disabled = false;
  startBtn.textContent = 'Начать игру';

  nextBtn.disabled = false;
});


// Таймер
function startTimer(remainingSeconds, fullTime) {
  stopTimer();

  let remaining = Math.max(0, Math.ceil(remainingSeconds));
  const total = fullTime || currentTimeLimit;

  timerVal.textContent = remaining;

  timerBar.style.width =
    `${Math.max(0, (remaining / total) * 100)}%`;

  timerInterval = setInterval(() => {
    remaining--;

    timerVal.textContent = Math.max(0, remaining);

    timerBar.style.width =
      `${Math.max(0, (remaining / total) * 100)}%`;

    if (remaining <= 5) {
      timerBar.style.background = 'var(--red)';
    } else {
      timerBar.style.background = '';
    }

    if (remaining <= 0) {
      stopTimer();
      lbBtn.style.display = 'block';
    }
  }, 1000);
}


function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}


// Таблица результатов
function renderLeaderboard(container, players) {
  container.innerHTML = '';

  const medals = ['🥇', '🥈', '🥉'];

  players.forEach((p, i) => {
    const item = document.createElement('div');

    item.className = `lb-item lb-item--${i + 1}`;

    item.innerHTML = `
      <span class="lb-item__rank">${medals[i] || i + 1}</span>
      <span class="lb-item__name">${escapeHtml(p.nickname)}</span>
      <span class="lb-item__score">${Number(p.score).toLocaleString()}</span>
    `;

    container.appendChild(item);
  });
}


// Защита текста
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
