"""TTS 디스크 캐시(data/tts_cache) 관리 도구.

기능:
- 캐시 WAV 파일명을 사람이 읽을 수 있게 리네임 (레거시 sha256.wav → {힌트}__sha256.wav)
- 미사용(매뉴얼에 없는) WAV 삭제

주의:
- "사용" 판정은 backend/data/canned_responses.json 기반(시나리오 response_text,
  templates.parts의 정적 조각, fragments.static)으로만 한다.
- DB(메뉴/옵션 조각)까지 포함해서 엄격히 관리하려면, 별도 확장 옵션을 추가해서
  메뉴/옵션 이름 목록을 같이 넣어야 한다.

사용법:
  python -m scripts.manage_tts_cache                 # 드라이런(변경 없음)
  python -m scripts.manage_tts_cache --apply         # 리네임 적용
  python -m scripts.manage_tts_cache --apply --prune # 리네임 + 미사용 삭제
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# 프로젝트 루트를 sys.path에 추가 (repo root에서 실행 가능하도록)
_ROOT = _project_root()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _data_paths(root: Path) -> tuple[Path, Path, Path]:
    data_dir = root / "data"
    scenarios_path = data_dir / "canned_responses.json"
    cache_dir = data_dir / "tts_cache"
    return data_dir, scenarios_path, cache_dir


_SLOT_RE = re.compile(r"^\{[a-zA-Z_]+\}$")
_DIGEST_RE = re.compile(r"([0-9a-f]{64})", re.IGNORECASE)


def _is_slot(part: str) -> bool:
    return bool(_SLOT_RE.match(part or ""))


def _collect_used_texts(scenarios_path: Path) -> list[str]:
    raw = json.loads(scenarios_path.read_text(encoding="utf-8"))

    used: list[str] = []

    # scenarios.response.response_text
    for sc in raw.get("scenarios", []):
        resp = sc.get("response") or {}
        txt = (resp.get("response_text") or "").strip()
        if txt:
            used.append(txt)

    # templates.parts 의 정적 조각 (슬롯 제외)
    for tpl in raw.get("templates", []):
        parts = tpl.get("parts") or []
        for p in parts:
            if isinstance(p, str) and p.strip() and (not _is_slot(p.strip())):
                used.append(p)

    # fragments.static
    fr = raw.get("fragments") or {}
    for s in fr.get("static", []) or []:
        if isinstance(s, str) and s.strip():
            used.append(s)

    # 중복 제거(순서 보존)
    seen: set[str] = set()
    out: list[str] = []
    for t in used:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _extract_digest_from_name(name: str) -> str | None:
    m = _DIGEST_RE.search(name)
    return m.group(1).lower() if m else None


def main() -> int:
    p = argparse.ArgumentParser(description="TTS 캐시 WAV 파일명 정리/정리")
    p.add_argument("--apply", action="store_true", help="실제로 파일을 수정")
    p.add_argument("--prune", action="store_true", help="미사용 WAV 파일 삭제")
    args = p.parse_args()

    root = _project_root()
    _, scenarios_path, cache_dir = _data_paths(root)

    if not scenarios_path.exists():
        raise SystemExit(f"canned_responses.json not found: {scenarios_path}")

    cache_dir.mkdir(parents=True, exist_ok=True)

    # canned_responses.py의 해시/힌트 로직을 그대로 재사용
    from services import canned_responses as cr

    used_texts = _collect_used_texts(scenarios_path)
    used_digests: dict[str, str] = {}  # digest -> text
    for t in used_texts:
        digest = cr.hashlib.sha256(f"{cr._CACHE_KEY_VERSION}:{t}".encode("utf-8")).hexdigest()  # type: ignore[attr-defined]
        used_digests[digest] = t

    # 1) 레거시 sha.wav → hint__sha.wav 리네임
    rename_ops: list[tuple[Path, Path]] = []

    for digest, text in used_digests.items():
        legacy = cache_dir / f"{digest}.wav"
        target = cache_dir / f"{cr._filename_hint(text)}__{digest}.wav"  # type: ignore[attr-defined]

        if target.exists():
            # 이미 새 형식이 존재하면 레거시는 그대로 둔다(중복 정리/삭제는 prune에서 처리)
            continue

        # 새 형식이 없고 레거시만 있으면 리네임
        if legacy.exists():
            rename_ops.append((legacy, target))

        # 새 형식이 다른 힌트로 존재하는지(예: 이전 힌트 길이/정책 변경) 확인
        matches = list(cache_dir.glob(f"*__{digest}.wav"))
        if matches and not target.exists():
            current = matches[0]
            if current.name != target.name:
                rename_ops.append((current, target))

    # 2) prune: 사용되지 않는 digest를 가진 wav 삭제
    delete_ops: list[Path] = []
    if args.prune:
        for f in cache_dir.glob("*.wav"):
            digest = _extract_digest_from_name(f.name)
            if digest is None:
                continue
            if digest not in used_digests:
                delete_ops.append(f)

    # 출력
    print(f"[manage_tts_cache] cache_dir={cache_dir}")
    print(f"[manage_tts_cache] used_texts={len(used_texts)}, used_digests={len(used_digests)}")
    print(f"[manage_tts_cache] rename_ops={len(rename_ops)}, delete_ops={len(delete_ops)}")

    for src, dst in rename_ops:
        print(f"  RENAME {src.name} -> {dst.name}")
    for f in delete_ops:
        print(f"  DELETE {f.name}")

    if not args.apply:
        print("[manage_tts_cache] dry-run: no changes applied")
        return 0

    # 실제 적용
    for src, dst in rename_ops:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and src.resolve() != dst.resolve():
            # 충돌 방지: dst가 이미 있으면 src만 삭제하지 않고 skip
            continue
        src.rename(dst)

    for f in delete_ops:
        try:
            f.unlink()
        except OSError:
            pass

    print("[manage_tts_cache] applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
