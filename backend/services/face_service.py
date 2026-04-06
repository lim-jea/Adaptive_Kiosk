"""
얼굴 분석 서비스 (Cafe Kiosk InsightFace 코드 통합).

InsightFace 설치 실패 시 mock 모드로 폴백하여 서버는 계속 동작.
- buffalo_m 모델: 첫 실행 시 ~/.insightface/models/ 에 자동 다운로드 (~300MB)
- mock 모드: 임의의 분석 결과 반환 (개발/테스트용)
"""
import gc
import base64
import logging
import random
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# InsightFace는 무거운 의존성이라 import 실패 시 mock 모드로 동작
try:
    import cv2
    import numpy as np
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    logger.warning("OpenCV/numpy not installed — face_service will run in mock mode")
    INSIGHTFACE_AVAILABLE = False


@dataclass
class FaceAnalysisResult:
    age_group: str        # 어린이/청년/중장년/노년
    gender: str           # male/female/unknown
    age_est: int          # 추정 나이
    confidence: float     # 0.0~1.0


def _age_to_group(age: float) -> str:
    if age <= 12:
        return "어린이"
    elif age <= 35:
        return "청년"
    elif age <= 55:
        return "중장년"
    else:
        return "노년"


class FaceService:
    """InsightFace 기반 얼굴 분석 싱글턴.
    설치 실패 시 mock 모드로 동작."""

    def __init__(self):
        self._app = None
        self._loaded = False
        self._mock_mode = not INSIGHTFACE_AVAILABLE

    async def load_models(self):
        """InsightFace buffalo_m 모델 로드. 실패 시 mock 모드."""
        if self._loaded:
            return

        if self._mock_mode:
            logger.info("FaceService: running in MOCK mode (no InsightFace)")
            self._loaded = True
            return

        try:
            from insightface.app import FaceAnalysis

            logger.info("Loading InsightFace buffalo_m model...")
            self._app = FaceAnalysis(name="buffalo_m", providers=["CPUExecutionProvider"])
            self._app.prepare(ctx_id=0, det_size=(320, 320))
            logger.info("InsightFace model loaded successfully.")
            self._loaded = True
        except Exception as e:
            logger.warning(f"InsightFace load failed: {e}. Falling back to MOCK mode.")
            self._mock_mode = True
            self._loaded = True

    def _decode_frame(self, b64_str: str):
        """Base64 → OpenCV 이미지"""
        try:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_str)
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as e:
            logger.warning(f"Frame decode failed: {e}")
            return None

    def _analyze_single_frame(self, img) -> Optional[dict]:
        if img is None or self._app is None:
            return None
        faces = self._app.get(img)
        if not faces:
            return None
        # 가장 큰 얼굴 선택
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return {
            "age": float(face.age) if hasattr(face, "age") else 30.0,
            "gender": "male" if (hasattr(face, "gender") and face.gender == 1) else "female",
        }

    def _mock_result(self) -> FaceAnalysisResult:
        """개발/테스트용 mock 결과"""
        age = random.randint(20, 70)
        return FaceAnalysisResult(
            age_group=_age_to_group(age),
            gender=random.choice(["male", "female"]),
            age_est=age,
            confidence=0.85,
        )

    async def analyze(self, frames_b64: list[str]) -> FaceAnalysisResult:
        """프레임 분석 후 평균값 반환. 분석 후 메모리 즉시 파기."""
        if not self._loaded:
            await self.load_models()

        if self._mock_mode:
            return self._mock_result()

        ages, genders, frames = [], [], []
        try:
            for b64 in frames_b64:
                img = self._decode_frame(b64)
                if img is not None:
                    frames.append(img)

            if not frames:
                logger.warning("No valid frames — returning default")
                return FaceAnalysisResult("청년", "unknown", 25, 0.0)

            for img in frames:
                result = self._analyze_single_frame(img)
                if result:
                    ages.append(result["age"])
                    genders.append(result["gender"])

            if not ages:
                logger.warning("No faces detected — returning default")
                return FaceAnalysisResult("청년", "unknown", 25, 0.0)

            avg_age = sum(ages) / len(ages)
            gender = "male" if genders.count("male") >= genders.count("female") else "female"
            return FaceAnalysisResult(
                age_group=_age_to_group(avg_age),
                gender=gender,
                age_est=round(avg_age),
                confidence=min(1.0, len(ages) / len(frames_b64)),
            )
        finally:
            for img in frames:
                del img
            frames.clear()
            gc.collect()


# 전역 싱글턴
face_service = FaceService()
