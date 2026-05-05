"""
src/utils/github_utils.py

Helpers for validating and parsing GitHub repository URLs.

Supported URL formats:
  https://github.com/owner/repo
  https://github.com/owner/repo.git
  https://github.com/owner/repo/tree/<branch>
  git@github.com:owner/repo.git   (SSH — normalized to HTTPS)
"""

import re
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GITHUB_HTTPS_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/?.]+)(\.git)?(/.*)?$",
    re.IGNORECASE,
)

_GITHUB_SSH_RE = re.compile(
    r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/?.]+)(\.git)?$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_valid_github_url(url: str) -> bool:
    """Return *True* if *url* looks like a valid GitHub repository URL."""
    url = url.strip()
    return bool(_GITHUB_HTTPS_RE.match(url) or _GITHUB_SSH_RE.match(url))


def parse_github_url(url: str) -> dict[str, str]:
    """Parse a GitHub URL into owner, repo, and clone_url."""
    url = url.strip()

    # Try HTTPS first
    m = _GITHUB_HTTPS_RE.match(url)
    if m:
        owner = m.group("owner")
        repo = m.group("repo")
        clone_url = f"https://github.com/{owner}/{repo}.git"
        return {"owner": owner, "repo": repo, "clone_url": clone_url}

    # Try SSH
    m = _GITHUB_SSH_RE.match(url)
    if m:
        owner = m.group("owner")
        repo = m.group("repo")
        clone_url = f"https://github.com/{owner}/{repo}.git"
        return {"owner": owner, "repo": repo, "clone_url": clone_url}

    raise ValueError(
        f"Not a valid GitHub repository URL: {url!r}. "
        "Expected formats:\n"
        "  https://github.com/owner/repo\n"
        "  git@github.com:owner/repo.git"
    )
