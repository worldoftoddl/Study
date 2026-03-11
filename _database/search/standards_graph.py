"""K-IFRS 기준서 간 참조 그래프 (NetworkX DiGraph).

output/chunks/*.json의 referenced_standards 필드에서 가중치 방향 그래프를 구축한다.
싱글턴 패턴으로 한 번만 구축하고 모듈 수준에서 캐시한다.

그래프 구조:
- 노드: 기준서 번호 문자열 ("1109", "1016")
- 엣지: source→target, weight = 참조 청크 수
- 노드 속성: display_id ("K-IFRS 1109")
"""

import json
import glob
import os
import re

import networkx as nx

from search.config import CHUNKS_DIR

# ── 모듈 수준 싱글턴 ─────────────────────────────────
_graph: nx.DiGraph | None = None
_NUM_TO_DISPLAY: dict[str, str] = {}

# 기준서 번호 추출 패턴
_STD_NUM_RE = re.compile(r"K-IFRS\s+(\d{3,4})")


def _extract_std_number(standard_id: str) -> str | None:
    """'K-IFRS 1016' → '1016'. 매칭 실패 시 None."""
    m = _STD_NUM_RE.search(standard_id)
    return m.group(1) if m else None


def _build_graph(chunks_dir: str | None = None) -> nx.DiGraph:
    """output/chunks/*.json에서 referenced_standards를 읽어 DiGraph를 구축한다."""
    global _NUM_TO_DISPLAY

    chunks_dir = chunks_dir or CHUNKS_DIR
    g = nx.DiGraph()
    edge_counts: dict[tuple[str, str], int] = {}

    for fpath in sorted(glob.glob(os.path.join(chunks_dir, "*.json"))):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        standard_id = data.get("standard_id", "")
        source_num = _extract_std_number(standard_id)

        # 제X호 패턴이 아닌 문서 (개념체계 등)는 standard_id 자체를 키로
        if source_num is None:
            # 개념체계 등은 그래프에서 제외 (번호 체계가 없으므로)
            continue

        # 노드 등록 + display_id 매핑
        if source_num not in _NUM_TO_DISPLAY:
            _NUM_TO_DISPLAY[source_num] = standard_id
        if not g.has_node(source_num):
            g.add_node(source_num, display_id=standard_id)

        for child in data.get("children", []):
            meta = child.get("metadata", {})
            ref_stds = meta.get("referenced_standards", [])
            for target_num in ref_stds:
                if target_num == source_num:
                    continue  # 자기참조 제거
                key = (source_num, target_num)
                edge_counts[key] = edge_counts.get(key, 0) + 1

    # 엣지 추가
    for (src, tgt), count in edge_counts.items():
        # 타겟 노드가 없으면 추가 (다른 기준서에서만 참조되는 경우)
        if not g.has_node(tgt):
            display = _NUM_TO_DISPLAY.get(tgt, f"K-IFRS {tgt}")
            g.add_node(tgt, display_id=display)
            if tgt not in _NUM_TO_DISPLAY:
                _NUM_TO_DISPLAY[tgt] = display
        g.add_edge(src, tgt, weight=count)

    return g


def get_graph(chunks_dir: str | None = None) -> nx.DiGraph:
    """싱글턴 그래프를 반환한다. 최초 호출 시 구축."""
    global _graph
    if _graph is None:
        _graph = _build_graph(chunks_dir)
    return _graph


def get_display_id(std_number: str) -> str:
    """'1016' → 'K-IFRS 1016'. 매핑 없으면 'K-IFRS {number}' 반환."""
    get_graph()  # _NUM_TO_DISPLAY 확보
    return _NUM_TO_DISPLAY.get(std_number, f"K-IFRS {std_number}")


def get_neighbors(std_number: str, hops: int = 1) -> dict[str, float]:
    """std_number에서 hops만큼의 이웃 기준서를 반환한다.

    Args:
        std_number: 기준서 번호 ("1016").
        hops: 1이면 직접 참조, 2이면 간접 참조까지.

    Returns:
        {neighbor_number: aggregated_weight} dict. 자기 자신은 제외.
        2-hop 가중치는 1-hop 가중치의 0.3배로 감쇠.
    """
    g = get_graph()
    if std_number not in g:
        return {}

    result: dict[str, float] = {}
    HOP2_DECAY = 0.3

    # 1-hop: 직접 참조 (outgoing)
    for _, target, data in g.out_edges(std_number, data=True):
        w = data.get("weight", 1)
        result[target] = result.get(target, 0) + w

    if hops >= 2:
        # 2-hop: 1-hop 이웃의 outgoing
        hop1_targets = list(result.keys())
        for mid in hop1_targets:
            mid_weight = result[mid]
            for _, target, data in g.out_edges(mid, data=True):
                if target == std_number:
                    continue
                w = data.get("weight", 1) * HOP2_DECAY
                decayed = w * (mid_weight / max(result.values()))  # 상대 가중치
                result[target] = result.get(target, 0) + decayed

    # 자기 자신 제거
    result.pop(std_number, None)
    return result


def get_reverse_refs(std_number: str) -> dict[str, int]:
    """std_number를 참조하는 기준서 목록을 반환한다 (역방향).

    Returns:
        {source_number: weight} dict.
    """
    g = get_graph()
    if std_number not in g:
        return {}

    result: dict[str, int] = {}
    for source, _, data in g.in_edges(std_number, data=True):
        result[source] = data.get("weight", 1)
    return result
