"""Persists carousels (slide text + metadata) and their rendered slide images."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from .models import Carousel


class CarouselStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, carousel_id: str) -> Path:
        return self.root / carousel_id

    def images_dir(self, carousel_id: str) -> Path:
        directory = self._dir(carousel_id) / "images"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def slide_image_path(self, carousel_id: str, index: int) -> Path:
        return self.images_dir(carousel_id) / f"slide_{index:02d}.png"

    def backgrounds_dir(self, carousel_id: str) -> Path:
        directory = self._dir(carousel_id) / "backgrounds"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def save_slide_background(self, carousel_id: str, index: int, source_path: str) -> str:
        """Copies an uploaded image in as slide `index`'s background, replacing any prior one."""
        directory = self.backgrounds_dir(carousel_id)
        for existing in directory.glob(f"slide_{index:02d}.*"):
            existing.unlink()
        dest = directory / f"slide_{index:02d}{Path(source_path).suffix or '.png'}"
        shutil.copy(source_path, dest)
        return str(dest)

    def save(self, carousel: Carousel) -> Carousel:
        directory = self._dir(carousel.id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "carousel.json").write_text(carousel.model_dump_json(indent=2), encoding="utf-8")
        return carousel

    def load(self, carousel_id: str) -> Carousel:
        path = self._dir(carousel_id) / "carousel.json"
        if not path.exists():
            raise FileNotFoundError(f"Carousel {carousel_id!r} not found")
        return Carousel.model_validate_json(path.read_text(encoding="utf-8"))

    def export_zip(self, carousel_id: str) -> Path:
        images_dir = self.images_dir(carousel_id)
        zip_path = self._dir(carousel_id) / f"{carousel_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for image_path in sorted(images_dir.glob("slide_*.png")):
                archive.write(image_path, arcname=image_path.name)
        return zip_path

    def delete(self, carousel_id: str) -> None:
        directory = self._dir(carousel_id)
        if directory.exists():
            shutil.rmtree(directory)
