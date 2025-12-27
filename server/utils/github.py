import re

_GITHUB_HTTPS_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
_GITHUB_SSH_RE = re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$")


def parse_github_repo(repo_url: str) -> tuple[str, str]:
    """Parse a GitHub repo URL into (owner, repo). Supports https and git@ URLs."""
    if not repo_url:
        raise ValueError("repo_url 不能为空")
    url = repo_url.strip()

    https = _GITHUB_HTTPS_RE.match(url)
    if https:
        return https.groups()

    ssh = _GITHUB_SSH_RE.match(url)
    if ssh:
        return ssh.groups()

    raise ValueError(f"GitHub 地址格式无效: {repo_url}")


def github_repo_full_name(repo_url: str) -> str:
    """Return GitHub repo full name 'owner/repo' from URL."""
    owner, repo = parse_github_repo(repo_url)
    return f"{owner}/{repo}"


def normalize_github_url(repo_url: str) -> str:
    """Normalize GitHub repo URL to HTTPS canonical form."""
    owner, repo = parse_github_repo(repo_url)
    return f"https://github.com/{owner}/{repo}"
