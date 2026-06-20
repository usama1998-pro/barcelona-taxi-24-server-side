from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status

from app.modules.logs.config import resolve_file_logger_config
from app.modules.logs.read_tail import read_tail_lines


class LogsService:
    def list_log_files(self) -> list[dict]:
        config = resolve_file_logger_config()
        if not config.enabled:
            return []

        directory = Path(config.file_path).parent
        base = Path(config.file_path).name
        names = {base}
        if directory.exists():
            for entry in directory.iterdir():
                if entry.is_file() and (
                    entry.name == base or entry.name.startswith(f"{base}.")
                ):
                    names.add(entry.name)

        files: list[dict] = []
        for name in names:
            row = self._describe_log_file(directory / name, name, base)
            if row:
                files.append(row)

        files.sort(
            key=lambda item: (not item["active"], item["modifiedAt"]),
            reverse=True,
        )
        return files

    def read_latest_lines(self, limit: int, requested_file: str | None = None) -> dict:
        config = resolve_file_logger_config()
        files = self.list_log_files()

        if not config.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File logging is disabled. Set LOG_FILE_ENABLED=true.",
            )

        base = Path(config.file_path).name
        file_name = (requested_file or "").strip() or base
        directory = Path(config.file_path).parent.resolve()
        resolved_path = (directory / file_name).resolve()
        try:
            resolved_path.relative_to(directory)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Log file not found: {file_name}",
            ) from error

        target = next((item for item in files if item["name"] == file_name), None)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Log file not found: {file_name}",
            )

        lines = read_tail_lines(target["path"], limit)
        return {
            "enabled": True,
            "file": target,
            "files": files,
            "lines": lines,
            "lineCount": len(lines),
            "limit": limit,
        }

    def _describe_log_file(
        self,
        file_path: Path,
        name: str,
        active_base_name: str,
    ) -> dict | None:
        if not file_path.exists():
            return None
        stat = file_path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        return {
            "name": name,
            "path": str(file_path),
            "sizeBytes": stat.st_size,
            "modifiedAt": modified,
            "active": name == active_base_name,
        }


logs_service = LogsService()
