import git

from datetime import datetime
from pathlib import Path

from config import REPOS_DIR
from src.core.models import RepoInfo
from src.utils.github_utils import parse_github_url

def clone_or_update_repo( github_url: str, branch: str | None = None) -> RepoInfo:
    """Clone or update a repo and return its metadata."""
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
    except git.GitCommandError as e:
        raise RuntimeError(f"git clone failed for {clone_url}: {e}") from e
    except (git.exc.NoSuchPathError, git.exc.InvalidGitRepositoryError) as e:
        raise RuntimeError(f"invalid destination or repo when cloning to {dest}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"unexpected error cloning {clone_url} to {dest}: {e}") from e


def _pull_repo(local_dir: Path, branch: str | None) -> git.Repo:
    """Open a local clone, optionally checkout a branch, and pull."""
    # Open the repository and validate
    try:
        repo = git.Repo(str(local_dir))
    except git.exc.NoSuchPathError as e:
        raise FileNotFoundError(f"Local repo path not found: {local_dir}") from e
    except git.exc.InvalidGitRepositoryError as e:
        raise RuntimeError(f"Not a git repository: {local_dir}") from e
    except Exception as e:
        raise RuntimeError(f"error opening repository at {local_dir}: {e}") from e

    origin = repo.remotes.origin

    if branch:
        # Checkout the requested branch if it's not already active
        try:
            try:
                current = repo.active_branch.name
            except TypeError:
                current = None

            if current != branch:
                try:
                    repo.git.checkout(branch)
                except git.GitCommandError as e:
                    raise RuntimeError(f"failed to checkout branch '{branch}' in {local_dir}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"error while checking out branch '{branch}' in {local_dir}: {e}") from e

    try:
        origin.pull()
        return repo
    except git.GitCommandError as e:
        raise RuntimeError(f"git pull failed for {local_dir}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"unexpected error pulling {local_dir}: {e}") from e
