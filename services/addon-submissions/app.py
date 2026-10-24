import hashlib
import hmac
import os
import re
import secrets
import time

from flask import Flask, jsonify, request

from safe_remote import InvalidSubmission, public_url
from store import Store


def create_app(settings=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=16384, DB_PATH=os.getenv('SUBMISSIONS_DB', '/var/lib/stremio-submissions/queue.sqlite3'),
                      SECRET=os.getenv('SUBMISSIONS_SECRET', ''), PREVIEW=os.getenv('PUBLISH_ENABLED', 'false') != 'true',
                      ORIGINS=os.getenv('SUBMISSIONS_ORIGINS', 'https://stremioaddonmanager.org,https://www.stremioaddonmanager.org').split(','))
    if settings:
        app.config.update(settings)
    if len(app.config['SECRET']) < 32:
        raise RuntimeError('SUBMISSIONS_SECRET must be configured')
    store = Store(app.config['DB_PATH'])
    app.extensions['store'] = store

    def sign(value):
        return hmac.new(app.config['SECRET'].encode(), value.encode(), hashlib.sha256).hexdigest()

    def identity():
        address = request.headers.get('X-Real-IP', '') if request.remote_addr == '127.0.0.1' else request.remote_addr
        return sign('ip:' + (address or request.remote_addr or 'unknown'))

    @app.before_request
    def guard():
        if request.path == '/addon-submissions/health':
            return None
        if request.headers.get('Origin') not in app.config['ORIGINS']:
            return jsonify(error='This origin is not allowed.'), 403
        if request.method == 'OPTIONS':
            return '', 204
        if request.method != 'POST' or not request.is_json:
            return jsonify(error='Send a JSON POST request.'), 415
        if not store.rate('requests', identity(), 180, 600):
            return jsonify(error='Too many requests. Please try again later.'), 429

    @app.after_request
    def headers(response):
        if request.headers.get('Origin') in app.config['ORIGINS']:
            response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
            response.headers['Vary'] = 'Origin'
            response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.errorhandler(400)
    @app.errorhandler(413)
    def bad_request(error):
        return jsonify(error='The request is invalid or too large.'), error.code

    @app.get('/addon-submissions/health')
    def health():
        return jsonify(ok=True, preview=app.config['PREVIEW'])

    @app.post('/addon-submissions/challenge')
    def challenge():
        if not store.rate('challenge', identity(), 20, 3600):
            return jsonify(error='Please wait before starting another submission.'), 429
        value = f'{int(time.time())}.{secrets.token_hex(16)}'
        return jsonify(challenge=value + '.' + sign(value + ':' + identity()), preview=app.config['PREVIEW'])

    @app.post('/addon-submissions/submit')
    def submit():
        if not store.rate('submit', identity(), 10, 3600):
            return jsonify(error='Too many submissions. Please try again later.'), 429
        body = request.get_json()
        if not isinstance(body, dict):
            return jsonify(error='Invalid form data.'), 400
        challenge = body.get('challenge', '')
        try:
            stamp, nonce, signature = challenge.split('.')
            age = time.time() - int(stamp)
            if not re.fullmatch('[a-f0-9]{32}', nonce) or not 2 <= age <= 7200 or not hmac.compare_digest(signature, sign(stamp + '.' + nonce + ':' + identity())):
                raise ValueError()
        except (ValueError, AttributeError, TypeError):
            return jsonify(error='The form session expired or is not ready. Please reload and try again.'), 400
        if body.get('website') or body.get('consent') is not True:
            return jsonify(error='Please confirm the submission rules.'), 400
        payload = {}
        for key, minimum, maximum in [('name', 2, 80), ('author', 0, 80), ('description', 40, 3000), ('iconUrl', 0, 2048), ('manifestUrl', 1, 2048)]:
            value = body.get(key, '')
            if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', value):
                return jsonify(error=f'Check the {key} field and its length.'), 400
            payload[key] = value.strip()
        if re.search(r'[<>\r\n]|https?://', payload['name'] + payload['author'], re.I):
            return jsonify(error='Names must be plain text, without links or HTML.'), 400
        try:
            payload['manifestUrl'] = public_url(payload['manifestUrl'], manifest=True)
            if payload['iconUrl']:
                payload['iconUrl'] = public_url(payload['iconUrl'])
        except InvalidSubmission as exc:
            return jsonify(error=str(exc)), 400
        payload['author'] = payload['author'] or 'Anonymous'
        ticket = sign('receipt:' + nonce)
        result = store.enqueue(payload, identity(), nonce, ticket)
        if result == 'limited':
            return jsonify(error='The submission limit has been reached. Try again tomorrow.'), 429
        if result == 'duplicate':
            return jsonify(error='This manifest has already been submitted. Use your saved receipt to check its status.'), 409
        return jsonify(ticket=ticket, preview=app.config['PREVIEW'], **store.status(ticket)), 202

    @app.post('/addon-submissions/status')
    def status():
        body = request.get_json()
        ticket = body.get('ticket', '') if isinstance(body, dict) else ''
        if not isinstance(ticket, str) or not re.fullmatch('[a-f0-9]{64}', ticket):
            return jsonify(error='Invalid submission receipt.'), 400
        result = store.status(ticket)
        if not result:
            return jsonify(error='No submission was found for this receipt.'), 404
        return jsonify(preview=app.config['PREVIEW'], **result)

    return app
