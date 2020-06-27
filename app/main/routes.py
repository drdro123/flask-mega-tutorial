from datetime import datetime

from flask import (
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_babel import _, get_locale
from flask_login import current_user, login_required
from guess_language import guess_language

from app import db
from app.main import bp
from app.main.forms import (
    EditProfileForm,
    EmptyForm,
    MessageForm,
    PostForm,
    SearchForm,
)
from app.models import Message, Notification, Post, User
from app.translate import translate


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())


@bp.route("/", methods=["GET", "POST"])
@bp.route("/index", methods=["GET", "POST"])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        language = guess_language(form.post.data)
        if language == "UNKNOWN" or len(language) > 5:
            language = ""
        post = Post(
            body=form.post.data,
            timestamp=datetime.utcnow(),
            user_id=current_user.id,
            language=language,
        )
        db.session.add(post)
        db.session.commit()
        flash(_("Post submitted!"))
        return redirect(
            url_for("main.index")
        )  # Better Refresh behaviour (POST/REDIRECT/GET). Also avoids duplicate posts

    page = request.args.get("page", 1, type=int)
    posts = current_user.followed_posts().paginate(
        page, current_app.config["POSTS_PER_PAGE"], False
    )

    next_url = url_for("main.index", page=posts.next_num) if posts.has_next else None
    prev_url = url_for("main.index", page=posts.prev_num) if posts.has_prev else None

    return render_template(
        "index.html",
        title="Home",
        posts=posts.items,
        form=form,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route("/explore")
def explore():
    page = request.args.get("page", 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config["POSTS_PER_PAGE"], False
    )
    next_url = url_for("main.explore", page=posts.next_num) if posts.has_next else None
    prev_url = url_for("main.explore", page=posts.prev_num) if posts.has_prev else None

    return render_template(
        "index.html",
        title="Explore",
        posts=posts.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route("/search")
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for("main.explore"))

    query = g.search_form.q.data
    page = request.args.get("page", 1, type=int)

    posts, total = Post.search(
        expression=query, page=page, per_page=current_app.config["POSTS_PER_PAGE"],
    )

    next_url = (
        url_for("app.search", q=query, page=page + 1)
        if total > page * current_app.config["POSTS_PER_PAGE"]
        else None
    )
    prev_url = url_for("app.search", q=query, page=page - 1) if page > 1 else None

    return render_template(
        "search.html",
        title=_("Search"),
        posts=posts,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route("/notifications")
@login_required
def notifications():
    since = request.args.get("since", 0.0, type=float)
    notifications = current_user.notifications.filter(
        Notification.timestamp > since
    ).order_by(Notification.timestamp.asc())
    return jsonify(
        [
            {"name": n.name, "data": n.get_payload(), "timestamp": n.timestamp}
            for n in notifications
        ]
    )


@bp.route("/messages")
@login_required
def messages():
    current_user.last_message_read_time = datetime.utcnow()
    current_user.add_notification("unread_message_count", 0)
    db.session.commit()

    page = request.args.get("page", 1, type=int)

    messages = current_user.messages_received.order_by(
        Message.timestamp.desc()
    ).paginate(page, current_app.config["POSTS_PER_PAGE"], False)

    next_url = (
        url_for("main.messages", page=messages.next_num) if messages.has_next else None
    )
    prev_url = (
        url_for("main.messages", page=messages.prev_num) if messages.has_prev else None
    )

    return render_template(
        "messages.html", messages=messages.items, next_url=next_url, prev_url=prev_url
    )


@bp.route("/send_message/<recipient>", methods=["GET", "POST"])
@login_required
def send_message(recipient):
    user = User.query.filter_by(username=recipient).first_or_404()
    form = MessageForm()
    if form.validate_on_submit():
        message = Message(author=current_user, recipient=user, body=form.message.data)
        db.session.add(message)
        user.add_notification("unread_message_count", user.new_messages())
        db.session.commit()
        flash(_("Your message has been sent"))
        return redirect(url_for("main.user", username=recipient))
    return render_template(
        "send_message.html", title=_("Send Message"), form=form, recipient=recipient
    )


@bp.route("/translate", methods=["POST"])
def translate_text():
    return jsonify(
        {"text": translate(request.form["text"], request.form["target_language"])}
    )


@bp.route("/users/<username>")
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get("page", 1, type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config["POSTS_PER_PAGE"], False
    )

    next_url = (
        url_for("main.user", username=username, page=posts.next_num)
        if posts.has_next
        else None
    )
    prev_url = (
        url_for("main.user", username=username, page=posts.prev_num)
        if posts.has_prev
        else None
    )

    form = EmptyForm()
    return render_template(
        "user.html",
        user=user,
        posts=posts.items,
        form=form,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route("/users/<username>/popup")
@login_required
def user_popup(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template("user_popup.html", user=user)


@bp.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if not user:
            flash(f"User {username} not found!")
            return redirect(url_for("main.index"))
        if user == current_user:
            flash(_("You cannot follow yourself!"))
            return redirect(url_for("main.user"), username=username)
        current_user.follow(user)
        db.session.commit()
        flash(_("You are now following %(username)s!", username=username))
        return redirect(url_for("main.user", username=username))
    else:
        return redirect(url_for("main.index"))


@bp.route("/unfollow/<username>", methods=["POST"])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if not user:
            flash(f"User {username} not found!")
            return redirect(url_for("main.index"))
        if user == current_user:
            flash(_("You cannot unfollow yourself!"))
            return redirect(url_for("main.user"), username=username)
        current_user.unfollow(user)
        db.session.commit()
        flash(_("You are no longer following %(username)s!", username=username))
        return redirect(url_for("main.user", username=username))
    else:
        return redirect(url_for("main.index"))


@bp.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
    elif request.method == "GET":
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template("edit_profile.html", title="Edit Profile", form=form)


@bp.route("/export_posts")
@login_required
def export_posts():
    if current_user.get_task_in_progress("export_posts"):
        flash(_("An export task is already in progress."))
    else:
        current_user.launch_task("export_posts", _("Exporting posts"))
        db.session.commit()
    return redirect(url_for("main.user", username=current_user.username))
