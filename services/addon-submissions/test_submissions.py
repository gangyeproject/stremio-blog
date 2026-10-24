import hashlib
import io
import json
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

import app
import safe_remote
import worker
from store import Store


MANIFEST = {'id': 'org.example.sample', 'name': 'Sample Catalog', 'description': 'A catalog of freely available educational movies.',
            'version': '1.0.0', 'types': ['movie'], 'resources': ['catalog'], 'catalogs': [{'id': 'sample', 'type': 'movie'}]}
PAYLOAD = {'name': 'Sample Catalog', 'manifestUrl': 'https://example.com/manifest.json',
           'description': 'A catalog of freely available educational movies for Stremio.', 'author': 'Anonymous', 'iconUrl': ''}
PROFILE = {'title': 'Sample Catalog: Educational Movies', 'summary': 'Explore freely available educational movies.',
           'content': 'Sample Catalog brings a collection of educational movies to Stremio.\n\n## Catalog\n\nBrowse the available titles.'}


class RemoteTests(unittest.TestCase):
    def test_public_url_restrictions(self):
        for url in ['http://example.com/manifest.json', 'file:///etc/passwd', 'https://user:pass@example.com/manifest.json',
                    'https://127.0.0.1/manifest.json', 'https://169.254.169.254/manifest.json', 'https://104.168.83.194/manifest.json',
                    'https://example.com:1337/manifest.json', 'https://example.com/manifest.json?api_key=secret',
                    'https://example.com/manifest.json#secret', 'https://localhost/manifest.json', 'https://test.local/manifest.json',
                    'https://admin.stremioaddonmanager.org/manifest.json', 'https://example.com\\@127.0.0.1/manifest.json']:
            with self.subTest(url=url), self.assertRaises(safe_remote.InvalidSubmission):
                safe_remote.public_url(url, manifest=True)
        self.assertEqual(safe_remote.public_url('https://EXAMPLE.COM:443/manifest.json', True), PAYLOAD['manifestUrl'])

    def test_nonmanifest_rejected(self):
        with self.assertRaises(safe_remote.InvalidSubmission):
            safe_remote.public_url('https://example.com/configure', True)

    def test_private_and_mixed_dns_rejected(self):
        for address in ['127.0.0.1', '10.0.0.1', '169.254.169.254', '192.168.1.1', '::1', '::ffff:127.0.0.1', '104.168.83.194', '224.0.0.1']:
            records = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443)),
                       (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
            with self.subTest(address=address), patch('safe_remote.socket.getaddrinfo', return_value=records), self.assertRaises(safe_remote.InvalidSubmission):
                safe_remote.public_addresses('example.com')

    def test_pinned_connection_and_redirect_revalidation(self):
        response = Mock(status=302, headers={'Location': 'https://private.example.com/manifest.json'})
        with patch('safe_remote.public_addresses', side_effect=[['8.8.8.8'], safe_remote.InvalidSubmission('private')]), \
             patch('safe_remote.urllib3.HTTPSConnectionPool') as pool:
            pool.return_value.urlopen.return_value = response
            with self.assertRaises(safe_remote.InvalidSubmission):
                safe_remote.safe_get(PAYLOAD['manifestUrl'])
            self.assertEqual(pool.call_args.args[0], '8.8.8.8')
            self.assertEqual(pool.call_args.kwargs['server_hostname'], 'example.com')
            self.assertFalse(pool.return_value.urlopen.call_args.kwargs['redirect'])
            self.assertFalse(pool.return_value.urlopen.call_args.kwargs['retries'])

    def test_size_cap(self):
        response = Mock(status=200, headers={}, read=Mock(return_value=b'12345'))
        with patch('safe_remote.public_addresses', return_value=['8.8.8.8']), patch('safe_remote.urllib3.HTTPSConnectionPool') as pool:
            pool.return_value.urlopen.return_value = response
            with self.assertRaises(safe_remote.InvalidSubmission):
                safe_remote.safe_get(PAYLOAD['manifestUrl'], limit=4)

    def test_manifest(self):
        self.assertEqual(safe_remote.validate_manifest(json.dumps(MANIFEST))['id'], MANIFEST['id'])
        for changes in [{'resources': []}, {'version': 'no'}, {'types': []}, {'catalogs': []},
                        {'behaviorHints': {'configurationRequired': True}}, {'name': ''}, {'catalogs': [{'id': 'x', 'type': 'unknown'}]}]:
            with self.subTest(changes=changes), self.assertRaises(safe_remote.InvalidSubmission):
                safe_remote.validate_manifest(json.dumps({**MANIFEST, **changes}))

    def test_icon_is_reencoded_and_optional(self):
        self.assertIsNone(safe_remote.sanitized_icon(''))
        original = io.BytesIO()
        Image.new('RGB', (100, 100), 'purple').save(original, format='PNG')
        with patch('safe_remote.safe_get', return_value=(original.getvalue(), 'image/png', 'https://example.com/icon.png')):
            result = safe_remote.sanitized_icon('https://example.com/icon.png')
            self.assertEqual(Image.open(io.BytesIO(result)).format, 'PNG')
        with patch('safe_remote.safe_get', return_value=(b'<svg></svg>', 'image/svg+xml', 'https://example.com/icon.svg')), self.assertRaises(safe_remote.InvalidSubmission):
            safe_remote.sanitized_icon('https://example.com/icon.svg')


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = app.create_app({'DB_PATH': str(Path(self.directory.name) / 'queue.db'), 'SECRET': 'x' * 64,
                                  'TESTING': True, 'ORIGINS': ['https://stremioaddonmanager.org']})
        self.client = self.app.test_client()
        self.headers = {'Origin': 'https://stremioaddonmanager.org'}

    def body(self):
        with patch('app.time.time', return_value=time.time() - 4):
            challenge = self.client.post('/addon-submissions/challenge', headers=self.headers, json={}).json['challenge']
        return {**PAYLOAD, 'author': '', 'consent': True, 'challenge': challenge}

    def test_anonymous_idempotency_and_private_status(self):
        body = self.body()
        response = self.client.post('/addon-submissions/submit', headers=self.headers, json=body)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json['state'], 'queued')
        repeated = self.client.post('/addon-submissions/submit', headers=self.headers, json=body)
        self.assertEqual(repeated.json['ticket'], response.json['ticket'])
        store = self.app.extensions['store']
        with store.connect() as connection:
            row = connection.execute('SELECT * FROM submissions').fetchone()
            self.assertEqual(json.loads(row['payload'])['author'], 'Anonymous')
        status = self.client.post('/addon-submissions/status', headers=self.headers, json={'ticket': response.json['ticket']}).json
        self.assertEqual(set(status), {'state', 'message', 'url', 'updated', 'preview'})
        self.assertIsNone(status['url'])

    def test_duplicates(self):
        self.client.post('/addon-submissions/submit', headers=self.headers, json=self.body())
        result = self.client.post('/addon-submissions/submit', headers=self.headers, json=self.body())
        self.assertEqual(result.status_code, 409)

    def test_untrusted_origin_and_malformed_data(self):
        self.assertEqual(self.client.post('/addon-submissions/challenge', headers={'Origin': 'https://evil.example'}, json={}).status_code, 403)
        self.assertEqual(self.client.post('/addon-submissions/submit', headers=self.headers, json=[]).status_code, 400)
        self.assertEqual(self.client.post('/addon-submissions/submit', headers=self.headers, data='bad').status_code, 415)

    def test_consent_and_honeypot(self):
        for change in [{'consent': False}, {'website': 'spam'}, {'name': '<script>'}, {'challenge': 'forged'}]:
            with self.subTest(change=change):
                response = self.client.post('/addon-submissions/submit', headers=self.headers, json={**self.body(), **change})
                self.assertEqual(response.status_code, 400)

    def test_per_network_limit_and_unknown_receipt(self):
        for index in range(4):
            body = self.body()
            body['manifestUrl'] = f'https://example.com/{index}/manifest.json'
            response = self.client.post('/addon-submissions/submit', headers=self.headers, json=body)
            self.assertEqual(response.status_code, 202 if index < 3 else 429)
        self.assertEqual(self.client.post('/addon-submissions/status', headers=self.headers, json={'ticket': 'b' * 64}).status_code, 404)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / 'queue.db')
        self.ticket = 'a' * 64
        self.store.enqueue(PAYLOAD, 'ip', 'nonce', self.ticket)
        self.session = Mock()

    def test_preview_never_publishes(self):
        with patch('worker.existing_addons', return_value=[]), patch('worker.safe_get', return_value=(json.dumps(MANIFEST), 'application/json', PAYLOAD['manifestUrl'])), \
             patch('worker.ReviewAI'), patch('worker.publisher.generate_addon_profile', return_value=PROFILE), \
             patch('worker.upload_icon') as upload, patch('worker.create_once') as publish:
            worker.run_once(self.store, self.session, False)
            self.assertEqual(self.store.status(self.ticket)['state'], 'approved_preview')
            publish.assert_not_called()
            upload.assert_not_called()

    def test_approved_publish_and_deployment_are_separate(self):
        with patch('worker.existing_addons', return_value=[]), patch('worker.safe_get', return_value=(json.dumps(MANIFEST), 'application/json', PAYLOAD['manifestUrl'])), \
             patch('worker.ReviewAI'), patch('worker.publisher.generate_addon_profile', return_value=PROFILE), \
             patch('worker.upload_icon', return_value=''), patch('worker.create_once') as publish:
            worker.run_once(self.store, self.session, True)
            status = self.store.status(self.ticket)
            self.assertEqual(status['state'], 'deploying')
            self.assertIsNone(status['url'])
            data = publish.call_args.args[1]
            self.assertIn('Anonymous', data['content'])
            self.assertEqual(data['title'], MANIFEST['name'])
            self.assertNotIn('![', data['content'])
            with self.store.connect() as connection:
                connection.execute('UPDATE submissions SET next_attempt=0')
            with patch('worker.live_visible', return_value=True):
                worker.run_once(self.store, self.session, True)
            self.assertEqual(self.store.status(self.ticket)['state'], 'published')

    def test_transient_failure_does_not_publish(self):
        with patch('worker.existing_addons', side_effect=RuntimeError('offline')), patch('worker.create_once') as publish:
            worker.run_once(self.store, self.session, True)
            self.assertEqual(self.store.status(self.ticket)['state'], 'retrying')
            publish.assert_not_called()

    def test_live_verification_requires_matching_detail_and_listing(self):
        data = {'title': 'Sample Catalog', 'manifestUrl': PAYLOAD['manifestUrl']}
        slug = 'community-sample-0123456789ab'
        valid_detail = '<article class="addon-article"><h1>Sample Catalog</h1><a href="stremio://example.com/manifest.json">Install</a><p>Author (as submitted): Anonymous</p></article>'
        valid_listing = f'<a href="/blog/addons/{slug}">Sample Catalog</a>'
        for detail, listing, expected in [
            (valid_detail, valid_listing, True),
            ('<h1>Not found</h1>Author', valid_listing, False),
            (valid_detail.replace('Sample Catalog', 'Wrong addon'), valid_listing, False),
            (valid_detail.replace('example.com', 'wrong.example.com'), valid_listing, False),
            (valid_detail, '<p>No addons found</p>', False),
        ]:
            with self.subTest(detail=detail, listing=listing):
                self.session.get.side_effect = [Mock(status_code=200, text=detail), Mock(status_code=200, text=listing)]
                self.assertEqual(worker.live_visible(self.session, slug, data), expected)

    def test_duplicate_skips_ai(self):
        with patch('worker.existing_addons', return_value=[{'manifestUrl': PAYLOAD['manifestUrl']}]), patch('worker.ReviewAI') as ai:
            worker.run_once(self.store, self.session, True)
            self.assertEqual(self.store.status(self.ticket)['state'], 'rejected')
            ai.assert_not_called()

    def test_manifest_failure_cannot_publish(self):
        with patch('worker.existing_addons', return_value=[]), patch('worker.safe_get', side_effect=safe_remote.InvalidSubmission('invalid manifest')), patch('worker.create_once') as publish:
            worker.run_once(self.store, self.session, True)
            self.assertEqual(self.store.status(self.ticket)['state'], 'rejected')
            publish.assert_not_called()

    def test_model_and_review_fail_closed(self):
        good = {**PROFILE, 'decision': 'approve', 'audience': 'general', 'confidence': .99, 'reason_code': 'ok'}
        for model, review, expected in [('other-model', good, RuntimeError), (None, good, RuntimeError),
                                        ('gpt-6-astra', {**good, 'audience': 'adult'}, worker.ReviewRejected),
                                        ('gpt-6-astra', {**good, 'confidence': .4}, worker.ReviewRejected),
                                        ('gpt-6-astra', {**good, 'confidence': True}, worker.ReviewRejected),
                                        ('gpt-6-astra', {**good, 'decision': 'uncertain'}, worker.ReviewRejected)]:
            response = Mock()
            response.json.return_value = {'model': model, 'output_text': json.dumps(review)}
            self.session.post.return_value = response
            with self.subTest(model=model, review=review), patch.dict(os.environ, {'OPENAI_BASE_URL': 'https://example.com/v1', 'OPENAI_API_KEY': 'test'}):
                ai = worker.ReviewAI(self.session, b'icon', {'submission': PAYLOAD}, self.store)
                with self.assertRaises(expected):
                    ai.generate_json('instructions', 'evidence')
                request = self.session.post.call_args.kwargs['json']
                self.assertEqual(request['model'], 'gpt-6-astra')
                self.assertEqual(request['input'][0]['content'][1]['type'], 'input_image')

    def test_restart_reconciles_approved_publication_without_ai(self):
        data = {'title': 'Sample', 'content': 'Approved', 'manifestUrl': PAYLOAD['manifestUrl'], 'sulg': 'community-sample-0123456789ab'}
        with self.store.connect() as connection:
            identity = connection.execute('SELECT id FROM submissions').fetchone()['id']
        self.store.update(identity, publication=json.dumps(data), slug=data['sulg'])
        with patch('worker.create_once') as publish, patch('worker.ReviewAI') as ai:
            worker.run_once(self.store, self.session, True)
            publish.assert_called_once()
            ai.assert_not_called()

    def test_post_timeout_reconciliation_does_not_create_twice(self):
        data = {'sulg': 'community-sample-0123456789ab', 'manifestUrl': PAYLOAD['manifestUrl'], 'content': 'Approved'}
        existing = {**data, 'publishedAt': '2026-10-24'}
        with patch.dict(os.environ, {'STRAPI_API_TOKEN': 'test'}), patch('worker.publisher.StrapiClient') as client:
            client.return_value.list_all.return_value = [existing]
            worker.create_once(self.session, data)
            self.session.post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
