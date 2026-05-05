from __future__ import annotations

from fastapi import HTTPException
from starlette.status import (
	HTTP_400_BAD_REQUEST,
	HTTP_404_NOT_FOUND,
	HTTP_422_UNPROCESSABLE_ENTITY,
	HTTP_500_INTERNAL_SERVER_ERROR,
	HTTP_503_SERVICE_UNAVAILABLE,
	HTTP_403_FORBIDDEN,
)

from src.core.models import ErrorResponse

STATUS_MESSAGES = {
	HTTP_400_BAD_REQUEST: "Bad Request",
	HTTP_403_FORBIDDEN: "Forbidden",
	HTTP_404_NOT_FOUND: "Not Found",
	HTTP_422_UNPROCESSABLE_ENTITY: "Unprocessable Entity",
	HTTP_500_INTERNAL_SERVER_ERROR: "Internal Server Error",
	HTTP_503_SERVICE_UNAVAILABLE: "Service Unavailable",
}

class BaseAPIException(HTTPException):
	"""Base exception class for all API exceptions."""

	def __init__(self, status_code: int, error_message: str):
		status_message = STATUS_MESSAGES.get(status_code, "Error")
		super().__init__(
			status_code=status_code,
			detail=ErrorResponse(
				statusCode=status_code,
				statusMessage=status_message,
				errorMessage=error_message,
			).model_dump(),
		)


class InvalidRequestBodyException(BaseAPIException):
	"""Exception for invalid or malformed request bodies."""

	def __init__(self, error: str):
		super().__init__(
			status_code=HTTP_422_UNPROCESSABLE_ENTITY,
			error_message=(
				f"Invalid request body: {error}. "
			),
		)


class InvalidRepoUrlException(BaseAPIException):
	"""Exception for repo URL parsing failures."""

	def __init__(self, url: str):
		super().__init__(
			status_code=HTTP_422_UNPROCESSABLE_ENTITY,
			error_message=f"Cannot parse owner/repo from URL: {url!r}",
		)


class InvalidInputException(BaseAPIException):
	"""Exception for validation or input errors."""

	def __init__(self, error: str):
		super().__init__(
			status_code=HTTP_422_UNPROCESSABLE_ENTITY,
			error_message=f"Invalid input: {error}",
		)


class RepoNotFoundException(BaseAPIException):
	"""Exception for repositories not found on disk."""

	def __init__(self, repo_name: str):
		super().__init__(
			status_code=HTTP_404_NOT_FOUND,
			error_message=(
				f"Repository '{repo_name}' not found locally. "
                "Make sure to ingest the repository before analyzing."
			),
		)


class LlmNotConfiguredException(BaseAPIException):
	"""Exception for missing LLM configuration."""

	def __init__(self, error: str):
		super().__init__(
			status_code=HTTP_503_SERVICE_UNAVAILABLE,
			error_message=f"{error}",
		)


class RepoCloneFailedException(BaseAPIException):
	"""Exception for repository clone failures."""

	def __init__(self, error: str):
		super().__init__(
			status_code=HTTP_500_INTERNAL_SERVER_ERROR,
			error_message=f"Failed to clone repository: {error}",
		)


class FileLoadFailedException(BaseAPIException):
	"""Exception for file loading failures."""

	def __init__(self, error: str):
		super().__init__(
			status_code=HTTP_500_INTERNAL_SERVER_ERROR,
			error_message=f"File loading failed: {error}",
		)


class CodeAnalysisFailedException(BaseAPIException):
	"""Exception for code analysis failures."""

	def __init__(self, error: str):
		super().__init__(
			status_code=HTTP_500_INTERNAL_SERVER_ERROR,
			error_message=f"Code analysis failed: {error}",
		)

