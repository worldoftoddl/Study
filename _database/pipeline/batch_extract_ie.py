#!/usr/bin/env python3
"""
적용사례(IE) 섹션 일괄 분리 스크립트

output/docx_md/ 의 모든 MD 파일에서 적용사례 섹션을 찾아
output/docx_md/적용사례/ 에 별도 파일로 저장하고, 원본에서 제거합니다.

Usage:
    python pipeline/batch_extract_ie.py              # 실제 실행
    python pipeline/batch_extract_ie.py --dry-run     # 미리보기만
    python pipeline/batch_extract_ie.py --single 1033 # 특정 기준서만
"""

import argparse
import re
from pathlib import Path

DOCX_MD_DIR = Path(__file__).parent.parent / 'output' / 'docx_md'
IE_DIR = DOCX_MD_DIR / '적용사례'

# 적용사례 시작 패턴: "## 적용사례" 또는 "## 적용사례실무적용지침"
IE_START_RE = re.compile(r'^## 적용사례')

# 적용사례 종료 패턴 (이 줄은 포함하지 않음)
IE_END_RE = re.compile(r'^## 결론도출근거')

# 적용사례 종료가 아닌 ## 헤더: 부록, 사례 등은 적용사례 내부 구조
# 종료는 오직 ## 결론도출근거 또는 ## 본 문 (중복 구조) 에서만

# _TOC_ 파일 제외
SKIP_PREFIXES = ('_TOC_',)


def extract_standard_info(filename: str) -> tuple:
    """파일명에서 기준서 번호와 제목 추출.

    Returns:
        (번호, 제목) 또는 (None, None)
    """
    # K-IFRS 제NNNN호_제목(...)
    m = re.search(r'제(\d{4})호_(.+?)[\(]', filename)
    if m:
        num = m.group(1)
        title = m.group(2).rstrip('_')
        return num, title

    # 비표준: 경영진설명서
    if '경영진설명서' in filename:
        return '실무서1', '경영진설명서'

    # 비표준: 실무서 2
    if '실무서_2' in filename:
        return '실무서2', '중요성에_대한_판단'

    # 비표준: 개념체계
    if '개념체계' in filename and '경영진' not in filename:
        return '개념체계', '재무보고를_위한_개념체계'

    return None, None


def find_ie_ranges(lines: list) -> list:
    """적용사례 섹션의 (start_inclusive, end_exclusive) 인덱스 쌍 목록 반환.

    end_exclusive는 ## 결론도출근거 줄 (포함하지 않음).
    결론도출근거가 없으면 파일 끝까지.
    """
    ranges = []
    i = 0
    n = len(lines)

    while i < n:
        if IE_START_RE.match(lines[i]):
            start = i
            # 종료 지점 탐색: 오직 ## 결론도출근거 또는 ## 본 문 에서만 종료
            end = n  # 기본: 파일 끝
            j = i + 1
            while j < n:
                line = lines[j]
                if IE_END_RE.match(line):
                    end = j
                    break
                # 중복 구조: ## 본 문 이 나오면 종료 (1033호 등)
                if line.strip() == '## 본 문':
                    end = j
                    break
                j += 1
            ranges.append((start, end))
            i = end
        else:
            i += 1

    return ranges


def process_file(md_path: Path, dry_run: bool = False) -> dict:
    """단일 MD 파일에서 적용사례 추출.

    Returns:
        결과 dict 또는 None (적용사례 없음)
    """
    content = md_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    ranges = find_ie_ranges(lines)
    if not ranges:
        return None

    # 첫 번째 범위의 IE 콘텐츠만 사용 (중복 구조 대응)
    first_start, first_end = ranges[0]
    ie_lines = lines[first_start:first_end]

    # 모든 범위를 원본에서 제거 (역순으로)
    remaining_lines = lines[:]
    for start, end in reversed(ranges):
        del remaining_lines[start:end]

    ie_content = '\n'.join(ie_lines)
    remaining = '\n'.join(remaining_lines)

    # 연속 빈 줄 정리
    ie_content = re.sub(r'\n{3,}', '\n\n', ie_content).strip() + '\n'
    remaining = re.sub(r'\n{3,}', '\n\n', remaining).strip() + '\n'

    ie_line_count = ie_content.count('\n')
    removed_total = sum(end - start for start, end in ranges)

    result = {
        'ie_content': ie_content,
        'remaining': remaining,
        'ie_lines': ie_line_count,
        'removed_lines': removed_total,
        'num_ranges': len(ranges),
        'ranges': ranges,
    }

    return result


def count_tables(text: str) -> int:
    """마크다운 텍스트 내 테이블 수 (| --- | 패턴 기준)."""
    return len(re.findall(r'^\|[\s\-|]+\|$', text, re.MULTILINE))


def check_broken_tables(text: str) -> list:
    """깨진 테이블 징후 탐지. 문제 목록 반환."""
    issues = []
    # 1열짜리 테이블 (구분선이 | --- | 만)
    single_col = re.findall(r'^\| --- \|$', text, re.MULTILINE)
    if single_col:
        issues.append(f'1열 테이블 {len(single_col)}개')

    return issues


def main():
    parser = argparse.ArgumentParser(description='적용사례(IE) 섹션 일괄 분리')
    parser.add_argument('--dry-run', action='store_true', help='실제 파일 수정 없이 미리보기만')
    parser.add_argument('--single', type=str, help='특정 기준서 번호만 처리 (예: 1033)')
    args = parser.parse_args()

    if not args.dry_run:
        IE_DIR.mkdir(exist_ok=True)

    results = []
    skipped = []
    table_issues = []

    md_files = sorted(DOCX_MD_DIR.glob('*.md'))

    for md_path in md_files:
        # _TOC_ 파일 건너뛰기
        if any(md_path.name.startswith(p) for p in SKIP_PREFIXES):
            continue

        num, title = extract_standard_info(md_path.name)
        if num is None:
            continue

        # --single 필터
        if args.single and args.single not in num:
            continue

        result = process_file(md_path, dry_run=args.dry_run)
        if result is None:
            skipped.append(f'{num} ({title})')
            continue

        ie_filename = f'IE_K-IFRS_{num}_{title}.md'
        ie_path = IE_DIR / ie_filename

        # 테이블 품질 점검
        n_tables = count_tables(result['ie_content'])
        issues = check_broken_tables(result['ie_content'])
        if issues:
            table_issues.append((num, title, issues))

        if not args.dry_run:
            # IE 파일 저장
            ie_path.write_text(result['ie_content'], encoding='utf-8')
            # 원본 수정
            md_path.write_text(result['remaining'], encoding='utf-8')

        status = '(dry-run)' if args.dry_run else '✓'
        dup_note = f' [중복 {result["num_ranges"]}개 범위]' if result['num_ranges'] > 1 else ''
        issue_note = f' ⚠ {", ".join(issues)}' if issues else ''

        print(f'{status} {num:>6s}: {result["ie_lines"]:>5d}줄 추출, '
              f'원본 {result["removed_lines"]:>5d}줄 제거, '
              f'테이블 {n_tables}개 → {ie_filename}'
              f'{dup_note}{issue_note}')

        results.append({
            'num': num,
            'title': title,
            'ie_filename': ie_filename,
            'ie_lines': result['ie_lines'],
            'removed_lines': result['removed_lines'],
            'num_ranges': result['num_ranges'],
            'n_tables': n_tables,
        })

    # 요약
    print(f'\n{"=" * 60}')
    print(f'처리 완료: {len(results)}개 파일')
    print(f'적용사례 없음: {len(skipped)}개 파일')
    if skipped:
        print(f'  → {", ".join(skipped[:10])}{"..." if len(skipped) > 10 else ""}')

    total_ie_lines = sum(r['ie_lines'] for r in results)
    total_removed = sum(r['removed_lines'] for r in results)
    total_tables = sum(r['n_tables'] for r in results)
    print(f'총 적용사례: {total_ie_lines:,}줄')
    print(f'원본에서 제거: {total_removed:,}줄')
    print(f'테이블 총: {total_tables}개')

    if table_issues:
        print(f'\n⚠ 테이블 품질 이슈 ({len(table_issues)}개 파일):')
        for num, title, issues in table_issues:
            print(f'  {num} {title}: {", ".join(issues)}')

    dup_files = [r for r in results if r['num_ranges'] > 1]
    if dup_files:
        print(f'\n⚠ 중복 구조 파일 ({len(dup_files)}개):')
        for r in dup_files:
            print(f'  {r["num"]} {r["title"]}: {r["num_ranges"]}개 범위')


if __name__ == '__main__':
    main()
