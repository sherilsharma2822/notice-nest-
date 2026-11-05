"""Start the NoticeNest web app:  python run.py"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True reloads the server when you edit code. Never use it on a public server.
    app.run(debug=True)
