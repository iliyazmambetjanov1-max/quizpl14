from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("  QuizPL14 launched!")
    print("  Open: http://localhost:5000")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
