from app import app, ensure_fallback_data, init_db


if __name__ == "__main__":
    init_db()
    ensure_fallback_data()
    app.run(debug=False, port=5001)
