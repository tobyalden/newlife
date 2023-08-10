from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db

import shortuuid
from urllib.parse import urlparse, parse_qs

from rq import Queue
import redis
from flaskr.utils import convert_mixtape

bp = Blueprint('mixtape', __name__)

pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
redis_conn = redis.Redis()
job_queue = Queue(connection=redis_conn)

@bp.route('/')
def index():
    db = get_db()
    mixtapes = db.execute(
        'SELECT m.id, m.url, m.title, m.body, m.created, m.author_id, u.username'
        ' FROM mixtape m JOIN user u ON m.author_id = u.id'
        ' ORDER BY m.created DESC'
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
        'SELECT m.id, m.locked, m.url, m.title, m.body, m.created, m.author_id, u.username'
        ' FROM mixtape m JOIN user u ON m.author_id = u.id'
        ' WHERE m.id = ?',
        (id,)
    ).fetchone()

    if mixtape is None:
        abort(404, f"Mixtape id {id} doesn't exist.")

    if check_author and mixtape['author_id'] != g.user['id']:
        abort(403)

    return mixtape

def get_mixtape_by_url(url, check_author=True):
    mixtape = get_db().execute(
        'SELECT m.id, m.url, m.locked, m.converted, m.title, m.body, m.created, m.author_id, u.username'
        ' FROM mixtape m JOIN user u ON m.author_id = u.id'
        ' WHERE m.url = ?',
        (url,)
    ).fetchone()

    if mixtape is None:
        abort(404, f"Mixtape with URL {url} doesn't exist.")

    if check_author and (g.user is None or mixtape['author_id'] != g.user['id']):
        abort(403)

    return mixtape

def get_tracks(mixtape_id, check_author=True):
    db = get_db()
    tracks = db.execute(
        'SELECT t.id, t.youtube_id, t.created, t.author_id, u.username'
        ' FROM track t JOIN user u ON t.author_id = u.id'
        ' WHERE t.mixtape_id = ?'
        ' ORDER BY t.created ASC',
        (mixtape_id,)
    ).fetchall()

    # TODO: Probably need to do some validation here

    return tracks

@bp.route('/<url>', methods=('GET', 'POST'))
def view(url):
    mixtape = get_mixtape_by_url(url, False) # TODO: False here should be based on if the mix is public or not
    tracks = get_tracks(mixtape['id'])
    if request.method == 'POST':
        youtube_url = request.form['youtubeUrl']
        error = None

        if not youtube_url:
            error = 'YouTube URL is required.'

        try:
            youtube_id = get_youtube_id(youtube_url)
        except:
            error = "Not a valid YouTube URL."

        if mixtape['locked']:
            error = 'Mixtape is locked and cannot be added to.'

        if error is not None:
            flash(error)
        else:
            db = get_db()

            db.execute(
                'INSERT INTO track (author_id, mixtape_id, youtube_id)'
                ' VALUES (?, ?, ?)',
                (g.user['id'], mixtape['id'], youtube_id)
            )
            db.commit()
            return redirect(url_for('mixtape.view', url=mixtape['url']))

    return render_template('mixtape/view.html', mixtape=mixtape, tracks=tracks)

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
            return redirect(url_for('mixtape.view', url=mixtape['url']))

    return render_template('mixtape/update.html', mixtape=mixtape)

@bp.route('/<int:id>/convert', methods=('GET', 'POST'))
@login_required
def convert(id):
    # TODO: Check you are the owner of the mixtape - this could be a decorator
    mixtape = get_mixtape(id)
    tracks = get_tracks(mixtape['id'])

    error = None

    if mixtape['locked']:
        error = 'Mixtape is locked and cannot be converted.'

    if error is not None:
        flash(error)
    else:
        db = get_db()
        db.execute(
            'UPDATE mixtape SET locked = ?'
            ' WHERE id = ?',
            (True, mixtape['id'])
        )
        db.commit()

        youtube_ids = []
        for track in tracks:
            youtube_ids.append(track['youtube_id'])

        job = job_queue.enqueue(convert_mixtape, youtube_ids, mixtape['id'], mixtape['url'])

        return redirect(url_for('mixtape.view', url=mixtape['url']))

    return render_template('mixtape/update.html', mixtape=mixtape)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    # TODO: Check you are the owner of the mixtape - this could be a decorator
    get_mixtape(id)
    db = get_db()
    db.execute('DELETE FROM mixtape WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('mixtape.index'))

def get_youtube_id(url):
    if url.startswith(('youtu', 'www')):
        url = 'http://' + url

    query = urlparse(url)

    if 'youtube' in query.hostname:
        if query.path == '/watch':
            return parse_qs(query.query)['v'][0]
        elif query.path.startswith(('/embed/', '/v/')):
            return query.path.split('/')[2]
    elif 'youtu.be' in query.hostname:
        return query.path[1:]
    else:
        raise ValueError ## TODO: Don't throw ValueError
