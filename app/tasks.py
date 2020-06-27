import json
import sys
import time

from rq import get_current_job
from flask import render_template

from app import create_app, db
from app.auth.email import send_email
from app.models import Post, Task, User


app = create_app()
app.app_context().push()


def _set_task_progress(progress):
    job = get_current_job()
    if job:
        job.meta["progress"] = progress
        job.save_meta()

        task = Task.query.get(job.get_id())
        task.user.add_notification(
            name="task_progress", data={"task_id": job.get_id(), "progress": progress}
        )

        if progress == 100:
            task.complete = True

        db.session.commit()


def export_posts(user_id):
    try:
        user = User.query.get(user_id)
        _set_task_progress(0)
        data = []
        total_posts = user.posts.count()
        for i, post in enumerate(user.posts.order_by(Post.timestamp.asc())):
            data.append(
                {"body": post.body, "timestamp": post.timestamp.isoformat() + "Z"}
            )
            time.sleep(5)  # Only needed to test out progress reporting
            _set_task_progress(i / total_posts * 100)

        # Send email to user
        send_email(
            subject="Your blog post export",
            sender=app.config["ADMINS"][0],
            recipients=[user.email],
            text_body=render_template("email/export_posts.txt", user=user),
            html_body=render_template("email/export_posts.html", user=user),
            attachments=[
                (
                    "posts.json",
                    "application/json",
                    json.dumps({"posts": data}, indent=4),
                )
            ],
            sync=True,
        )
    except:
        app.logger.error("Unhandled exception", exc_info=sys.exc_info())
    finally:
        _set_task_progress(100)


def example(seconds):
    job = get_current_job()
    for i in range(seconds):
        job.meta["progress"] = i / seconds * 100
        job.save_meta()
        print(i)
        time.sleep(1)
    job.meta["progress"] = 100
    job.save_meta()
    print("Task completed")
