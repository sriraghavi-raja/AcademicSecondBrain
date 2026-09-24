"""Account-level operations that touch every store holding a user's data."""

import re
from pathlib import Path
from typing import Any

from src.rag.registry import user_data
from src.services.auth_service import AuthError

SAFE_FILE_COMPONENT = re.compile(r"[A-Za-z0-9_-]+")


class AccountService:
    def __init__(self, auth_service: Any, document_service: Any, output_dir: str = "outputs"):
        self.auth_service = auth_service
        self.document_service = document_service
        # generate_resume writes <user_id>_resume.docx into this folder
        self.output_dir = output_dir

    def delete_user(self, user_id: str) -> None:
        """
        Deletes a user and everything they own: indexed documents, stored files, chats, skills, study and
        career records, generated resumes, and finally the account and its refresh tokens.

        The data goes first and the account last. If a step fails the account still exists, so the caller
        can simply run the deletion again; every step is safe to repeat.
        """
        if self.auth_service.get_user(user_id) is None:
            raise AuthError("User not found")

        self.document_service.delete_all_for_owner(user_id)
        user_data.delete_user_records(user_id)
        self._remove_resume(user_id)
        self.auth_service.delete_user(user_id)

    def _remove_resume(self, user_id: str) -> None:
        if SAFE_FILE_COMPONENT.fullmatch(user_id):
            (Path(self.output_dir) / f"{user_id}_resume.docx").unlink(missing_ok=True)
