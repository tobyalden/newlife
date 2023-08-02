from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db

import shortuuid

bp = Blueprint('mixtape', __name__)

@bp.route('/')
def index():
    db = get_db()
    mixtapes = db.execute(
        'SELECT p.id, url, title, body, created, author_id, username'
        ' FROM mixtape p JOIN user u ON p.author_id = u.id'
        ' ORDER BY created DESC'
    ).fetchall()
    return render_template('mixtape/index.html', mixtapes=mixtapes)

@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        url = get_uuid()
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO mixtape (title, body, author_id, url)'
                ' VALUES (?, ?, ?, ?)',
                (title, body, g.user['id'], url)
            )
            db.commit()
            return redirect(url_for('mixtape.index'))

    return render_template('mixtape/create.html')

def get_uuid():
    # TODO: Ensure UUIDs are unique and don't conflict with other URLs
    return shortuuid.ShortUUID().random(length=8)

def get_mixtape(id, check_author=True):
    mixtape = get_db().execute(
        'SELECT p.id, title, body, created, author_id, username'
        ' FROM mixtape p JOIN user u ON p.author_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if mixtape is None:
        abort(404, f"Mixtape id {id} doesn't exist.")

    if check_author and mixtape['author_id'] != g.user['id']:
        abort(403)

    return mixtape

def get_mixtape_by_url(url, check_author=True):
    mixtape = get_db().execute(
        'SELECT p.id, url, title, body, created, author_id, username'
        ' FROM mixtape p JOIN user u ON p.author_id = u.id'
        ' WHERE p.url = ?',
        (url,)
    ).fetchone()

    if mixtape is None:
        abort(404, f"Mixtape with URL {url} doesn't exist.")

    if check_author and (g.user is None or mixtape['author_id'] != g.user['id']):
        abort(403)

    return mixtape

@bp.route('/<url>')
def view(url):
    mixtape = get_mixtape_by_url(url, False) # TODO: False here should be based on if the mix is public or not
    return render_template('mixtape/view.html', mixtape=mixtape)

@bp.route('/<url>/update', methods=('GET', 'POST'))
@login_required
def update(url):
    mixtape = get_mixtape_by_url(url)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE mixtape SET title = ?, body = ?'
                ' WHERE id = ?',
                (title, body, mixtape['id'])
            )
            db.commit()
            return redirect(url_for('mixtape.index'))

    return render_template('mixtape/update.html', mixtape=mixtape)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_mixtape(id)
    db = get_db()
    db.execute('DELETE FROM mixtape WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('mixtape.index'))
