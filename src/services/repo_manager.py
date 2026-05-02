"""
src/services/repo_manager.py

Repository Manager (Step 2)
============================
Responsible for:
  1. Validating and parsing the incoming GitHub URL.
  2. Cloning the repository to the local ``repos/`` directory.
  3. Re-using an already-cloned copy if one exists (git pull to update it).
  4. Returning a :class:`RepoInfo` instance that downstream steps can consume.

Design notes
------------
* Uses the ``gitpython`` library for all Git operations so that we never
  shell out directly — this gives us proper error handling and cross-platform
  support.
* The local clone lives at  ``<REPOS_DIR>/<owner>__<repo>/``.
* All heavy I/O is synchronous; the FastAPI endpoint runs it in a thread-pool
  via ``asyncio.to_thread`` (see the route handler).
"""

from datetime import datetime
from pathlib import Path

import git  # gitpython

from config import REPOS_DIR
from src.core.models import RepoInfo
from src.utils.github_utils import parse_github_url


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clone_or_update_repo(
    github_url: str,
    branch: str | None = None,
) -> RepoInfo:
    """
    Clone *github_url* into the local cache, or ``git pull`` if it already
    exists.

    Parameters
    ----------
    github_url:
        A validated GitHub repository URL (HTTPS or SSH).
    branch:
        Optional branch / tag to check out after cloning.  When *None* the
        repository's default branch is used.

    Returns
    -------
    RepoInfo
        Metadata object describing the cloned repository.

    Raises
    ------
    ValueError
        If the URL cannot be parsed as a GitHub repository URL.
    git.GitCommandError
        If the clone / pull operation fails (e.g. private repo, network error).
    """
    parsed = parse_github_url(github_url)
    owner: str = parsed["owner"]
    repo_name: str = parsed["repo"]
    clone_url: str = parsed["clone_url"]

    # Deterministic local directory name:  "owner__repo"
    local_dir: Path = REPOS_DIR / f"{owner}__{repo_name}"

    already_existed = local_dir.exists()

    if already_existed:
        repo = _pull_repo(local_dir, branch)
    else:
        repo = _clone_repo(clone_url, local_dir, branch)

    # Resolve the active branch name (may differ from requested branch)
    try:
        active_branch: str | None = repo.active_branch.name
    except TypeError:
        # Detached HEAD (e.g. checked out a tag)
        active_branch = None

    return RepoInfo(
        owner=owner,
        repo=repo_name,
        clone_url=clone_url,
        local_path=local_dir,
        branch=active_branch or branch,
        cloned_at=datetime.utcnow(),
        already_existed=already_existed,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _clone_repo(clone_url: str, dest: Path, branch: str | None) -> git.Repo:
    """Perform a fresh ``git clone`` of *clone_url* into *dest*."""
    kwargs: dict = {
        "url": clone_url,
        "to_path": str(dest),
        "depth": 1,  # shallow clone for speed — no history needed
    }
    if branch:
        kwargs["branch"] = branch

    try:
        repo = git.Repo.clone_from(**kwargs)
        return repo
    except git.GitCommandError:
        raise


def _pull_repo(local_dir: Path, branch: str | None) -> git.Repo:
    """
    Open the existing local clone and pull the latest changes.

    If *branch* is provided and differs from the current branch, check it out.
    """
    try:
        repo = git.Repo(str(local_dir))
        origin = repo.remotes.origin

        if branch:
            # Checkout the requested branch if it's not already active
            try:
                current = repo.active_branch.name
            except TypeError:
                current = None

            if current != branch:
                repo.git.checkout(branch)

        origin.pull()
        return repo
    except git.GitCommandError:
        raise
