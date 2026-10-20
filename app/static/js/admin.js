/**
 * QuizPL14 — admin.js
 * JavaScript панели ведущего (host.html)
 */

const socket = io();

// ── Элементы DOM ─────────────────────────────
const screens = {
  lobby:       document.getElementById('screen-lobby'),
  question:    document.getElementById('screen-question'),
  leaderboard: document.getElementById('screen-leaderboard'),
  gameover:    document.getElementById('screen-gameover'),
};
const playerCount   = document.getElementById('player-count');
const answeredCount = document.getElementById('answered-count');
const lobbyList     = document.getElementById('lobby-player-list');
const startBtn      = document.getElementById('start-btn');
const nextBtn       = document.getElementById('next-btn');
const lbBtn         = document.getElementById('leaderboard-btn');

// Вопрос
const qProgress = document.getElementById('q-progress');
const qText     = document.getElementById('q-text');
const optA = document.getElementById('opt-a');
const optB = document.getElementById('opt-b');
const optC = document.getElementById('opt-c');
const optD = document.getElementById('opt-d');

const timerBar = document.getElementById('timer-bar');
const timerVal = document.getElementById('timer-val');

// Лидерборд
const lbList    = document.getElementById('leaderboard-list');
const finalLb   = document.getElementById('final-leaderboard');

let timerInterval = null;
let currentTimeLimit = 20;

// ── Состояние ─────────────────────────────────
function showScreen(name) {
  Object.values(screens).forEach(s => s.style.display = 'none');
  screens[name].style.display = 'flex';
}

// ── Подключение ───────────────────────────────
socket.on('connect', () => {
  socket.emit('host_join', { pin: PIN });
});

socket.on('host_joined', (data) => {
  playerCount.textContent = data.player_count;
  showScreen('lobby');
});

// ── Новый участник зашёл ─────────────────────
socket.on('player_joined', (data) => {
  playerCount.textContent = data.player_count;
  const tag = document.createElement('div');
  tag.className = 'lobby-player-tag';
  tag.textContent = data.nickname;
  lobbyList.appendChild(tag);
});

// ── Кнопка: Начать игру ───────────────────────
startBtn.addEventListener('click', () => {
  socket.emit('start_game', { pin: PIN });
  startBtn.disabled = true;
  startBtn.textContent = 'Загрузка...';
});

// ── Получен вопрос ────────────────────────────
socket.on('question_start', (data) => {
  const q = data.question;
  currentTimeLimit = q.time_limit;

  qProgress.textContent = `Вопрос ${data.question_index + 1} из ${data.total_questions}`;
  qText.textContent = q.question_text;
  optA.textContent = q.option_a;
  optB.textContent = q.option_b;
  optC.textContent = q.option_c;
  optD.textContent = q.option_d;

  answeredCount.textContent = '0';

  startTimer(q.time_limit);
  showScreen('question');

  startBtn.style.display = 'none';
  nextBtn.style.display = 'none';
  lbBtn.style.display = 'none';
});

// ── Прогресс ответов ──────────────────────────
socket.on('answer_progress', (data) => {
  answeredCount.textContent = data.answered;
  playerCount.textContent   = data.total;
});

// ── Лидерборд ─────────────────────────────────
socket.on('leaderboard', (data) => {
  stopTimer();
  renderLeaderboard(lbList, data.leaderboard);

  // Подсветить правильный вариант
  const correctMap = { a: optA, b: optB, c: optC, d: optD };
  const correct = data.correct_option;
  document.querySelectorAll('.host-answer').forEach(el => el.style.opacity = '0.4');
  const correctParent = correctMap[correct]?.closest('.host-answer');
  if (correctParent) {
    correctParent.style.opacity = '1';
    correctParent.style.outline = '3px solid #fff';
  }

  showScreen('leaderboard');
  nextBtn.style.display = 'block';
  lbBtn.style.display = 'none';
});

// ── Кнопка: Следующий вопрос ─────────────────
nextBtn.addEventListener('click', () => {
  // Сбросить подсветку
  document.querySelectorAll('.host-answer').forEach(el => {
    el.style.opacity = '';
    el.style.outline = '';
  });
  socket.emit('next_question', { pin: PIN });
  nextBtn.style.display = 'none';
});

// ── Кнопка: Показать лидеров вручную ─────────
lbBtn.addEventListener('click', () => {
  socket.emit('show_leaderboard', { pin: PIN });
});

// ── Конец игры ────────────────────────────────
socket.on('game_over', (data) => {
  stopTimer();
  renderLeaderboard(finalLb, data.leaderboard);
  showScreen('gameover');
  nextBtn.style.display = 'none';
  lbBtn.style.display = 'none';
});

// ── Ошибки ────────────────────────────────────
socket.on('error', (data) => {
  alert('Ошибка: ' + data.message);
});

// ── Таймер ────────────────────────────────────
function startTimer(seconds) {
  stopTimer();
  let remaining = seconds;
  timerVal.textContent = remaining;
  timerBar.style.width = '100%';

  timerInterval = setInterval(() => {
    remaining--;
    timerVal.textContent = remaining;
    timerBar.style.width = `${(remaining / seconds) * 100}%`;

    if (remaining <= 5) {
      timerBar.style.background = 'var(--red)';
    } else {
      timerBar.style.background = '';
    }

    if (remaining <= 0) {
      stopTimer();
      // Показать кнопку лидерборда если ещё не показан
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

// ── Рендер лидерборда ─────────────────────────
function renderLeaderboard(container, players) {
  container.innerHTML = '';
  const medals = ['🥇', '🥈', '🥉'];
  players.forEach((p, i) => {
    const item = document.createElement('div');
    item.className = `lb-item lb-item--${i + 1}`;
    item.innerHTML = `
      <span class="lb-item__rank">${medals[i] || i + 1}</span>
      <span class="lb-item__name">${escapeHtml(p.nickname)}</span>
      <span class="lb-item__score">${p.score.toLocaleString()}</span>
    `;
    container.appendChild(item);
  });
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
