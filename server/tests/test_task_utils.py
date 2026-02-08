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


from utils.github import github_repo_full_name, normalize_github_url, parse_github_repo  # noqa: E402
from utils.prompt import get_latest_user_prompt  # noqa: E402


class TaskUtilsTest(unittest.TestCase):
    def test_parse_github_repo_https(self):
        self.assertEqual(
            parse_github_repo('https://github.com/octocat/Hello-World'),
            ('octocat', 'Hello-World')
        )

    def test_parse_github_repo_https_with_git(self):
        self.assertEqual(
            parse_github_repo('https://github.com/octocat/Hello-World.git/'),
            ('octocat', 'Hello-World')
        )

    def test_parse_github_repo_ssh(self):
        self.assertEqual(
            parse_github_repo('git@github.com:octocat/Hello-World.git'),
            ('octocat', 'Hello-World')
        )

    def test_parse_github_repo_invalid(self):
        with self.assertRaises(ValueError):
            parse_github_repo('https://example.com/octocat/Hello-World')

    def test_github_repo_full_name(self):
        self.assertEqual(
            github_repo_full_name('https://github.com/octocat/Hello-World'),
            'octocat/Hello-World'
        )

    def test_normalize_github_url_ssh(self):
        self.assertEqual(
            normalize_github_url('git@github.com:octocat/Hello-World.git'),
            'https://github.com/octocat/Hello-World'
        )

    def test_normalize_github_url_https(self):
        self.assertEqual(
            normalize_github_url('https://github.com/octocat/Hello-World.git/'),
            'https://github.com/octocat/Hello-World'
        )

    def test_get_latest_user_prompt_empty(self):
        self.assertEqual(get_latest_user_prompt({}), '')

    def test_get_latest_user_prompt_no_user(self):
        task = {
            'chat_messages': [
                {'role': 'assistant', 'content': 'hi'}
            ]
        }
        self.assertEqual(get_latest_user_prompt(task), '')

    def test_get_latest_user_prompt_last_user(self):
        task = {
            'chat_messages': [
                {'role': 'user', 'content': 'first'},
                {'role': 'assistant', 'content': 'reply'},
                {'role': 'user', 'content': 'latest'}
            ]
        }
        self.assertEqual(get_latest_user_prompt(task), 'latest')


if __name__ == '__main__':
    unittest.main()
