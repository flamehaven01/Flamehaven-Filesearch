"""
Multimodal processing hooks for optional vision delegation.
"""
from __future__ import annotations

import logging
import signal
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Any, Dict, Optional, Protocol

from .config import Config
from .exceptions import FileSizeExceededError

logger = logging.getLogger(__name__)

# Default timeout for vision processing (seconds)
DEFAULT_VISION_TIMEOUT = 30


@contextmanager
def timeout_context(seconds: int):
    """Context manager for timeout enforcement (Unix only)."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Vision processing exceeded {seconds}s timeout")

    # Only enable on Unix-like systems
    if hasattr(signal, 'SIGALRM'):
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows: no signal-based timeout, just yield
        yield


class VisionStrategy(str, Enum):
    FAST = "fast"
    DETAIL = "detail"


@dataclass
class ProcessedImage:
    text: str
    metadata: Dict[str, Any]


class VisionModal(Protocol):
    def describe_image(self, image_bytes: bytes, strategy: VisionStrategy) -> str:
        ...


class NoopVisionModal:
    def describe_image(self, image_bytes: bytes, strategy: VisionStrategy) -> str:
        return ""


class PillowVisionModal:
    def __init__(self):
        try:
            from PIL import Image
        except Exception as exc:
            raise RuntimeError("Pillow is required for vision provider") from exc
        self._image = Image

    def describe_image(self, image_bytes: bytes, strategy: VisionStrategy) -> str:
        image = self._image.open(BytesIO(image_bytes))
        width, height = image.size
        mode = image.mode
        fmt = image.format or "unknown"
        description = f"Image {width}x{height} mode={mode} format={fmt}"
        if strategy == VisionStrategy.DETAIL:
            try:
                sample = image.convert("RGB").resize((1, 1))
                r, g, b = sample.getpixel((0, 0))
                description += f" avg_rgb={r},{g},{b}"
            except Exception:
                pass
        return description


class TesseractVisionModal:
    def __init__(self):
        try:
            from PIL import Image
        except Exception as exc:
            raise RuntimeError("Pillow is required for vision provider") from exc
        try:
            import pytesseract
        except Exception as exc:
            raise RuntimeError("pytesseract is required for OCR provider") from exc
        self._image = Image
        self._tesseract = pytesseract

    def describe_image(self, image_bytes: bytes, strategy: VisionStrategy) -> str:
        image = self._image.open(BytesIO(image_bytes))
        text = self._tesseract.image_to_string(image) or ""
        if strategy == VisionStrategy.DETAIL:
            width, height = image.size
            text = text.strip()
            if text:
                return f"{text}\nImage {width}x{height}"
            return f"Image {width}x{height}"
        return text.strip()


class MultimodalProcessor:
    def __init__(
        self,
        vision_modal: VisionModal,
        strategy: VisionStrategy = VisionStrategy.FAST,
        max_size_mb: int = 10,
        timeout_seconds: int = DEFAULT_VISION_TIMEOUT,
    ):
        self.vision_modal = vision_modal
        self.strategy = strategy
        self.max_size_mb = max_size_mb
        self.timeout_seconds = timeout_seconds

    def describe_image_bytes(self, image_bytes: bytes) -> ProcessedImage:
        if not image_bytes:
            return ProcessedImage(text="", metadata={"status": "empty"})

        # Validate image size
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > self.max_size_mb:
            error_msg = (
                f"Image size {size_mb:.2f}MB exceeds limit of {self.max_size_mb}MB"
            )
            logger.warning(error_msg)
            raise FileSizeExceededError(error_msg)

        try:
            # Apply timeout for vision processing
            with timeout_context(self.timeout_seconds):
                text = self.vision_modal.describe_image(image_bytes, self.strategy)
        except TimeoutError as exc:
            logger.error("Vision processing timeout: %s", exc)
            return ProcessedImage(
                text="",
                metadata={
                    "status": "timeout",
                    "error": str(exc),
                    "timeout_seconds": self.timeout_seconds,
                },
            )
        except Exception as exc:
            logger.warning("Vision processing failed: %s", exc)
            return ProcessedImage(
                text="",
                metadata={"status": "error", "error": str(exc)},
            )
        return ProcessedImage(
            text=text or "",
            metadata={
                "status": "ok",
                "strategy": self.strategy.value,
                "size_mb": round(size_mb, 2),
            },
        )


def _parse_strategy(value: Optional[str]) -> VisionStrategy:
    if not value:
        return VisionStrategy.FAST
    try:
        return VisionStrategy(value.strip().lower())
    except ValueError:
        return VisionStrategy.FAST


def _select_vision_modal(
    config: Config, vision_modal: Optional[VisionModal]
) -> VisionModal:
    if vision_modal is not None:
        return vision_modal
    provider = (config.vision_provider or "auto").strip().lower()
    if provider in {"none", "off", "disabled"}:
        return NoopVisionModal()
    if provider in {"auto", "pillow"}:
        try:
            return PillowVisionModal()
        except Exception as exc:
            logger.warning("Vision provider unavailable: %s", exc)
            if provider == "pillow":
                return NoopVisionModal()
    if provider == "tesseract":
        try:
            return TesseractVisionModal()
        except Exception as exc:
            logger.warning("OCR provider unavailable: %s", exc)
            return NoopVisionModal()
    return NoopVisionModal()


def get_multimodal_processor(
    config: Optional[Config] = None,
    vision_modal: Optional[VisionModal] = None,
) -> Optional[MultimodalProcessor]:
    config = config or Config.from_env()
    if not config.vision_enabled and vision_modal is None:
        return None
    return MultimodalProcessor(
        vision_modal=_select_vision_modal(config, vision_modal),
        strategy=_parse_strategy(config.vision_strategy),
        max_size_mb=config.multimodal_image_max_mb,
        timeout_seconds=DEFAULT_VISION_TIMEOUT,
    )
