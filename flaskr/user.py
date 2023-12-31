import os

from flask import Blueprint
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, send_from_directory, current_app
)

from flaskr.db import get_db
from flaskr import ALLOWED_IMAGE_EXTENSIONS
from flaskr.utils import (get_image_extension, allowed_image_file)

bp = Blueprint('user', __name__)

@bp.route('/user/<username>', methods=('GET', 'POST'))
def view(username):
    user = get_db().execute(
        'SELECT u.id, u.username, u.avatar'
        ' FROM user u'
        ' WHERE u.username = ?',
        (username,)
    ).fetchone()

    if user is None:
        abort(404, f"User with username {username} doesn't exist.")

    if request.method == 'POST':
        if 'avatar' in request.files:
            file = request.files['avatar']
            if allowed_image_file(file.filename):
                avatar = username + '.' + get_image_extension(file.filename)
                if user['avatar']:
                    old_filename = os.path.join(current_app.config['USER_AVATAR_FOLDER'], user['avatar'])
                    if os.path.exists(old_filename):
                        os.remove(old_filename)
                file.save(os.path.join(current_app.config['USER_AVATAR_FOLDER'], avatar))

                db = get_db()
                db.execute(
                    'UPDATE user SET avatar = ?'
                    ' WHERE id = ?',
                    (avatar, user['id'])
                )
                db.commit()

    return render_template('user/view.html', user=user)
