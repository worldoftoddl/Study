import os
import sys
import glob
from typing import Literal
from langchain_core.tools import tool
from tavily import TavilyClient


tavily_client = TavilyClient()

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

# _database/search 모듈 임포트를 위한 경로 추가
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "_database")
sys.path.insert(0, os.path.abspath(DATABASE_DIR))


@tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> str:
    """인터넷에서 최신 정보를 검색합니다. 날씨, 뉴스, 실시간 정보 등을 찾을 때 사용하세요."""
    results = tavily_client.search(
        query, max_results=max_results, topic=topic
    )
    # 검색 결과를 읽기 좋게 포맷팅
    output = []
    for r in results.get("results", []):
        output.append(f"**{r['title']}**\n{r['content']}\n출처: {r['url']}\n")
    return "\n---\n".join(output) if output else "검색 결과가 없습니다."


@tool
def calculator(expression: str) -> str:
    """수학 계산을 수행합니다. 사칙연산, 거듭제곱(**), 나머지(%) 등을 지원합니다.
    예: '123 * 456 + 789', '2 ** 10', '100 / 3'"""
    # 안전한 문자만 허용
    allowed = set("0123456789+-*/.() %")
    if not all(c in allowed for c in expression.replace(" ", "")):
        return "오류: 허용되지 않는 문자가 포함되어 있습니다. 숫자와 연산자만 사용하세요."
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"계산 오류: {e}"


def load_skills() -> list[dict]:
    """skills/ 디렉토리에서 모든 SKILL.md 파일을 읽어 반환합니다."""
    skills = []
    pattern = os.path.join(SKILLS_DIR, "**", "SKILL.md")
    for path in glob.glob(pattern, recursive=True):
        skill_name = os.path.basename(os.path.dirname(path))
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        skills.append({"name": skill_name, "content": content, "path": path})
    return skills


@tool
def list_skills() -> str:
    """사용 가능한 스킬 목록을 보여줍니다."""
    skills = load_skills()
    if not skills:
        return "등록된 스킬이 없습니다."
    output = "사용 가능한 스킬:\n"
    for s in skills:
        # SKILL.md에서 description 라인 추출
        lines = s["content"].split("\n")
        desc = ""
        for line in lines:
            if line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
                break
        output += f"- **{s['name']}**: {desc}\n"
    return output


@tool
def get_skill(skill_name: str) -> str:
    """특정 스킬의 상세 내용을 가져옵니다. 스킬의 지침에 따라 작업을 수행할 때 사용하세요."""
    skills = load_skills()
    for s in skills:
        if s["name"] == skill_name:
            return s["content"]
    available = [s["name"] for s in skills]
    return f"'{skill_name}' 스킬을 찾을 수 없습니다. 사용 가능: {available}"


# ── K-IFRS Qdrant 검색 도구 ──

_qdrant_client = None
_qdrant_embeddings = None


def _get_qdrant_resources():
    """Qdrant 클라이언트와 임베딩 모델을 lazy 초기화합니다."""
    global _qdrant_client, _qdrant_embeddings
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        from langchain_upstage import UpstageEmbeddings
        from search.config import MODEL_NAME

        qdrant_path = os.path.join(os.path.abspath(DATABASE_DIR), "qdrant_storage")
        _qdrant_client = QdrantClient(path=qdrant_path)
        _qdrant_embeddings = UpstageEmbeddings(
            model=MODEL_NAME,
            upstage_api_key=os.getenv("UPSTAGE_API_KEY"),
        )
    return _qdrant_client, _qdrant_embeddings


@tool
def kifrs_search(query: str, top_k: int = 5) -> str:
    """K-IFRS(한국채택국제회계기준) 기준서를 검색합니다.
    회계 기준, 재무제표, 자산/부채/수익/비용 관련 질문에 사용하세요.
    Parent-Child 계층 검색으로 관련 문단과 형제 문단을 함께 반환합니다."""
    from search.retriever import search_with_parent

    client, embeddings = _get_qdrant_resources()
    groups = search_with_parent(client, embeddings, query, top_k=top_k)

    if not groups:
        return "K-IFRS 기준서에서 관련 내용을 찾지 못했습니다."

    output = []
    for g_idx, g in enumerate(groups, 1):
        section = f"[{g_idx}] {g['heading']}"
        output.append(section)

        # 매칭된 Child 문단
        for mc in g["matched_children"]:
            para = mc.get("para_number", "?")
            score = mc.get("score", 0)
            output.append(f"  (문단 {para}, score={score:.4f})")
            output.append(f"  {mc['content']}\n")

        # 형제 문단 (매칭된 것 제외, 맥락 제공)
        matched_ids = {mc["chunk_id"] for mc in g["matched_children"]}
        siblings = [s for s in g["siblings"] if s["chunk_id"] not in matched_ids]
        if siblings:
            output.append(f"  [형제 문단 {len(siblings)}건]")
            for s in siblings[:3]:  # 최대 3개만
                preview = s["content"][:200].replace("\n", " ")
                output.append(f"  - 문단 {s.get('para_number', '?')}: {preview}...")

        output.append("---")

    return "\n".join(output)


ALL_TOOLS = [web_search, calculator, list_skills, get_skill, kifrs_search]
