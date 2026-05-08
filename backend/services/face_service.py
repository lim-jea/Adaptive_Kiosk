"""
Face analysis service backed by the shared 0424 model.

The imported model code is kept as close as practical to the original shared
script. This service layer only adapts it to the existing API contract:
`analyze(List[str]) -> FaceAnalysisResult`.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import settings

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from insightface.app import FaceAnalysis

    RUNTIME_AVAILABLE = True
except ImportError as exc:
    logger.warning("Vision dependencies unavailable: %s", exc)
    cv2 = None
    np = None
    torch = None
    nn = None
    F = None
    FaceAnalysis = None
    RUNTIME_AVAILABLE = False


@dataclass
class FaceAnalysisResult:
    age_group: str
    gender: str
    age_est: int
    confidence: float


def _age_to_group(age: float) -> str:
    if age <= 12:
        return "아동"
    if age <= 35:
        return "청년"
    if age <= 55:
        return "중장년"
    return "노년"


def _normalize_gender(gender_value: int) -> str:
    return "female" if gender_value == 1 else "male"


if RUNTIME_AVAILABLE:
    class ResidualBlock(nn.Module):
        def __init__(self, dim: int, dropout: float = 0.5):
            super().__init__()
            self.fc1 = nn.Linear(dim, dim)
            self.bn1 = nn.BatchNorm1d(dim)
            self.fc2 = nn.Linear(dim, dim)
            self.bn2 = nn.BatchNorm1d(dim)
            self.dropout = nn.Dropout(dropout)
            self.gelu = nn.GELU()

        def forward(self, x):
            residual = x
            out = self.gelu(self.bn1(self.fc1(x)))
            out = self.dropout(out)
            out = self.bn2(self.fc2(out))
            return self.gelu(out + residual)


    class FeatureAttention(nn.Module):
        def __init__(self, dim: int, num_heads: int = 8):
            super().__init__()
            self.attention = nn.MultiheadAttention(
                embed_dim=dim,
                num_heads=num_heads,
                batch_first=True,
                dropout=0.3,
            )

        def forward(self, x):
            x_seq = x.unsqueeze(1)
            attn_output, _ = self.attention(x_seq, x_seq, x_seq)
            return attn_output.squeeze(1)


    class KioskMultiTaskHead(nn.Module):
        def __init__(self):
            super().__init__()
            self.attention_layer = FeatureAttention(dim=512, num_heads=8)

            self.age_network = nn.Sequential(
                nn.Linear(512, 512),
                nn.BatchNorm1d(512),
                nn.GELU(),
                nn.Dropout(0.5),
                ResidualBlock(512, dropout=0.5),
                ResidualBlock(512, dropout=0.5),
                nn.Linear(512, 256),
                nn.BatchNorm1d(256),
                nn.GELU(),
                nn.Dropout(0.5),
                nn.Linear(256, 101),
            )
            self.register_buffer("age_bins", torch.arange(0, 101, dtype=torch.float32))

            self.gender_network = nn.Sequential(
                nn.Linear(512, 256),
                nn.BatchNorm1d(256),
                nn.GELU(),
                nn.Dropout(0.5),
                ResidualBlock(256, dropout=0.5),
                nn.Linear(256, 1),
            )

        def forward(self, features):
            x = F.normalize(features, p=2, dim=1)
            attended_features = self.attention_layer(x)
            fused_features = x + attended_features

            gender_logits = self.gender_network(fused_features)
            age_logits = self.age_network(fused_features)
            age_probs = F.softmax(age_logits, dim=1)
            expected_age = torch.sum(age_probs * self.age_bins, dim=1, keepdim=True)
            return age_logits, expected_age, gender_logits
else:
    class KioskMultiTaskHead:  # pragma: no cover - only used in missing-dependency fallback
        pass


class FaceService:
    def __init__(self):
        self._app = None
        self._model = None
        self._device = None
        self._loaded = False
        self._load_error: Optional[str] = None
        self._model_path = self._resolve_model_path(settings.FACE_MODEL_PATH)
        self._insightface_model_name = settings.FACE_INSIGHTFACE_MODEL_NAME
        self._det_score_threshold = settings.FACE_DETECTION_SCORE_THRESHOLD
        self._min_face_size = settings.FACE_MIN_FACE_SIZE
        self._min_valid_frames = settings.FACE_MIN_VALID_FRAMES

    @staticmethod
    def _resolve_model_path(model_path: str) -> Path:
        path = Path(model_path)
        if path.is_absolute():
            return path
        backend_root = Path(__file__).resolve().parents[1]
        repo_root = backend_root.parent
        backend_relative = backend_root / path
        if backend_relative.exists():
            return backend_relative
        return repo_root / path

    async def load_models(self):
        if self._loaded:
            return

        if not RUNTIME_AVAILABLE:
            self._load_error = "required vision packages are not installed"
            self._loaded = True
            return

        if not self._model_path.exists():
            self._load_error = f"model weights not found: {self._model_path}"
            self._loaded = True
            return

        try:
            self._device = torch.device(
                "cuda" if settings.FACE_USE_CUDA and torch.cuda.is_available() else "cpu"
            )

            self._model = KioskMultiTaskHead().to(self._device)
            state_dict = torch.load(self._model_path, map_location=self._device)
            self._model.load_state_dict(state_dict)
            self._model.eval()

            providers = ["CPUExecutionProvider"]
            if settings.FACE_USE_CUDA and torch.cuda.is_available():
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

            self._app = FaceAnalysis(
                name=self._insightface_model_name,
                providers=providers,
            )
            ctx_id = 0 if settings.FACE_USE_CUDA and torch.cuda.is_available() else -1
            self._app.prepare(
                ctx_id=ctx_id,
                det_size=(
                    settings.FACE_DETECTION_WIDTH,
                    settings.FACE_DETECTION_HEIGHT,
                ),
            )

            self._loaded = True
            self._load_error = None
            logger.info(
                "Face service ready with shared 0424 model (%s, insightface=%s)",
                self._model_path,
                self._insightface_model_name,
            )
        except Exception as exc:
            self._loaded = True
            self._load_error = str(exc)
            logger.warning("Face service model load failed: %s", exc)

    def _decode_frame(self, b64_str: str):
        try:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_str)
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as exc:
            logger.warning("Frame decode failed: %s", exc)
            return None

    def _infer_face(self, face) -> Optional[tuple[int, int]]:
        bbox = face.bbox.astype(int)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width < self._min_face_size or height < self._min_face_size:
            return None
        if float(face.det_score) < self._det_score_threshold:
            return None
        if not hasattr(face, "embedding") or face.embedding is None:
            return None

        embedding = torch.from_numpy(face.embedding).float().unsqueeze(0).to(self._device)
        with torch.no_grad():
            _, expected_age, gender_logits = self._model(embedding)

        age = int(torch.round(expected_age).item())
        gender_prob = torch.sigmoid(gender_logits).item()
        gender_value = 1 if gender_prob >= 0.5 else 0
        return age, gender_value

    def _analyze_frame(self, frame) -> Optional[tuple[int, int]]:
        if self._app is None or self._model is None or frame is None:
            return None

        faces = self._app.get(frame, max_num=3)
        for face in faces:
            result = self._infer_face(face)
            if result is not None:
                return result
        return None

    def _fallback_result(self) -> FaceAnalysisResult:
        logger.warning("Using fallback face analysis result: %s", self._load_error)
        return FaceAnalysisResult(
            age_group="청년",
            gender="unknown",
            age_est=25,
            confidence=0.0,
        )

    def _analyze_sync(self, frames_b64: list[str]) -> FaceAnalysisResult:
        ages: list[int] = []
        genders: list[int] = []

        for b64 in frames_b64:
            frame = self._decode_frame(b64)
            result = self._analyze_frame(frame)
            if result is None:
                continue
            age, gender_value = result
            ages.append(age)
            genders.append(gender_value)
            if len(ages) >= self._min_valid_frames:
                break

        if not ages:
            logger.warning("No usable faces detected from provided frames")
            return FaceAnalysisResult(
                age_group="청년",
                gender="unknown",
                age_est=25,
                confidence=0.0,
            )

        final_age = int(np.median(ages))
        final_gender_value = 1 if sum(genders) > (len(genders) / 2) else 0
        confidence = min(1.0, len(ages) / max(1, len(frames_b64)))
        return FaceAnalysisResult(
            age_group=_age_to_group(final_age),
            gender=_normalize_gender(final_gender_value),
            age_est=final_age,
            confidence=confidence,
        )

    async def analyze(self, frames_b64: list[str]) -> FaceAnalysisResult:
        if not self._loaded:
            await self.load_models()

        if self._app is None or self._model is None or self._device is None:
            return self._fallback_result()

        return await asyncio.to_thread(self._analyze_sync, frames_b64)


face_service = FaceService()
