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
_TERM_INTRO_RE = re.compile(
    r"이\s*기준서에서\s*사용하는\s*용어의\s*(뜻|정의)"
)


def build_terms_index(
    chunks_dir: str = "output/chunks",
    output_path: str = "output/terms_index.json",
    verbose: bool = False,
) -> dict:
    """전 기준서에서 용어정의 청크를 찾아 기준서별 매핑을 생성한다.

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

    file_count = 0
    for fpath in sorted(glob.glob(os.path.join(chunks_dir, "*.json"))):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        standard_id = data.get("standard_id", "")
        file_count += 1

        for child in data.get("children", []):
            content = child.get("content", "")

            if not _TERM_INTRO_RE.search(content[:100]):
                continue

            chunk_id = child.get("chunk_id", "")
            preview = content[:100].replace("\n", " ")

            standard_to_chunk[standard_id] = {
                "chunk_id": chunk_id,
                "content_preview": preview,
            }
            chunk_id_list.append(chunk_id)

            if verbose:
                print(f"  [{standard_id}] {chunk_id}")
                print(f"    {preview}...")

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
        print(f"용어정의 청크: {len(chunk_id_list)}개 기준서")
        print(f"저장 위치: {output_path}")

    return index


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    build_terms_index(verbose=verbose)
