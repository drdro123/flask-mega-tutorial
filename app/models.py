from datetime import datetime
from hashlib import md5
from time import time
import jwt

from flask import current_app
from flask_login import UserMixin
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

    # Relationships (i.e. data pulled from other tables)
    posts = db.relationship("Post", backref="author", lazy="dynamic")
    followed = db.relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )

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

    def __repr__(self):
        return f"<User {self.username}>"


class Post(SearchableMixin, db.Model):

    __searchable__ = ["body"]

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    language = db.Column(db.String(5))


db.event.listen(db.session, "before_commit", SearchableMixin.before_commit)
db.event.listen(db.session, "after_commit", SearchableMixin.after_commit)
