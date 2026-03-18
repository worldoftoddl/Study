#!/usr/bin/env python3
"""
DOCX MD 보일러플레이트 섹션 삭제 스크립트

삭제 대상:
1. ## 시행일* 섹션 (개정이력) — 단, ### 경과 규정 하위섹션은 보존
2. 의결문 블록 (회계기준위원회의 의결)
3. ### 기타 참고사항 섹션
4. 제·개정 경과 섹션

보존 대상:
- ### 경과 규정 (실질 회계 지침)
- 본문, 결론도출근거, 적용사례, 부록 등
"""

import re
from pathlib import Path


def remove_sections(lines: list[str]) -> list[str]:
    """시행일, 의결문, 기타 참고사항, 제·개정 경과 섹션 삭제."""
    result = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 1) ## 시행일* 섹션 감지
        if re.match(r'^## 시행일', stripped):
            # 시행일 헤더 ~ 다음 ## 헤더 전까지 스캔
            # 단, ### 경과 규정이 나오면 그 부분은 보존
            j = i + 1
            transition_blocks = []  # (start, end) of 경과규정 blocks

            while j < n:
                s = lines[j].strip()
                # 다음 ## 레벨 헤더가 나오면 시행일 섹션 끝
                if re.match(r'^## [^#]', s):
                    break
                # "부록" 단독 라인도 시행일 섹션 종료 (경영진설명서 등)
                if s == '부록':
                    break
                # ### 경과 규정 발견 → 보존 블록 시작
                if re.match(r'^### 경과\s*규정', s):
                    k_start = j
                    k = j + 1
                    while k < n:
                        ks = lines[k].strip()
                        # ### 또는 ## 레벨 헤더가 나오면 경과규정 블록 끝
                        if re.match(r'^#{2,3} [^#]', ks):
                            break
                        # 의결문이 나오면 경과규정 블록 끝
                        if re.search(r'회계기준위원회의\s*의결', ks):
                            break
                        k += 1
                    transition_blocks.append((k_start, k))
                    j = k
                else:
                    j += 1

            # 경과규정 블록이 있으면 해당 부분만 결과에 추가
            for (ts, te) in transition_blocks:
                # 경과규정 앞에 빈줄 추가
                if result and result[-1].strip():
                    result.append('\n')
                for idx in range(ts, te):
                    result.append(lines[idx])

            i = j
            continue

        # 2) 의결문 블록: 다양한 형태의 회계기준위원회 의결문
        #    - "기업회계기준(서|해석서) 제XXXX호의 제정/개정/수정에 대한 회계기준위원회의 의결"
        #    - "'재무보고를 위한 개념체계'의 전면개정에 대한 회계기준위원회의 의결"
        if re.search(r'회계기준위원회의\s*의결', stripped) and not stripped.startswith('#'):
            # 의결문 블록 ~ 다음 ## 헤더 또는 다른 구조적 마커까지 삭제
            j = i + 1
            while j < n:
                s = lines[j].strip()
                # ## 헤더면 중단
                if re.match(r'^## [^#]', s):
                    break
                # 다음 의결문 블록이면 중단 (해당 블록에서 다시 처리)
                if re.search(r'회계기준위원회의\s*의결', s):
                    break
                # ### 헤더면 중단 (기타 참고사항 등)
                if re.match(r'^### ', s):
                    break
                j += 1
            i = j
            continue

        # 3) ### 기타 참고사항 섹션
        if re.match(r'^### 기타 참고사항', stripped):
            j = i + 1
            while j < n:
                s = lines[j].strip()
                if re.match(r'^#{2,3} [^#]', s):
                    # 기타 참고사항 내부의 하위 내용은 삭제, ## 레벨에서 중단
                    if s.startswith('## '):
                        break
                    # ### 레벨이 "기타 참고사항" 내부 하위인지 다른 섹션인지 판단
                    # 기타 참고사항 아래에는 국제회계기준과의 관계, 기준서 주요 특징 등이 있음
                    # 안전하게: 제·개정 경과 이후 끝나므로 ## 에서만 중단
                    if s.startswith('## '):
                        break
                j += 1
            i = j
            continue

        # 4) 제·개정 경과 섹션 (보통 파일 말미)
        if re.match(r'^제·개정 경과$', stripped):
            j = i + 1
            while j < n:
                s = lines[j].strip()
                if re.match(r'^## [^#]', s):
                    break
                j += 1
            i = j
            continue

        # 5) "이 해석서의 주요 특징" — 기타 참고사항 하위 블록 (### 없이 단독)
        #    기타 참고사항과 같이 삭제되므로 별도 처리 불필요

        result.append(line)
        i += 1

    # 후처리: 연속 빈줄 3개 이상을 2개로 축소
    cleaned = []
    blank_count = 0
    for line in result:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)

    # 파일 끝 빈줄 정리
    while cleaned and cleaned[-1].strip() == '':
        cleaned.pop()
    cleaned.append('\n')

    return cleaned


def process_file(filepath: Path, dry_run: bool = False) -> dict:
    """단일 파일 처리. 삭제된 라인 수 등 통계 반환."""
    text = filepath.read_text(encoding='utf-8')
    lines = text.split('\n')
    # split 후 마지막에 빈 문자열이 붙으므로 줄 단위로 \n 보존
    lines_with_nl = [line + '\n' for line in lines[:-1]]
    if lines[-1]:  # 마지막 줄에 개행이 없었으면
        lines_with_nl.append(lines[-1] + '\n')

    original_count = len(lines_with_nl)
    cleaned = remove_sections(lines_with_nl)
    new_count = len(cleaned)
    removed = original_count - new_count

    stats = {
        'file': filepath.name,
        'original_lines': original_count,
        'new_lines': new_count,
        'removed_lines': removed,
    }

    if not dry_run and removed > 0:
        filepath.write_text(''.join(cleaned), encoding='utf-8')

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='DOCX MD 보일러플레이트 섹션 삭제')
    parser.add_argument('--dry-run', action='store_true', help='변경하지 않고 통계만 출력')
    parser.add_argument('--single', type=str, help='단일 파일만 처리')
    args = parser.parse_args()

    md_dir = Path(__file__).parent.parent / 'output' / 'docx_md'

    if args.single:
        files = [md_dir / args.single]
    else:
        # _TOC_ 파일 제외
        files = sorted(f for f in md_dir.glob('*.md') if not f.name.startswith('_TOC_'))

    total_removed = 0
    changed_files = 0

    for f in files:
        if not f.exists():
            print(f"  [SKIP] {f.name} not found")
            continue
        stats = process_file(f, dry_run=args.dry_run)
        if stats['removed_lines'] > 0:
            changed_files += 1
            total_removed += stats['removed_lines']
            print(f"  {'[DRY]' if args.dry_run else '[OK]'} {stats['file']}: "
                  f"{stats['original_lines']} → {stats['new_lines']} (-{stats['removed_lines']})")

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}총 {changed_files}개 파일에서 {total_removed}줄 삭제")


if __name__ == '__main__':
    main()
