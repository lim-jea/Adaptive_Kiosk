"""
시나리오 매뉴얼 기반 즉시 응답.

backend/data/canned_responses.json 의 시나리오를 stage + 정규식으로 매칭해서
Gemini 호출 없이 미리 정의된 AIChatResponse를 반환한다.
같이 backend/data/tts_cache/{sha256}.wav 디렉터리에 합성된 음성을 영구 저장해서
서버 재시작 후에도 캐시가 유지되도록 한다.
"""
import hashlib
import io
import json
import logging
import re
import wave
from pathlib import Path
from typing import Optional

from schemas.chat import AIChatResponse

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_SCENARIOS_PATH = _DATA_DIR / "canned_responses.json"
_TTS_CACHE_DIR = _DATA_DIR / "tts_cache"


# ─── 시나리오 로드 ───────────────────────────────────────────────────────────

class _Scenario:
    __slots__ = ("id", "stages", "patterns", "response")

    def __init__(self, id: str, stages: set[str], patterns: list[re.Pattern], response: AIChatResponse):
        self.id = id
        self.stages = stages
        self.patterns = patterns
        self.response = response


_scenarios: list[_Scenario] = []
_templates: list[dict] = []   # [{id, expand, text}]
_fragments_cfg: dict = {}     # {static: [...], include_menus: bool, include_options: bool}


def load_scenarios() -> int:
    """JSON에서 시나리오 + 템플릿을 읽어 메모리에 적재. 시작 시 + 핫 리로드용."""
    global _scenarios, _templates
    if not _SCENARIOS_PATH.exists():
        logger.warning("[canned] %s 없음 — 빈 시나리오 목록 사용", _SCENARIOS_PATH)
        _scenarios = []
        _templates = []
        return 0

    try:
        with _SCENARIOS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("[canned] 시나리오 JSON 파싱 실패: %s", e)
        _scenarios = []
        _templates = []
        return 0

    new_list: list[_Scenario] = []
    for item in data.get("scenarios", []):
        try:
            match = item.get("match", {})
            stages = set(match.get("stages", []))
            patterns = [re.compile(p) for p in match.get("patterns", [])]
            response = AIChatResponse.model_validate(item["response"])
            new_list.append(_Scenario(
                id=item["id"],
                stages=stages,
                patterns=patterns,
                response=response,
            ))
        except Exception as e:
            logger.warning("[canned] 시나리오 '%s' 로드 실패: %s", item.get("id"), e)

    _scenarios = new_list
    _templates = list(data.get("templates", []))
    global _fragments_cfg
    _fragments_cfg = dict(data.get("fragments", {}))
    logger.info(
        "[canned] 시나리오 %d개, 템플릿 %d개, fragment 정적 %d개 로드",
        len(_scenarios), len(_templates), len(_fragments_cfg.get("static", [])),
    )
    return len(_scenarios)


def match_canned(text: str, stage: str) -> Optional[AIChatResponse]:
    """현재 stage에서 매칭되는 첫 시나리오의 응답을 반환. 없으면 None."""
    if not text:
        return None
    for sc in _scenarios:
        if sc.stages and stage not in sc.stages:
            continue
        for pat in sc.patterns:
            if pat.search(text):
                return sc.response.model_copy(deep=True)
    return None


def all_canned_texts() -> list[str]:
    """프리워밍용 — 모든 시나리오의 response_text 목록."""
    return [sc.response.response_text for sc in _scenarios if sc.response.response_text]


async def expand_template_texts(db) -> list[str]:
    """
    템플릿이 사용하는 정적 조각만 반환.

    parts가 정의된 템플릿은 슬롯이 아닌 부분만 합성 대상이 된다.
    슬롯({menu}/{option})에 들어갈 메뉴/옵션 자체는 expand_fragment_texts가 처리하므로
    여기서는 중복 합성을 피한다.

    parts가 없는(레거시) 템플릿은 fall-back으로 모든 조합을 풀어 반환한다.
    """
    from sqlalchemy import select
    from crud.menu import get_menus
    from models.menu import OptionItem

    out: list[str] = []
    menu_names: list[str] = []
    option_names: list[str] = []

    for tpl in _templates:
        parts = tpl.get("parts")
        if parts:
            # 슬롯이 아닌 정적 문자열 조각만 합성 대상
            for p in parts:
                if not _is_slot(p):
                    out.append(p)
            continue

        # 레거시: parts 없으면 풀어서 통째 합성
        text = tpl.get("text", "")
        expand = tpl.get("expand")
        if expand == "menus":
            if not menu_names:
                try:
                    rows, _ = await get_menus(db, limit=1000)
                    menu_names = [m["name"] for m in rows]
                except Exception as e:
                    logger.warning("[canned] 메뉴 로드 실패: %s", e)
            for name in menu_names:
                out.append(text.replace("{menu}", name))
        elif expand == "options":
            if not option_names:
                try:
                    items = (await db.execute(select(OptionItem))).scalars().all()
                    option_names = sorted({i.name for i in items if i.name})
                except Exception as e:
                    logger.warning("[canned] 옵션 로드 실패: %s", e)
            for name in option_names:
                out.append(text.replace("{option}", name))
        else:
            out.append(text)
    return out


_SLOT_RE = re.compile(r"^\{[a-zA-Z_]+\}$")


def _is_slot(part: str) -> bool:
    return bool(_SLOT_RE.match(part))


def template_to_segments(template_id: str, **slots) -> Optional[list[str]]:
    """
    템플릿의 parts를 그대로 audio_segments 배열로 변환.
    슬롯은 인자값으로 치환된다.

    예: template_to_segments("menu_selected", menu="아메리카노")
        → ["아메리카노", " 선택하셨어요. 옵션을 골라주세요."]
    """
    for tpl in _templates:
        if tpl.get("id") != template_id:
            continue
        parts = tpl.get("parts")
        if not parts:
            return None
        out: list[str] = []
        for p in parts:
            if _is_slot(p):
                key = p[1:-1]  # {menu} → menu
                val = slots.get(key)
                if val is None:
                    return None
                # 슬롯 값은 단일 문자열 뿐 아니라 여러 조각(list[str])도 허용한다.
                if isinstance(val, (list, tuple)):
                    out.extend(str(x) for x in val)
                else:
                    out.append(str(val))
            else:
                out.append(p)
        return out
    return None


async def expand_fragment_texts(db) -> list[str]:
    """
    런타임 합성 조각으로 쓸 텍스트 목록.
    정적 조각 + DB의 메뉴/옵션 이름을 각각 단독으로 반환.
    프리워밍 시 이 목록을 개별 합성해 디스크에 저장한다.
    """
    from sqlalchemy import select
    from crud.menu import get_menus
    from models.menu import OptionItem

    out: list[str] = list(_fragments_cfg.get("static", []))

    if _fragments_cfg.get("include_menus"):
        try:
            menu_rows, _ = await get_menus(db, limit=1000)
            out.extend(m["name"] for m in menu_rows)
        except Exception as e:
            logger.warning("[canned] fragment 메뉴 로드 실패: %s", e)

    if _fragments_cfg.get("include_options"):
        try:
            items = (await db.execute(select(OptionItem))).scalars().all()
            out.extend(sorted({i.name for i in items if i.name}))
        except Exception as e:
            logger.warning("[canned] fragment 옵션 로드 실패: %s", e)

    return list(dict.fromkeys(out))


_SILENCE_THRESHOLD = 600    # 16-bit PCM (max 32767) — 약 -35dB
_TRIM_HEAD_MS = 20          # 트림 후 최소 남길 head pad
_TRIM_TAIL_MS = 20
_CROSSFADE_MS = 25          # 인접 조각 사이 선형 크로스페이드
_GAP_MS = 0                 # 부드럽게 이어붙이기 위해 0


def _ms_to_samples(ms: int, rate: int) -> int:
    return int(rate * ms / 1000)


def _trim_silence(pcm: bytes, rate: int, sample_width: int) -> bytes:
    """양 끝 무음(역치 이하)을 잘라내고 짧은 head/tail pad만 남긴다."""
    if sample_width != 2 or len(pcm) < 4:
        return pcm
    import array
    samples = array.array("h")
    samples.frombytes(pcm)

    n = len(samples)
    start = 0
    while start < n and abs(samples[start]) < _SILENCE_THRESHOLD:
        start += 1
    end = n - 1
    while end > start and abs(samples[end]) < _SILENCE_THRESHOLD:
        end -= 1

    if start >= end:
        return pcm

    head_pad = _ms_to_samples(_TRIM_HEAD_MS, rate)
    tail_pad = _ms_to_samples(_TRIM_TAIL_MS, rate)
    new_start = max(0, start - head_pad)
    new_end = min(n, end + tail_pad + 1)
    return samples[new_start:new_end].tobytes()


def _crossfade(a: bytes, b: bytes, rate: int, sample_width: int) -> bytes:
    """a의 마지막과 b의 처음을 _CROSSFADE_MS만큼 선형 크로스페이드해서 결합."""
    if sample_width != 2 or _CROSSFADE_MS <= 0:
        return a + b

    import array
    fade_samples = _ms_to_samples(_CROSSFADE_MS, rate)
    a_arr = array.array("h"); a_arr.frombytes(a)
    b_arr = array.array("h"); b_arr.frombytes(b)
    n = min(fade_samples, len(a_arr), len(b_arr))
    if n <= 0:
        return a + b

    head = a_arr[:-n]
    tail = b_arr[n:]
    mixed = array.array("h", [0] * n)
    for i in range(n):
        w = (i + 1) / (n + 1)  # 0..1
        v = int(a_arr[len(a_arr) - n + i] * (1 - w) + b_arr[i] * w)
        # clip
        if v > 32767: v = 32767
        elif v < -32768: v = -32768
        mixed[i] = v
    return head.tobytes() + mixed.tobytes() + tail.tobytes()


def _read_wav_pcm(wav_bytes: bytes) -> Optional[tuple[bytes, int, int, int]]:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            return (
                wf.readframes(wf.getnframes()),
                wf.getframerate(),
                wf.getsampwidth(),
                wf.getnchannels(),
            )
    except Exception as e:
        logger.warning("[canned] WAV 디코드 실패: %s", e)
        return None


def compose_audio_from_segments(segments: list[str]) -> Optional[bytes]:
    """
    각 조각의 디스크 WAV를 PCM으로 디코드 → 양 끝 무음 트림 → 인접 조각 크로스페이드 →
    단일 WAV로 묶어 반환. 조각 중 하나라도 디스크에 없으면 None.

    모든 조각이 동일 음성/샘플레이트로 합성되었다는 가정하에 동작.
    """
    if not segments:
        return None

    pcm_list: list[bytes] = []
    rate = 24000
    sample_width = 2
    channels = 1

    for seg in segments:
        wav_bytes = get_cached_wav(seg)
        if wav_bytes is None:
            return None
        decoded = _read_wav_pcm(wav_bytes)
        if decoded is None:
            return None
        pcm, rate, sample_width, channels = decoded
        pcm = _trim_silence(pcm, rate, sample_width)
        if pcm:
            pcm_list.append(pcm)

    if not pcm_list:
        return None

    # 인접 조각을 크로스페이드로 결합
    merged = pcm_list[0]
    for chunk in pcm_list[1:]:
        merged = _crossfade(merged, chunk, rate, sample_width)

    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(merged)
    return out.getvalue()


# ─── 가격 → 한국어 숫자 조각 시퀀스 ─────────────────────────────────────────

_DIGIT_KO = ["", " 일 ", " 이 ", " 삼 ", " 사 ", " 오 ", " 육 ", " 칠 ", " 팔 ", " 구 "]
_UNIT_TEN = " 십 "
_UNIT_HUN = " 백 "
_UNIT_THO = " 천 "
_UNIT_MAN = " 만 "


def price_to_segments(price: int) -> list[str]:
    """
    정수 가격을 한국어 숫자 조각 시퀀스로 변환.
    예: 4500 → ["사", "천", "오", "백"]
        25000 → ["이", "만", "오", "천"]
        130000 → ["십삼", "만"]  → 실제로는 ["십","삼","만"]
    각 조각이 fragments static 목록에 들어 있어야 디스크 캐시 hit 가능.
    """
    if price <= 0:
        return ["영"]

    out: list[str] = []
    n = int(price)

    # 만 단위 처리
    man = n // 10000
    rest = n % 10000

    if man > 0:
        if man != 1:
            out.extend(_chunk_under_10000(man))
        out.append(_UNIT_MAN)
    if rest > 0:
        out.extend(_chunk_under_10000(rest))

    return out


def _chunk_under_10000(n: int) -> list[str]:
    """0 < n < 10000 을 한국어 숫자 조각 리스트로."""
    out: list[str] = []
    digits = [(n // 1000) % 10, (n // 100) % 10, (n // 10) % 10, n % 10]
    units = [_UNIT_THO, _UNIT_HUN, _UNIT_TEN, ""]
    for d, u in zip(digits, units):
        if d == 0:
            continue
        if d == 1 and u in (_UNIT_THO, _UNIT_HUN, _UNIT_TEN):
            out.append(u)
        else:
            out.append(_DIGIT_KO[d])
            if u:
                out.append(u)
    return out


def price_segments_with_suffix(price: int) -> list[str]:
    """가격 + ' 원입니다.' 까지 합쳐 audio_segments에 바로 넣을 수 있는 형태."""
    return [" 총 "] + price_to_segments(price) + [" 원입니다."]


def compose_template(template_id: str, **slots) -> Optional[str]:
    """
    런타임에서 템플릿을 슬롯으로 채워 텍스트 반환.
    예: compose_template("menu_selected", menu="아메리카노")
        → "아메리카노 선택하셨어요. 옵션을 골라주세요."
    """
    for tpl in _templates:
        if tpl.get("id") == template_id:
            text = tpl.get("text", "")
            for k, v in slots.items():
                text = text.replace("{" + k + "}", str(v))
            return text
    return None


def get_template_phrases_for_prompt() -> str:
    """시스템 프롬프트에 끼울 템플릿 매뉴얼.
    parts가 있는 템플릿은 audio_segments 배열을 그대로 보여줘서 AI가 즉시 따라할 수 있게 한다."""
    if not _templates:
        return ""
    lines = [
        "[템플릿 응답 — 슬롯만 채워 그대로 사용하세요]",
        "아래 형식 그대로 사용하면 미리 합성된 음성 조각이 즉시 이어붙어 재생됩니다.",
        "{menu}, {option}은 실제 메뉴/옵션 이름으로 정확히 치환하세요.",
        "",
    ]
    for tpl in _templates:
        lines.append(f"- ({tpl['id']}) {tpl['text']}")
        parts = tpl.get("parts")
        if parts:
            seg_repr = ", ".join(f'"{p}"' for p in parts)
            lines.append(f"   audio_segments: [{seg_repr}]")
    return "\n".join(lines)


def get_fragments_for_prompt() -> str:
    """
    시스템 프롬프트에 끼울 조각 합성 매뉴얼.
    AI가 audio_segments 필드에 조각 텍스트 배열을 채우면, 백엔드가 미리 캐시된
    조각 WAV를 이어붙여 즉시 재생한다 (Gemini TTS 호출 0회).
    """
    static = _fragments_cfg.get("static", [])
    if not static and not _fragments_cfg.get("include_menus") and not _fragments_cfg.get("include_options"):
        return ""

    lines = [
        "[음성 조각 합성 — 주문 요약 등 조합형 응답에 사용]",
        "긴 조합형 응답(예: 주문 요약)은 response_text와 함께 audio_segments 필드에",
        "아래 조각들의 배열을 넣으세요. 백엔드가 조각 음성을 이어붙여 즉시 재생합니다.",
        "",
        "사용 가능한 조각:",
    ]
    if _fragments_cfg.get("include_menus"):
        lines.append("- 모든 메뉴 이름 (예: \"아메리카노\", \"카페라떼\")")
    if _fragments_cfg.get("include_options"):
        lines.append("- 모든 옵션 이름 (예: \"톨\", \"아이스\", \"샷 추가\")")
    if static:
        lines.append("- 정적 연결구: " + ", ".join(f'"{s}"' for s in static))
    lines += [
        "",
        "원칙:",
        "- 조합형 응답(주문 요약, 가격 안내 등)에서만 audio_segments를 채운다.",
        "  단순한 인사/취소/긍정 같은 짧은 응답은 그냥 response_text만 채우면 된다.",
        "- 조각 텍스트는 위 목록의 정적 연결구·메뉴 이름·옵션 이름·숫자 단위를",
        "  정확히 같은 문자열로 사용해야 한다 (공백·순서 포함).",
        "- response_text와 audio_segments의 의미는 일치해야 한다.",
        "  segments를 이어 붙인 결과가 response_text를 그대로 반영하지 않으면",
        "  백엔드가 segments를 무시하고 라이브 합성으로 폴백한다.",
        "",
        "한국어 숫자 표기 원칙 (가격을 segments로 분해할 때):",
        "- 자릿수 단위는 '십/백/천/만' 을 그대로 쓴다.",
        "- 1로 시작하는 십/백/천/만 앞의 '일'은 생략한다 (한국어 자연 발화 규칙).",
        "- 0인 자리는 건너뛴다.",
        "",
        "audio_segments 구성 형식:",
        '  ["{변하는 부분: 메뉴/옵션/숫자}", "{고정 연결구}", ...]',
    ]
    return "\n".join(lines)


def get_canned_phrases_for_prompt(stage: Optional[str] = None) -> str:
    """
    시스템 프롬프트에 끼울 '권장 응답 매뉴얼'.
    현재 stage에 해당하는 시나리오만 (의도 → 권장 문구) 형태로 최소한만 노출한다.
    """
    relevant = [
        sc for sc in _scenarios
        if (not sc.stages) or (stage is None) or (stage in sc.stages)
    ]
    if not relevant:
        return ""
    lines = [
        "[권장 응답 매뉴얼]",
        "사용자 의도가 아래 항목과 일치하면 response_text를 글자 그대로 복사한다.",
        "그래야 미리 합성된 음성이 즉시 재생되어 응답 지연이 없다.",
        "",
    ]
    for sc in relevant:
        intent = sc.response.intent
        text = sc.response.response_text
        lines.append(f"- {intent}: {text}")
    return "\n".join(lines)


async def collect_prewarm_segments(
    db=None,
    *,
    include_menus: Optional[bool] = None,
    include_options: Optional[bool] = None,
) -> list[str]:
    """조각 합성(audio_segments)용으로 '개별 WAV로 미리 합성해 둘 텍스트' 목록을 수집.

    구성:
    - fragments.static (정적 연결구/숫자 단위 등)
    - 템플릿(parts)의 슬롯이 아닌 정적 문자열 조각
    - (선택) 메뉴/옵션 이름(각각 단독 조각) — DB가 필요

    include_menus/include_options를 None으로 두면 canned_responses.json의 설정을 따른다.
    """
    out: list[str] = []

    # 1) fragments.static
    out.extend(_fragments_cfg.get("static", []) or [])

    # 2) templates.parts 의 정적 조각
    for tpl in _templates:
        parts = tpl.get("parts")
        if not parts:
            continue
        for p in parts:
            if not _is_slot(p):
                out.append(p)

    # 3) (선택) 메뉴/옵션 이름
    want_menus = _fragments_cfg.get("include_menus") if include_menus is None else include_menus
    want_options = _fragments_cfg.get("include_options") if include_options is None else include_options

    if (want_menus or want_options) and db is None:
        # DB가 없으면 정적 조각만 반환
        return list(dict.fromkeys(s for s in out if s))

    if want_menus or want_options:
        # 기존 구현 재사용: 정적 조각 + 메뉴/옵션 이름을 단독 조각으로 수집
        try:
            frag_texts = await expand_fragment_texts(db)
            out.extend(frag_texts)
        except Exception as e:
            logger.warning("[canned] prewarm segment 수집 실패(DB): %s", e)

    return list(dict.fromkeys(s for s in out if s))


# ─── TTS 디스크 캐시 ─────────────────────────────────────────────────────────

# 캐시 키에 음성 식별자를 포함시켜 voice를 바꿨을 때 옛 파일이 잘못 재생되지 않게 한다.
# v1 캐시에 WAV가 아닌 오디오(PCM 등)가 저장된 경우가 있어 v2로 올린다.
_CACHE_KEY_VERSION = "kore-v2"


def _looks_like_wav(wav_bytes: bytes) -> bool:
    return (
        isinstance(wav_bytes, (bytes, bytearray))
        and len(wav_bytes) >= 12
        and wav_bytes[0:4] == b"RIFF"
        and wav_bytes[8:12] == b"WAVE"
    )


_ILLEGAL_FILENAME_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1F]")


def _filename_hint(text: str, max_len: int = 40) -> str:
    """텍스트를 파일명 힌트로 변환.

    - Windows/NTFS에서 금지되는 문자를 제거
    - 공백을 '_'로 축약
    - 너무 길면 잘라낸다
    """
    s = (text or "").strip()
    s = _ILLEGAL_FILENAME_CHARS.sub("", s)
    s = re.sub(r"\s+", "_", s)
    s = s.strip("._ ")
    if not s:
        return "tts"
    return s[:max_len]


def _wav_path_for(text: str) -> Path:
    digest = hashlib.sha256(f"{_CACHE_KEY_VERSION}:{text}".encode("utf-8")).hexdigest()
    hint = _filename_hint(text)
    return _TTS_CACHE_DIR / f"{hint}__{digest}.wav"


def _legacy_wav_path_for(text: str) -> Path:
    """이전 버전(파일명이 sha256만 있던 형태) 경로."""
    digest = hashlib.sha256(f"{_CACHE_KEY_VERSION}:{text}".encode("utf-8")).hexdigest()
    return _TTS_CACHE_DIR / f"{digest}.wav"


def get_cached_wav(text: str) -> Optional[bytes]:
    """디스크 캐시에서 WAV 바이트 로드. 없으면 None."""
    # 신규: {hint}__{sha}.wav
    p = _wav_path_for(text)
    if p.exists():
        try:
            b = p.read_bytes()
            if not _looks_like_wav(b):
                return None
            return b
        except Exception as e:
            logger.warning("[canned] WAV 로드 실패 %s: %s", p.name, e)

    # 레거시: {sha}.wav
    legacy = _legacy_wav_path_for(text)
    if legacy.exists():
        try:
            b = legacy.read_bytes()
            if not _looks_like_wav(b):
                return None
            return b
        except Exception as e:
            logger.warning("[canned] WAV 로드 실패 %s: %s", legacy.name, e)
    return None


def save_cached_wav(text: str, wav_bytes: bytes) -> None:
    """디스크 캐시에 WAV 영구 저장."""
    try:
        _TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _wav_path_for(text).write_bytes(wav_bytes)
    except Exception as e:
        logger.warning("[canned] WAV 저장 실패: %s", e)


# 모듈 import 시점에 시나리오 자동 로드
load_scenarios()
