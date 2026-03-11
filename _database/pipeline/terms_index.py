"""K-IFRS 용어 정의 인덱스 빌더.

output/chunks/*.json에서 용어정의 청크를 식별하고,
기준서별로 용어정의 청크의 chunk_id를 매핑한다.

검색 시 해당 기준서의 용어정의 청크 전체를 컨텍스트에 주입하면,
LLM이 필요한 용어를 직접 참조할 수 있다.

Usage:
    python -m pipeline.terms_index              # output/terms_index.json 생성
    python -m pipeline.terms_index --verbose    # 추출 과정 출력
"""

import json
import glob
import os
import re
import sys

# ── 용어정의 청크 식별 패턴 ──────────────────────────

# Primary: parent_id(heading) 기반 구조적 탐지
_PARENT_TERM_RE = re.compile(r"_h_(?:부록_)?용어의_(?:정의|뜻)")

# Secondary: content 기반 텍스트 탐지 (fallback)
_TERM_INTRO_RE = re.compile(
    r"(기준서|해석서)에서\s*사용(하는|되는)\s*용어의\s*(뜻|정의)"
)

# 자체 정의 없이 다른 기준서 참조만 하는 청크 제외 (예: 1039)
_XREF_ONLY_RE = re.compile(r"에서\s*정(?:의)?하고\s*있")


def _register(
    standard_id: str,
    child: dict,
    standard_to_chunk: dict[str, dict],
    chunk_id_list: list[str],
    verbose: bool,
) -> None:
    """기준서-용어정의 청크 매핑을 등록한다."""
    chunk_id = child.get("chunk_id", "")
    content = child.get("content", "")
    preview = content[:100].replace("\n", " ")

    standard_to_chunk[standard_id] = {
        "chunk_id": chunk_id,
        "content_preview": preview,
    }
    chunk_id_list.append(chunk_id)

    if verbose:
        print(f"  [{standard_id}] {chunk_id}")
        print(f"    {preview}...")


def build_terms_index(
    chunks_dir: str = "output/chunks",
    output_path: str = "output/terms_index.json",
    verbose: bool = False,
) -> dict:
    """전 기준서에서 용어정의 청크를 찾아 기준서별 매핑을 생성한다.

    2-pass 탐지:
      Pass 1 — parent_id 기반 (구조적 신호, primary)
      Pass 2 — content 기반 (텍스트 패턴, fallback)

    출력 구조:
    {
      "standard_to_chunk": {
        "K-IFRS 1016": {
          "chunk_id": "KIFRS1016_main_unk_4",
          "content_preview": "이 기준서에서 사용하는 용어의 뜻은..."
        }
      },
      "chunk_id_list": ["KIFRS1016_main_unk_4", ...]
    }
    """
    standard_to_chunk: dict[str, dict] = {}
    chunk_id_list: list[str] = []

    # 파일별 데이터 캐시 (Pass 2 재사용)
    all_files: list[tuple[str, dict]] = []

    file_count = 0
    for fpath in sorted(glob.glob(os.path.join(chunks_dir, "*.json"))):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        file_count += 1
        all_files.append((fpath, data))

    # ── Pass 1: parent_id 기반 탐지 ──────────────────
    if verbose:
        print("── Pass 1: parent_id 기반 탐지 ──")
    for fpath, data in all_files:
        standard_id = data.get("standard_id", "")

        for child in data.get("children", []):
            parent_id = child.get("parent_id", "")
            if not _PARENT_TERM_RE.search(parent_id):
                continue
            # 결론근거(bc) 섹션 제외
            if "_bc_" in parent_id:
                continue
            # 참조만 하는 청크 제외 (예: 1039)
            content = child.get("content", "")
            if _XREF_ONLY_RE.search(content[:200]):
                if verbose:
                    print(f"  [{standard_id}] SKIP (xref only): {child.get('chunk_id','')}")
                continue
            # 기준서당 첫 번째 child만 채택
            if standard_id not in standard_to_chunk:
                _register(standard_id, child, standard_to_chunk, chunk_id_list, verbose)

    # ── Pass 2: content 기반 fallback ─────────────────
    if verbose:
        print("\n── Pass 2: content 기반 fallback ──")
    for fpath, data in all_files:
        standard_id = data.get("standard_id", "")
        if standard_id in standard_to_chunk:
            continue

        for child in data.get("children", []):
            content = child.get("content", "")
            if _TERM_INTRO_RE.search(content[:200]):
                _register(standard_id, child, standard_to_chunk, chunk_id_list, verbose)
                break

    index = {
        "standard_to_chunk": standard_to_chunk,
        "chunk_id_list": chunk_id_list,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"\n=== 용어 인덱스 빌드 완료 ===")
        print(f"파일 수: {file_count}")
        print(f"용어정의 청크: {len(standard_to_chunk)}개 기준서")
        print(f"저장 위치: {output_path}")

    return index


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    build_terms_index(verbose=verbose)
