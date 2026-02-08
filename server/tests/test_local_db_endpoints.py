import os
import sys
import tempfile
import unittest


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

    def test_requires_auth_header(self):
        resp = self.client.get('/local-db/export')
        self.assertEqual(resp.status_code, 401)

    def test_export_and_reset_local_db(self):
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

        export1 = self.client.get('/local-db/export', headers={'X-User-ID': self.user_id})
        self.assertEqual(export1.status_code, 200)
        payload1 = export1.get_json() or {}
        self.assertEqual(payload1.get('status'), 'success')
        data1 = payload1.get('data') or {}
        self.assertEqual(data1.get('user_id'), self.user_id)
        self.assertEqual(len(data1.get('projects') or []), 1)
        self.assertEqual(len(data1.get('tasks') or []), 1)

        reset = self.client.post('/local-db/reset', headers={'X-User-ID': self.user_id}, json={})
        self.assertEqual(reset.status_code, 200)
        payload_reset = reset.get_json() or {}
        self.assertEqual(payload_reset.get('status'), 'success')

        export2 = self.client.get('/local-db/export', headers={'X-User-ID': self.user_id})
        self.assertEqual(export2.status_code, 200)
        payload2 = export2.get_json() or {}
        self.assertEqual(payload2.get('status'), 'success')
        data2 = payload2.get('data') or {}
        self.assertEqual(len(data2.get('projects') or []), 0)
        self.assertEqual(len(data2.get('tasks') or []), 0)


if __name__ == '__main__':
    unittest.main()
