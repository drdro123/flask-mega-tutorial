from app import cli, create_app, db
from app.models import Message, Notification, Post, Task, User


app = create_app()
cli.register(app)


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "Message": Message,
        "Notification": Notification,
        "Post": Post,
        "Task": Task,
        "User": User,
    }
