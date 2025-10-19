# run.py
import os
from app import create_app
from app.routes import start_background_threads

app = create_app()

if __name__ == '__main__':
    # Start the background threads ONCE before running the app
    start_background_threads()

    # Use 0.0.0.0 to make the server accessible on your network
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host=host, port=port, debug=True, use_reloader=False)