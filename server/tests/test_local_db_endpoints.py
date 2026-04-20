import os
import sys
import tempfile
import unittest
import json


os.environ['SUPABASE_DISABLED'] = 'true'
_tmp_db = tempfile.NamedTemporaryFile(prefix='async-code-test-db-', suffix='.json', delete=False)
_tmp_db.close()
os.environ['LOCAL_DB_PATH'] = _tmp_db.name

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)


from main import app  # noqa: E402
from database import DatabaseOperations  # noqa: E402


class LocalDbEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.user_id = 'test-user'
        self._reset_db_file()

    def _reset_db_file(self):
        with open(_tmp_db.name, 'w', encoding='utf-8') as f:
            json.dump({'meta': {'project_id': 1, 'task_id': 1}, 'users': {}, 'projects': [], 'tasks': []}, f)

    def _write_db(self, payload):
        with open(_tmp_db.name, 'w', encoding='utf-8') as f:
            json.dump(payload, f)

    def test_export_missing_auth_header_returns_401(self):
        resp = self.client.get('/local-db/export')
        self.assertEqual(resp.status_code, 401)
        payload = resp.get_json() or {}
        self.assertEqual(payload.get('status'), 'error')

    def test_export_happy_path_returns_expected_counts(self):
        DatabaseOperations.create_project(
            user_id=self.user_id,
            name='test-project',
            description='',
            repo_url='https://github.com/octocat/Hello-World',
            repo_name='Hello-World',
            repo_owner='octocat',
            settings={},
        )
        DatabaseOperations.create_task(
            user_id=self.user_id,
            project_id=None,
            repo_url='https://github.com/octocat/Hello-World',
            target_branch='main',
            agent='codex',
            chat_messages=[{'role': 'user', 'content': 'test', 'timestamp': 'now'}],
        )

        export_resp = self.client.get('/local-db/export', headers={'X-User-ID': self.user_id})
        self.assertEqual(export_resp.status_code, 200)
        payload = export_resp.get_json() or {}
        self.assertEqual(payload.get('status'), 'success')

        data = payload.get('data') or {}
        self.assertEqual(data.get('user_id'), self.user_id)
        self.assertEqual(len(data.get('projects') or []), 1)
        self.assertEqual(len(data.get('tasks') or []), 1)

    def test_export_sanitizes_user_github_token(self):
        self._write_db({
            'meta': {'project_id': 1, 'task_id': 1},
            'users': {
                self.user_id: {
                    'id': self.user_id,
                    'email': 'tester@example.com',
                    'github_token': 'ghp_secret_token',
                }
            },
            'projects': [],
            'tasks': [],
        })

        export_resp = self.client.get('/local-db/export', headers={'X-User-ID': self.user_id})
        self.assertEqual(export_resp.status_code, 200)
        payload = export_resp.get_json() or {}
        self.assertEqual(payload.get('status'), 'success')

        user = (payload.get('data') or {}).get('user') or {}
        self.assertNotIn('github_token', user)
        self.assertEqual(user.get('id'), self.user_id)

    def test_reset_clears_projects_and_tasks(self):
        DatabaseOperations.create_project(
            user_id=self.user_id,
            name='test-project',
            description='',
            repo_url='https://github.com/octocat/Hello-World',
            repo_name='Hello-World',
            repo_owner='octocat',
            settings={},
        )
        DatabaseOperations.create_task(
            user_id=self.user_id,
            project_id=None,
            repo_url='https://github.com/octocat/Hello-World',
            target_branch='main',
            agent='codex',
            chat_messages=[{'role': 'user', 'content': 'test', 'timestamp': 'now'}],
        )

        reset_resp = self.client.post('/local-db/reset', headers={'X-User-ID': self.user_id}, json={})
        self.assertEqual(reset_resp.status_code, 200)
        reset_payload = reset_resp.get_json() or {}
        self.assertEqual(reset_payload.get('status'), 'success')

        export_resp = self.client.get('/local-db/export', headers={'X-User-ID': self.user_id})
        self.assertEqual(export_resp.status_code, 200)
        payload = export_resp.get_json() or {}
        self.assertEqual(payload.get('status'), 'success')

        data = payload.get('data') or {}
        self.assertEqual(len(data.get('projects') or []), 0)
        self.assertEqual(len(data.get('tasks') or []), 0)


if __name__ == '__main__':
    unittest.main()
