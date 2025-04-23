from app import app

if __name__ == "__main__":
    # This block allows running the app directly using `python wsgi.py`
    # for development/testing, similar to `python app.py`.
    # Gunicorn itself imports the 'app' object directly and doesn't run this block.
    # You might adjust host/port here if needed for direct execution.
    print("Running Flask app via wsgi.py (for development/testing only)...")
    app.run(debug=True, port=5000)
