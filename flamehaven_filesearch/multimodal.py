"""
Multimodal processing hooks for optional vision delegation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Protocol

from .config import Config

logger = logging.getLogger(__name__)


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


class MultimodalProcessor:
    def __init__(
        self,
        vision_modal: VisionModal,
        strategy: VisionStrategy = VisionStrategy.FAST,
    ):
        self.vision_modal = vision_modal
        self.strategy = strategy

    def describe_image_bytes(self, image_bytes: bytes) -> ProcessedImage:
        if not image_bytes:
            return ProcessedImage(text="", metadata={"status": "empty"})
        try:
            text = self.vision_modal.describe_image(image_bytes, self.strategy)
        except Exception as exc:
            logger.warning("Vision processing failed: %s", exc)
            return ProcessedImage(text="", metadata={"status": "error"})
        return ProcessedImage(
            text=text or "",
            metadata={"status": "ok", "strategy": self.strategy.value},
        )


def _parse_strategy(value: Optional[str]) -> VisionStrategy:
    if not value:
        return VisionStrategy.FAST
    try:
        return VisionStrategy(value.strip().lower())
    except ValueError:
        return VisionStrategy.FAST


def get_multimodal_processor(
    config: Optional[Config] = None,
    vision_modal: Optional[VisionModal] = None,
) -> Optional[MultimodalProcessor]:
    config = config or Config.from_env()
    if not config.vision_enabled and vision_modal is None:
        return None
    return MultimodalProcessor(
        vision_modal=vision_modal or NoopVisionModal(),
        strategy=_parse_strategy(config.vision_strategy),
    )
