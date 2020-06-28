from flask import abort, jsonify, request, url_for

from app import db
from app.api import bp, errors
from app.api.auth import token_auth
from app.models import User


@bp.route("users/<int:id>", methods=["GET"])
@token_auth.login_required
def get_user(id):
    """Return a user."""
    return jsonify(User.query.get_or_404(id).to_dict())


@bp.route("users", methods=["GET"])
@token_auth.login_required
def get_users():
    """Return all users."""
    page = request.args.get("page", type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)

    data = User.to_collection_dict(User.query, page, per_page, "api.get_users")
    return data


@bp.route("users/<int:id>/followers", methods=["GET"])
@token_auth.login_required
def get_followers(id):
    """Return followers of a specific user."""
    user = User.query.get_or_404(id)
    page = request.args.get("page", type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)

    data = User.to_collection_dict(
        user.followers, page, per_page, "api.get_followers", id=id
    )
    return data


@bp.route("users/<int:id>/followed", methods=["GET"])
@token_auth.login_required
def get_followed(id):
    """Return the users followed by a specific user."""
    user = User.query.get_or_404(id)
    page = request.args.get("page", type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)

    data = User.to_collection_dict(
        user.followed, page, per_page, "api.get_followers", id=id
    )
    return data


@bp.route("users", methods=["POST"])
def create_user():
    """Create a new user."""
    data = request.get_json() or {}
    mandatory = ["username", "email", "password"]
    missing = [i for i in mandatory if not data.get(i)]

    # Some sanity checks
    if missing:
        return errors.bad_request(f"Missing mandatory fields in request: {missing}.")
    if User.query.filter_by(username=data["username"]).first():
        return errors.bad_request("Please choose a different username.")
    if User.query.filter_by(email=data["email"]).first():
        return errors.bad_request("Please choose a different email address.")

    user = User()
    user.from_dict(data, new_user=True)
    db.session.add(user)
    db.session.commit()

    response = jsonify(user.to_dict())
    response.status_code = 201
    response.headers["Location"] = url_for("api.get_user", id=user.id)

    return response


@bp.route("users/<int:id>", methods=["PUT"])
@token_auth.login_required
def update_user(id):
    """Update details for a user."""
    if token_auth.current_user().id != id:
        abort(403)

    data = request.get_json() or {}
    user = User.query.get_or_404(id)

    # Sanity checks
    if (
        data.get("username")
        and data["username"] != user.username
        and User.query.filter_by(username=data["username"]).first()
    ):
        return errors.bad_request("Please choose a different username.")
    if (
        data.get("email")
        and data["email"] != user.email
        and User.query.filter_by(email=data["email"]).first()
    ):
        return errors.bad_request("Please choose a different email.")

    user.from_dict(data)
    db.session.commit()

    return jsonify(user.to_dict())
