from datetime import datetime
from hashlib import md5
from time import time
import json
import jwt

from flask import current_app
from flask_login import UserMixin
import redis
import rq
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login, search


@login.user_loader
def user_loader(id):
    return User.query.get(int(id))


followers = db.Table(
    "followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("followed_id", db.Integer, db.ForeignKey("user.id")),
)


class SearchableMixin:
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = search.query_index(
            index=cls.__tablename__, query=expression, page=page, per_page=per_page
        )
        if total == 0:
            return cls.query.filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        return (
            cls.query.filter(cls.id.in_(ids)).order_by(db.case(when, value=cls.id)),
            total,
        )

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            "add": list(session.new),
            "update": list(session.dirty),
            "delete": list(session.deleted),
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes["add"]:
            if isinstance(obj, SearchableMixin):
                search.add_to_index(obj.__tablename__, obj)
        for obj in session._changes["update"]:
            if isinstance(obj, SearchableMixin):
                search.add_to_index(obj.__tablename__, obj)
        for obj in session._changes["delete"]:
            if isinstance(obj, SearchableMixin):
                search.remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in cls.query:
            search.add_to_index(obj.__tablename__, obj)


class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(124))
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_read_time = db.Column(db.DateTime)

    # Relationships (i.e. data pulled from other tables)
    posts = db.relationship("Post", backref="author", lazy="dynamic")
    tasks = db.relationship("Task", backref="user", lazy="dynamic")
    followed = db.relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )
    messages_sent = db.relationship(
        "Message", foreign_keys="Message.sender_id", backref="author", lazy="dynamic"
    )
    messages_received = db.relationship(
        "Message",
        foreign_keys="Message.recipient_id",
        backref="recipient",
        lazy="dynamic",
    )
    notifications = db.relationship("Notification", backref="user", lazy="dynamic")

    def add_notification(self, name, data):
        self.notifications.filter_by(name=name).delete()
        n = Notification(name=name, user=self, payload_json=json.dumps(data))
        db.session.add(n)
        return n

    def new_messages(self):
        """Return count of unread messags."""
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        return (
            Message.query.filter_by(recipient=self)
            .filter(Message.timestamp > last_read_time)
            .count()
        )

    def launch_task(self, name, description, *args, **kwargs):
        rq_job = current_app.task_queue.enqueue(
            f"app.tasks.{name}", self.id, *args, **kwargs
        )

        task = Task(id=rq_job.get_id(), name=name, description=description, user=self)
        db.session.add(task)

        return task

    def get_tasks_in_progress(self):
        return Task.query.filter_by(user=self, complete=False).all()

    def get_task_in_progress(self, name):
        return Task.query.filter_by(user=self, name=name, complete=False).first()

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def followed_posts(self):
        followed = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)
        ).filter(followers.c.follower_id == self.id)
        own = Post.query.filter_by(user_id=self.id)

        return followed.union(own).order_by(Post.timestamp.desc())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            payload={"reset_password": self.id, "exp": time() + expires_in},
            key=current_app.config["SECRET_KEY"],
            algorithm="HS256",
        ).decode("utf-8")

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(
                jwt=token, key=current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )["reset_password"]
            id = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )["reset_password"]
        except:  # noqa: E722
            return
        return User.query.get(id)

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"


class Post(SearchableMixin, db.Model):

    __searchable__ = ["body"]

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    language = db.Column(db.String(5))


class Message(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f"<Message: {self.body}>"


class Notification(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    timestamp = db.Column(db.Float, index=True, default=time)
    payload_json = db.Column(db.Text)

    def get_payload(self):
        return json.loads(str(self.payload_json))


class Task(db.Model):

    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(128), index=True)
    description = db.Column(db.String(128))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    complete = db.Column(db.Boolean, default=False)

    def get_rq_job(self):
        try:
            return rq.job.Job.fetch(id=self.id, connection=current_app.redis)
        except (rq.exceptions.NoSuchJobError, redis.exceptions.RedisError):
            return None

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get("progress", 0) if job is not None else 100


db.event.listen(db.session, "before_commit", SearchableMixin.before_commit)
db.event.listen(db.session, "after_commit", SearchableMixin.after_commit)
