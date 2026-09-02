"""Persists templates (layouts) as JSON + optional background image, one directory per template."""

from __future__ import annotations

import shutil
from pathlib import Path

from .models import Template


class TemplateStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, template_id: str) -> Path:
        return self.root / template_id

    def save(self, template: Template) -> Template:
        directory = self._dir(template.id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "template.json").write_text(template.model_dump_json(indent=2), encoding="utf-8")
        return template

    def load(self, template_id: str) -> Template:
        path = self._dir(template_id) / "template.json"
        if not path.exists():
            raise FileNotFoundError(f"Template {template_id!r} not found")
        return Template.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[Template]:
        templates = []
        for directory in sorted(self.root.iterdir()):
            path = directory / "template.json"
            if path.exists():
                templates.append(Template.model_validate_json(path.read_text(encoding="utf-8")))
        return templates

    def delete(self, template_id: str) -> None:
        directory = self._dir(template_id)
        if directory.exists():
            shutil.rmtree(directory)

    def save_background_image(self, template_id: str, source_path: str) -> str:
        """Copies an uploaded image into the template's directory and returns its stored path."""
        directory = self._dir(template_id)
        directory.mkdir(parents=True, exist_ok=True)
        dest = directory / f"background{Path(source_path).suffix or '.png'}"
        shutil.copy(source_path, dest)
        return str(dest)
