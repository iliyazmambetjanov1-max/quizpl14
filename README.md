# ⚡ QuizPL14 — Система интерактивных викторин

Аналог Kahoot на Python/Flask с поддержкой реального времени через WebSocket.

## Быстрый старт

### 1. Установить зависимости
```bash
pip install -r requirements.txt
```

### 2. Создать администратора
```bash
flask create-admin
```
По умолчанию: логин `admin`, пароль `admin123`

### 3. Запустить сервер
```bash
python run.py
```

Откройте браузер: **http://localhost:5000**

---

## Роли

| Роль | URL | Описание |
|---|---|---|
| Ведущий | `/auth/login` | Создание и запуск викторин |
| Участник | `/join` | Вход по PIN-коду |

## Как играть

1. **Ведущий** входит в панель → создаёт викторину → запускает игру → получает PIN
2. **Участники** открывают `/join`, вводят PIN и никнейм
3. Ведущий нажимает **▶ Начать игру**
4. Все видят вопрос одновременно, участники нажимают кнопку ответа
5. После каждого вопроса — таблица лидеров

## Структура проекта

```
quizpl14/
├── app/
│   ├── auth/       # Авторизация
│   ├── admin/      # Панель ведущего (CRUD)
│   ├── game/       # Маршруты участника
│   ├── sockets/    # WebSocket события
│   ├── models.py   # БД: User, Quiz, Question, GameSession, Player
│   ├── static/     # CSS + JS
│   └── templates/  # HTML-шаблоны
├── config.py
├── run.py
└── requirements.txt
```

## Технологии

- **Backend**: Python 3, Flask, Flask-SocketIO, Flask-SQLAlchemy, Flask-Login
- **Database**: SQLite
- **Frontend**: HTML5, Vanilla CSS, Vanilla JS, Socket.IO client
- **Real-time**: WebSocket (eventlet)
