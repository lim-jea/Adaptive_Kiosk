"""
얼굴 분석 서비스 (스마트 마스크 라우팅 + Custom PyTorch Model 통합).
"""
import os
import gc
import base64
import logging
import random
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# InsightFace 및 PyTorch 의존성 확인 (실패 시 mock 모드)
try:
    import cv2
    import numpy as np
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from insightface.app import FaceAnalysis
    AI_DEPS_AVAILABLE = True
except ImportError:
    logger.warning("OpenCV/numpy/torch/insightface not installed — face_service will run in mock mode")
    AI_DEPS_AVAILABLE = False


# ==========================================
# 1. Custom PyTorch Model Definitions
# ==========================================
if AI_DEPS_AVAILABLE:
    # 1-A. 기존 베이스 모델 (마스크 미착용 시 사용)
    class KioskMultiTaskHead(nn.Module):
        def __init__(self):
            super(KioskMultiTaskHead, self).__init__()
            self.age_head = nn.Sequential(
                nn.Linear(512, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.4), nn.Linear(512, 101)
            )
            self.register_buffer('age_bins', torch.arange(0, 101, dtype=torch.float32))
            self.gender_head = nn.Sequential(
                nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.4), nn.Linear(256, 1)
            )

        def forward(self, features):
            gender_logits = self.gender_head(features)
            age_logits = self.age_head(features)
            age_probs = F.softmax(age_logits, dim=1)
            expected_age = torch.sum(age_probs * self.age_bins, dim=1, keepdim=True) 
            return age_logits, expected_age, gender_logits

    # 1-B. 신규 마스크 어댑터 모델 (마스크 착용 시 사용)
    class ResidualBlock(nn.Module):
        def __init__(self, dim, dropout=0.5):
            super(ResidualBlock, self).__init__()
            self.fc1 = nn.Linear(dim, dim); self.bn1 = nn.BatchNorm1d(dim)
            self.fc2 = nn.Linear(dim, dim); self.bn2 = nn.BatchNorm1d(dim)
            self.dropout = nn.Dropout(dropout); self.gelu = nn.GELU()
        def forward(self, x): 
            return self.gelu(self.bn2(self.fc2(self.dropout(self.gelu(self.bn1(self.fc1(x)))))) + x)

    class FeatureAttention(nn.Module):
        def __init__(self, dim, num_heads=8):
            super(FeatureAttention, self).__init__()
            self.attention = nn.MultiheadAttention(embed_dim=dim, num_heads=num_heads, batch_first=True, dropout=0.3)
        def forward(self, x): 
            return self.attention(x.unsqueeze(1), x.unsqueeze(1), x.unsqueeze(1))[0].squeeze(1)

    class KioskAdapterModel(nn.Module):
        def __init__(self):
            super(KioskAdapterModel, self).__init__()
            self.attention_layer = FeatureAttention(dim=512, num_heads=8)
            self.age_network = nn.Sequential(
                nn.Linear(512, 512), nn.BatchNorm1d(512), nn.GELU(), nn.Dropout(0.5),
                ResidualBlock(512, dropout=0.5), ResidualBlock(512, dropout=0.5),
                nn.Linear(512, 256), nn.BatchNorm1d(256), nn.GELU(), nn.Dropout(0.5), nn.Linear(256, 101)
            )
            self.register_buffer('age_bins', torch.arange(0, 101, dtype=torch.float32))
            self.gender_network = nn.Sequential(
                nn.Linear(512, 256), nn.BatchNorm1d(256), nn.GELU(), nn.Dropout(0.5), ResidualBlock(256, dropout=0.5), nn.Linear(256, 1)
            )
            self.mask_network = nn.Sequential(
                nn.Linear(512, 256), nn.BatchNorm1d(256), nn.GELU(), nn.Dropout(0.4), nn.Linear(256, 1)
            )
            self.masked_age_adapter = nn.Sequential(
                nn.Linear(512, 128), nn.BatchNorm1d(128), nn.GELU(), nn.Dropout(0.3), nn.Linear(128, 1)
            )

        def forward(self, features):
            x = F.normalize(features, p=2, dim=1)
            fused = x + self.attention_layer(x)
            
            age_logits = self.age_network(fused)
            base_expected_age = torch.sum(F.softmax(age_logits, dim=1) * self.age_bins, dim=1, keepdim=True)
            gender_logits = self.gender_network(fused)
            mask_logits = self.mask_network(fused)
            
            age_delta = self.masked_age_adapter(fused)
            mask_probs = torch.sigmoid(mask_logits)
            final_expected_age = base_expected_age + (age_delta * mask_probs)
            
            return final_expected_age, gender_logits, mask_logits


# ==========================================
# 2. Response Dataclass (기존 배리어프리 앱 규격)
# ==========================================
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


# ==========================================
# 3. Service Core Logic
# ==========================================
class FaceService:
    """InsightFace 임베딩 + 듀얼 스마트 라우팅 가중치 기반 분석 싱글턴."""

    def __init__(self):
        self._app = None
        self._base_model = None
        self._mask_model = None
        self._device = None
        self._mask_threshold = 0.80
        self._loaded = False
        self._mock_mode = not AI_DEPS_AVAILABLE

    async def load_models(self):
        """듀얼 인공지능 모델 가중치 정식 로드"""
        if self._loaded:
            return

        if self._mock_mode:
            logger.info("FaceService: running in MOCK mode (missing dependencies)")
            self._loaded = True
            return

        try:
            logger.info("Loading AI Models (InsightFace buffalo_l & Smart Routing Dual Heads)...")
            self._device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            
            # 1. InsightFace 눈(Vision) 장착
            self._app = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
            self._app.prepare(ctx_id=0 if torch.cuda.is_available() else -1, det_size=(320, 320))
            
            # 2. 아키텍처 모델 2개 선언
            self._base_model = KioskMultiTaskHead().to(self._device)
            self._mask_model = KioskAdapterModel().to(self._device)
            
            # 3. 경로 탐색 후 가중치 파일 로드
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            base_model_path = os.path.join(BASE_DIR, "data", "best_kiosk_head_final.pth")
            mask_model_path = os.path.join(BASE_DIR, "data", "best_mask_head_model.pth")
            
            logger.info(f"Loading base model weights from: {base_model_path}")
            self._base_model.load_state_dict(torch.load(base_model_path, map_location=self._device, weights_only=False))
            self._base_model.eval()
            
            logger.info(f"Loading mask model weights from: {mask_model_path}")
            mask_ckpt = torch.load(mask_model_path, map_location=self._device, weights_only=False)
            self._mask_model.load_state_dict(mask_ckpt.get("model_state_dict", mask_ckpt))
            self._mask_model.eval()
            
            self._mask_threshold = mask_ckpt.get("threshold", 0.80) if isinstance(mask_ckpt, dict) else 0.80
            
            logger.info(f"AI Models loaded successfully on {self._device}. (Mask Threshold: {self._mask_threshold:.2f})")
            self._loaded = True
            
        except Exception as e:
            logger.error(f"Model load failed: {e}. Falling back to MOCK mode.")
            self._mock_mode = True
            self._loaded = True

    def _decode_frame(self, b64_str: str):
        """Base64 → OpenCV 이미지 변환"""
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
        """단일 프레임 정밀 라우팅 연산"""
        if img is None or self._app is None or self._base_model is None or self._mask_model is None:
            return None
            
        faces = self._app.get(img)
        if not faces:
            return None
            
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        
        w, h = face.bbox[2] - face.bbox[0], face.bbox[3] - face.bbox[1]
        if w < 120 or h < 120 or face.det_score < 0.5:
            return None

        embedding = torch.from_numpy(face.embedding).float().unsqueeze(0).to(self._device)
        
        with torch.no_grad():
            # 💡 [라우팅 1단계] 마스크 유무 우선 판별
            _, _, mask_logits = self._mask_model(embedding)
            mask_prob = torch.sigmoid(mask_logits).item()
            is_masked = mask_prob >= self._mask_threshold

            # 💡 [라우팅 2단계] 마스크 여부에 따른 정밀 분기 처리
            if is_masked:
                expected_age, gender_logits, _ = self._mask_model(embedding)
            else:
                _, expected_age, gender_logits = self._base_model(embedding)
            
        gender_prob = torch.sigmoid(gender_logits).item()
        predicted_age = float(torch.round(expected_age).item())
        
        # 기계학습 원본 라벨 기준 반영 (1.0 >= female, 0.0 => male)
        predicted_gender = "female" if gender_prob >= 0.5 else "male"

        return {
            "age": predicted_age,
            "gender": predicted_gender,
            "is_masked": is_masked
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
        """프레임 집계 후 정식 Dataclass 형태로 결과 패킹"""
        if not self._loaded:
            await self.load_models()

        if self._mock_mode:
            return self._mock_result()

        ages, genders, masks, frames = [], [], [], []
        try:
            for b64 in frames_b64:
                img = self._decode_frame(b64)
                if img is not None:
                    frames.append(img)

            if not frames:
                logger.warning("No valid frames — returning default")
                return FaceAnalysisResult("청년", "unknown", 25, 0.0)

            # 최대 5프레임까지만 정밀 검사 진행
            for img in frames[:5]:
                result = self._analyze_single_frame(img)
                if result:
                    ages.append(result["age"])
                    genders.append(result["gender"])
                    masks.append(1 if result["is_masked"] else 0)

            if not ages:
                logger.warning("No faces detected/valid — returning default")
                return FaceAnalysisResult("청년", "unknown", 25, 0.0)

            # 결과 집계 (나이: 중간값 / 성별: 다수결)
            final_age = int(np.median(ages))
            gender = "female" if genders.count("female") > (len(genders) / 2) else "male"
            is_mask_worn = sum(masks) > (len(masks) / 2)
            
            logger.info(f"📊 [스마트 라우팅 최종 판단] {final_age}세 ({_age_to_group(final_age)}) | {gender} | 마스크 유무: {is_mask_worn}")
            
            # 🌟 [규격 통합 완성] 기존 앱이 기다리던 Dataclass 통신 문서 양식 그대로 리턴!
            return FaceAnalysisResult(
                age_group=_age_to_group(final_age),
                gender=gender,
                age_est=final_age,
                confidence=min(1.0, len(ages) / len(frames_b64)),
            )
        finally:
            for img in frames:
                del img
            frames.clear()
            gc.collect()


# 전역 싱글턴
face_service = FaceService()