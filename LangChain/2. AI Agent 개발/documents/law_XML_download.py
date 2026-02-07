"""
법령 XML 자동 다운로드 스크립트
================================
법제처 Open API(law.go.kr/DRF)를 사용하여
지정한 법령들의 현행 XML을 자동으로 다운로드합니다.

사용법:
    python download_laws.py

설정:
    - OC: 법제처 Open API 인증키 (본인 키로 교체)
    - LAWS: 다운로드할 법령 목록 (법령명, 파일명, 시행령/시행규칙 포함 여부)
    - OUTPUT_DIR: 저장 경로
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os
import time
import json
from datetime import datetime
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()


# ============================================================
# 설정
# ============================================================

OC = os.environ["LAW_API_OC"]  # 법제처 Open API 인증키

OUTPUT_DIR = "./law_xml"  # 저장 디렉토리

# 다운로드할 법령 목록
# include_sub=True → 시행령 + 시행규칙도 함께 다운로드
LAWS = [
    {"name": "소득세법",           "include_sub": True},
    {"name": "법인세법",           "include_sub": True},
    {"name": "부가가치세법",       "include_sub": True},
    {"name": "조세특례제한법",     "include_sub": True},
    {"name": "국세기본법",         "include_sub": True},
    {"name": "종합부동산세법",     "include_sub": True},
    {"name": "상속세 및 증여세법", "include_sub": True},
    {"name": "국세징수법",         "include_sub": True},
]


# ============================================================
# API URL 구성
# ============================================================

SEARCH_URL = "https://law.go.kr/DRF/lawSearch.do"
DOWNLOAD_URL = "https://www.law.go.kr/DRF/lawService.do"


@dataclass
class LawInfo:
    """검색 결과에서 추출한 법령 정보"""
    name: str           # 법령명
    mst: str            # 법령일련번호 (MST)
    ef_date: str        # 시행일자 (efYd)
    law_type: str       # 법률/대통령령/부령
    pub_date: str       # 공포일자
    pub_no: str         # 공포번호


def search_law(query: str, exact_name: str | None = None) -> list[LawInfo]:
    """
    법령 검색 API를 호출하여 현행 법령 정보를 반환합니다.
    
    Parameters
    ----------
    query : str
        검색어 (URL 인코딩 전 한글)
    exact_name : str, optional
        정확히 일치하는 법령명으로 필터링. 
        None이면 query를 그대로 사용.
        
    Returns
    -------
    list[LawInfo]
        현행 법령 목록 (보통 1개, 시행령/시행규칙 포함 시 여러 개)
    
    주의사항
    --------
    - 검색 API(target=eflaw)는 연혁법령까지 모두 반환합니다.
    - <현행연혁코드>현행</현행연혁코드>인 항목만 필터링합니다.
    - 검색어가 포함된 다른 법령도 나올 수 있으므로 exact_name으로 필터링합니다.
      예: "소득세법" 검색 → "소득세법", "소득세법 시행령", "소득세법 시행규칙",
          "법인세법상 소득세법 관련..." 등이 모두 나올 수 있음
    """
    if exact_name is None:
        exact_name = query
        
    encoded_query = urllib.parse.quote(query)
    url = f"{SEARCH_URL}?OC={OC}&target=eflaw&query={encoded_query}"
    
    print(f"  🔍 검색 중: {query}")
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    data = resp.read().decode("utf-8")
    
    # XML 파싱
    root = ET.fromstring(data)
    
    results = []
    for law_elem in root.findall("law"):
        # 현행만 필터링
        status = law_elem.findtext("현행연혁코드", "")
        if status != "현행":
            continue
        
        # 법령명 정확 매칭
        name = law_elem.findtext("법령명한글", "").strip()
        if name != exact_name:
            continue
        
        info = LawInfo(
            name=name,
            mst=law_elem.findtext("법령일련번호", ""),
            ef_date=law_elem.findtext("시행일자", ""),
            law_type=law_elem.findtext("법령구분명", ""),
            pub_date=law_elem.findtext("공포일자", ""),
            pub_no=law_elem.findtext("공포번호", ""),
        )
        results.append(info)
    
    return results


def download_law_xml(law_info: LawInfo, output_path: str) -> bool:
    """
    법령 XML을 다운로드하여 파일로 저장합니다.
    
    Parameters
    ----------
    law_info : LawInfo
        다운로드할 법령 정보
    output_path : str
        저장할 파일 경로
        
    Returns
    -------
    bool
        성공 여부
        
    참고
    ----
    - target=law + type=XML 조합으로 전체 법령 XML을 받습니다.
    - efYd(시행일자)를 함께 전달해야 해당 시점의 법령을 받을 수 있습니다.
    """
    url = (
        f"{DOWNLOAD_URL}?OC={OC}&target=law"
        f"&MST={law_info.mst}&type=XML&efYd={law_info.ef_date}"
    )
    
    print(f"  ⬇️  다운로드: {law_info.name} (MST={law_info.mst}, 시행일={law_info.ef_date})")
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=60)
        data = resp.read()
        
        with open(output_path, "wb") as f:
            f.write(data)
        
        size_kb = len(data) / 1024
        print(f"  ✅ 저장 완료: {output_path} ({size_kb:.1f} KB)")
        return True
        
    except Exception as e:
        print(f"  ❌ 다운로드 실패: {e}")
        return False


def make_filename(law_name: str) -> str:
    """
    법령명 → 파일명 변환
    공백과 특수문자를 제거하여 안전한 파일명을 만듭니다.
    
    예: "상속세 및 증여세법" → "상속세_및_증여세법.xml"
    """
    safe_name = law_name.replace(" ", "_")
    return f"{safe_name}.xml"


def get_sub_law_names(base_name: str) -> list[str]:
    """
    본법 이름으로부터 시행령/시행규칙 이름을 생성합니다.
    
    예: "소득세법" → ["소득세법 시행령", "소득세법 시행규칙"]
    
    주의: 모든 법률에 시행규칙이 있는 것은 아닙니다.
    시행규칙이 없는 경우 검색 결과가 비어있어 건너뜁니다.
    """
    return [
        f"{base_name} 시행령",
        f"{base_name} 시행규칙",
    ]

def download(name: str, output_dir: str = "./law_xml", include_sub: bool = False) -> None:
    """
    법령명만 넣으면 바로 다운로드.
    
    사용법 (ipynb):
        from law_XML_download import download
        download("소득세법")
        download("소득세법", include_sub=True)  # 시행령+시행규칙 포함
    """
    os.makedirs(output_dir, exist_ok=True)
    
    targets = [name]
    if include_sub:
        targets.extend(get_sub_law_names(name))
    
    for target_name in targets:
        found = search_law(target_name)
        if not found:
            print(f"  ⚠️  '{target_name}' 현행 법령을 찾을 수 없습니다.")
            continue
        
        output_path = os.path.join(output_dir, make_filename(target_name))
        download_law_xml(found[0], output_path)
        time.sleep(1)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("법령 XML 자동 다운로드")
    print(f"저장 경로: {os.path.abspath(OUTPUT_DIR)}")
    print(f"다운로드 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 다운로드 결과를 기록할 리스트
    results = []
    
    for law_config in LAWS:
        base_name = law_config["name"]
        include_sub = law_config.get("include_sub", False)
        
        # 다운로드할 법령명 목록 구성
        targets = [base_name]
        if include_sub:
            targets.extend(get_sub_law_names(base_name))
        
        print(f"\n{'─' * 50}")
        print(f"📋 {base_name} (시행령/시행규칙 포함: {include_sub})")
        print(f"{'─' * 50}")
        
        for target_name in targets:
            # 1) 검색
            found = search_law(query=target_name, exact_name=target_name)
            
            if not found:
                print(f"  ⚠️  '{target_name}' 현행 법령을 찾을 수 없습니다. 건너뜁니다.")
                results.append({
                    "법령명": target_name,
                    "상태": "NOT_FOUND",
                    "파일": None,
                })
                time.sleep(0.5)
                continue
            
            law_info = found[0]
            
            # 2) 다운로드
            filename = make_filename(target_name)
            output_path = os.path.join(OUTPUT_DIR, filename)
            
            success = download_law_xml(law_info, output_path)
            
            results.append({
                "법령명": target_name,
                "상태": "OK" if success else "FAILED",
                "파일": filename if success else None,
                "법령일련번호": law_info.mst,
                "시행일자": law_info.ef_date,
                "공포일자": law_info.pub_date,
                "법령구분": law_info.law_type,
            })
            
            # API 부하 방지를 위한 딜레이
            time.sleep(1)
    
    # ============================================================
    # 결과 요약
    # ============================================================
    print(f"\n{'=' * 60}")
    print("📊 다운로드 결과 요약")
    print(f"{'=' * 60}")
    
    ok_count = sum(1 for r in results if r["상태"] == "OK")
    fail_count = sum(1 for r in results if r["상태"] == "FAILED")
    skip_count = sum(1 for r in results if r["상태"] == "NOT_FOUND")
    
    for r in results:
        icon = {"OK": "✅", "FAILED": "❌", "NOT_FOUND": "⚠️"}[r["상태"]]
        name = r["법령명"]
        if r["상태"] == "OK":
            print(f"  {icon} {name:<25s} → {r['파일']} (시행일: {r['시행일자']})")
        elif r["상태"] == "NOT_FOUND":
            print(f"  {icon} {name:<25s} → 현행 법령 없음 (건너뜀)")
        else:
            print(f"  {icon} {name:<25s} → 다운로드 실패")
    
    print(f"\n  총 {len(results)}건 중 성공 {ok_count} / 실패 {fail_count} / 건너뜀 {skip_count}")
    
    # 결과를 JSON으로도 저장 (나중에 메타데이터로 활용 가능)
    meta_path = os.path.join(OUTPUT_DIR, "_download_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "download_date": datetime.now().isoformat(),
            "oc": OC,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  메타데이터 저장: {meta_path}")


if __name__ == "__main__":
    main()