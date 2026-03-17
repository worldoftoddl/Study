# IFRS 기준서 해독법과 RAG 시스템 설계 전략

**IFRS/K-IFRS 기준서는 세법과 근본적으로 다른 문서 구조를 가지며, 이 차이가 RAG 시스템의 청킹 전략을 결정짓는다.** IFRS는 "Standard → Appendix A(용어정의) → Appendix B(적용지침) → BC/IE(비규범적)" 체계로 이루어져 있고, 본문과 적용지침이 동등한 규범력을 갖는 반면, 한국 세법은 "편>장>절>관>조>항>호>목"의 8단계 계층에 "법률→시행령→시행규칙"의 3단 위임 구조가 결합된다. 회계 전문가는 IAS 8의 GAAP 계층을 따라 Scope 판단 → 정의 확인 → 본문 요건 → 적용지침 순서로 기준서를 읽으며, 이 독해 패턴이 곧 RAG 검색의 최적 경로가 된다. 최근 연구들은 법률·회계 문서에 대해 structure-aware hierarchical chunking과 cross-reference graph를 결합한 접근이 naive chunking 대비 현저히 우수함을 보여준다.

---

## IFRS 기준서는 규범력 기준으로 두 층위로 나뉜다

IFRS 기준서 하나는 여러 구성요소로 이루어져 있지만, 핵심 구분은 **"기준서의 일부(part of the Standard)"인지 아닌지**다. IFRS Foundation은 이를 명확히 구분한다.

**규범적(authoritative) 구성요소**는 네 가지다. 첫째, 본문(Standard text)으로 번호만 붙은 문단(예: 1, 2, 3... 또는 IFRS 9처럼 4.1.1, 5.7.1 형태)이다. 굵은 글씨 문단이 핵심 원칙을 진술하고 일반 문단이 이를 부연하지만, **모든 문단은 동등한 권위**를 갖는다. 둘째, 부록 A(Appendix A: Defined Terms)로 "이 부록은 기준서의 불가분 일부(integral part)"라고 명시된다. 셋째, 부록 B(Appendix B: Application Guidance)로 B1, B2... 또는 B4.1.7 형태로 번호가 매겨지며, 역시 "기준서의 다른 부분과 동일한 권위(same authority)"를 갖는다고 선언된다. 넷째, 부록 C/D(시행일, 경과규정, 타 기준서 개정)도 기준서의 일부다.

**비규범적(non-authoritative) 구성요소**는 기준서에 "수반(accompany)"하지만 일부가 아니다. 결론도출근거(Basis for Conclusions, BC1, BC2...)는 IASB가 왜 그런 결론에 도달했는지 설명하며, 사례(Illustrative Examples, IE1, IE2...)는 실무 적용 예시를 제공하고, 적용지침(Implementation Guidance, IG1, IG2...)은 Q&A 형태의 가이드다. 이들은 의무가 아니지만, 기준서의 rubric이 "결론도출근거의 맥락에서 읽어야 한다(should be read in the context of)"고 명시하므로 실무상 참조가 필수적이다.

| 구성요소 | 기준서의 일부? | 의무? | 문단 번호 형태 |
|---------|------------|------|-------------|
| 본문(Main text) | ✅ | ✅ | 1, 2, 3... 또는 4.1.1 |
| 부록 A 용어정의 | ✅ (integral part) | ✅ | 용어 목록 |
| 부록 B 적용지침 | ✅ (same authority) | ✅ | B1, B2... 또는 B4.1.7 |
| 결론도출근거(BC) | ❌ (accompanies) | ❌ | BC1, BCZ4.54... |
| 사례(IE) | ❌ | ❌ | IE1, IE2... |
| 적용지침(IG) | ❌ | ❌ | IG1, IG2... |
| 서론(IN) | ❌ | ❌ | IN1, IN2... |

K-IFRS는 이 구조를 **그대로 한국어로 번역**한 것이다. IFRS Foundation과의 저작권 계약에 따라 "내용을 추가, 삭감, 변경할 수 없다"는 원칙이 적용된다. 다만 한국 고유의 요구사항은 **"한" 접두사 문단**(예: 한138.1~한138.6)으로 추가되며, 대표적으로 국제 IFRS에 없는 **영업손익(operating profit/loss) 표시 의무**가 여기에 포함된다. K-IFRS 번호 체계는 제1001호(=IAS 1)~제1041호(=IAS 41), 제1101호(=IFRS 1)~제1118호(=IFRS 18), 제2101호 이후(=IFRIC/SIC 해석서)로 매핑된다.

---

## 전문가는 IAS 8 계층을 따라 기준서를 역추적한다

회계사·감사인이 새로운 거래를 만났을 때의 독해 순서는 IAS 8(회계정책, 회계추정의 변경과 오류) 문단 7-12가 규정하는 **GAAP 계층(hierarchy of GAAP)**을 그대로 반영한다.

**1단계: 어떤 기준서가 적용되는가(Scope 판단).** 전문가는 먼저 거래의 경제적 실질을 파악한 뒤, 해당될 수 있는 기준서들의 **Scope 문단**(통상 기준서 초반 2-8번 문단)을 확인한다. 여기서 핵심은 **scope exclusion(적용 범위 제외)**이다. 예를 들어 IFRS 15(수익)의 문단 5는 리스계약(→IFRS 16), 보험계약(→IFRS 17), 금융상품(→IFRS 9)을 명시적으로 제외한다. 여러 기준서가 겹칠 때는 "더 구체적인 기준서가 먼저 분리·측정하고, IFRS 15가 잔여 부분을 처리"하는 원칙이 적용된다. 리스+서비스 묶음 계약의 경우 IFRS 16이 리스 요소를 먼저 분리하고, 나머지 서비스 요소에 IFRS 15가 적용되는 식이다.

**2단계: 정의(Definitions) 확인.** Scope 판단의 관문이 바로 부록 A의 정의다. 계약이 "리스"의 정의(IFRS 16)를 충족하는지, "보험계약"의 정의(IFRS 17)를 충족하는지에 따라 적용 기준서가 달라진다. IFRS 본문에서 정의된 용어는 **첫 등장 시 이탤릭체**로 표시되어 독자에게 "이 용어는 기술적 정의가 있다"는 신호를 준다.

**3단계: 인식→측정→표시→공시 순서로 본문 요건 적용.** 기준서 본문의 실질적 요건은 대체로 인식(Recognition), 초기 측정(Initial Measurement), 후속 측정(Subsequent Measurement), 표시(Presentation), 공시(Disclosure) 순서로 배치되어 있다.

**4단계: 적용지침(Appendix B) 병행 참조.** 적용지침은 본문 원칙의 "how-to"를 제공한다. 예를 들어 IFRS 15의 B2-B13은 "기간에 걸쳐 이행되는 수행의무"의 구체적 판단 기준을, B34-B38은 "본인 vs 대리인" 판단 지침을 제공한다. 본문과 동일한 규범력이므로 반드시 함께 읽어야 한다.

**5단계: IE/BC 참조와 IFRIC 확인.** 비규범적이지만 사례(IE)는 IASB가 의도한 적용 방식을 보여주고, 결론도출근거(BC)는 모호한 요건의 해석 단서를 제공한다. IFRS 해석위원회(IFRIC)의 해석서는 규범적이며, 의제결정(Agenda Decisions)은 공식적으로는 의무가 아니지만 실무상 매우 강한 영향력을 행사한다.

**6단계: 해당 기준서가 없는 경우의 유추(IAS 8.10-12).** 특정 기준서가 없으면 유사한 거래를 다루는 다른 기준서를 유추 적용하고, 그래도 없으면 개념체계(Conceptual Framework)의 정의·인식기준·측정개념을 사용한다. US GAAP 등 다른 기준 체계도 참고할 수 있지만, IFRS나 개념체계와 충돌하면 안 된다.

---

## IFRS 텍스트의 세 가지 고유한 언어적 특성

**원칙 중심(principle-based) 서술이 판단 여지를 만든다.** IFRS는 US GAAP처럼 산업별 세부 규칙을 두지 않고 넓은 원칙을 제시한 뒤 전문가적 판단(professional judgment)에 맡긴다. "probable(개연성이 있는)", "virtually certain(거의 확실한)", "significant(유의적인)", "material(중요한)" 같은 **정성적 판단 용어**가 빈번하며, 밝은선(bright-line) 수치 기준이 거의 없다. 이는 NLP 시스템이 이진적 준수/비준수 판단을 내리기 어렵게 만드는 핵심 요인이다.

**조동사 계층이 의무의 강도를 결정한다.** IFRS 텍스트의 조동사는 명확한 규범적 위계를 형성한다:

- **"shall"** — 의무적 요건. "An entity **shall** recognise revenue when..." 거의 모든 요건 문단에 등장하며, K-IFRS에서는 "~한다", "~하여야 한다"로 번역된다
- **"shall not"** — 금지. "An entity **shall not** reclassify any financial liability"
- **"should"** — 강한 권고. 본문보다는 rubric이나 수반 자료에서 주로 사용
- **"may"** — 허용/선택권. "An entity **may** elect to use one or more of the following exemptions"
- **"can"** — 사실적 능력/가능성. 규범적 힘이 없는 서술적 표현

**조건문과 예외 구조가 복잡한 논리 트리를 형성한다.** IFRS는 "if...then", "unless", "except when", "to the extent that", "notwithstanding" 등의 조건 표현을 중첩적으로 사용한다. 예를 들어 IFRS 1에서: 최초 적용 기업은 IFRS 3을 소급 적용하지 않을 수 있다(may elect) → **그러나(however)** 하나라도 소급 적용하면 → 그 이후 모든 사업결합을 소급 적용**하여야 한다(shall)** → **그리고(and)** 같은 시점부터 IFRS 10도 적용하여야 한다. 이런 연쇄 조건 의존성은 단일 문단 내에서도 발생하며, 문단 간에 걸쳐 나타나기도 한다. "notwithstanding" 절은 앞선 일반 규칙을 무효화하는 계층적 우선순위 표지(override marker)로 기능한다.

상호참조(cross-reference)도 독특한 텍스트 특성이다. 기준서 내부 참조("문단 B22-B28 참조"), 기준서 간 참조("IFRS 9 문단 4.1.2에 따라"), BC/IE 참조("[참조: 결론도출근거 문단 BC4.1-BC4.45]") 등 세 종류의 참조가 촘촘한 네트워크를 형성한다. HTML 버전에서는 하이퍼링크로 구현되지만, PDF나 텍스트 추출 시에는 이 관계 정보가 손실되기 쉽다.

---

## RAG 시스템을 위한 청킹 전략: 구조 인식이 핵심이다

법률·회계 문서에 대한 naive chunking(고정 크기 분할)은 조건문 논리를 절단하고 상호참조를 파괴하며 계층 관계를 무시하기 때문에, 검색 품질이 현저히 떨어진다. 최근 연구들은 **structure-aware hierarchical chunking**을 권장한다.

**계층적 부모-자식(parent-child) 청킹**이 가장 유력한 접근이다. 부모 청크(500-2,000 토큰)는 섹션 단위의 넓은 맥락을 담고, 자식 청크(100-500 토큰)는 개별 문단이나 특정 요건을 담는다. 검색 시 자식 청크로 정밀 매칭한 뒤 부모 청크를 컨텍스트로 반환하는 방식이다. LangChain의 ParentDocumentRetriever, LlamaIndex의 HierarchicalNodeParser, Amazon Bedrock의 계층적 청킹 기능이 이를 구현한다.

**상호참조 해결(cross-reference resolution)**은 법률·회계 RAG의 가장 큰 도전이다. WhyHow.AI의 Chia Jeng Yang과 Timothy Chung은 2024년 말레이시아 규제 문서 대상 연구에서 **multi-graph multi-agent recursive retrieval** 방식을 제안했다. 조항 7.2가 "Para 7.3 and 7.4 참조"라고 할 때, 시스템이 문서 계층 그래프를 탐색하여 참조된 조항을 재귀적으로 검색하는 것이다. 이 방식은 GPT-4o 기반 표준 RAG를 포함한 기존 방법 대비 참조 의무 누락을 크게 줄였다.

**컨텍스트 강화(context enrichment)** 기법도 중요하다. Anthropic의 Contextual Retrieval(2024)은 LLM이 전체 문서 맥락에서 각 청크에 대한 간결한 맥락 설명을 생성하여 청크 앞에 붙이는 방식이다. "Towards Reliable Retrieval in RAG for Large Legal Datasets"(2025, arxiv 2510.06999)는 Summary-Augmented Chunking(SAC)을 제안하여 각 청크에 문서 수준 요약을 부착했고, 개인정보 보호정책·NDA·M&A 계약서에서 Document-Level Retrieval Mismatch를 감소시켰다. 메타데이터 접두(예: "IFRS 16 > 리스이용자 회계처리 > 인식")를 임베딩 전에 청크에 붙이는 것도 효과적이다.

**도메인 특화 의미 청킹**도 발전하고 있다. RegGuard(2026, arxiv 2601.17826)는 Roche와 협력하여 제약 규제 문서용 HiSACC(Hierarchical Semantic Aggregation for Contextual Chunking)를 개발했고, 비연속적 섹션 간의 의미적 일관성을 유지하면서 동적으로 의미 단위를 식별한다. LegalBench-RAG(2024, arxiv 2408.10343)는 법률 도메인 RAG 검색 평가를 위한 최초의 벤치마크를 제공한다.

IFRS 기준서에 특화된 권장 청킹 전략은 다음과 같다:

- 문서 구조를 먼저 파싱하여 문단 번호 패턴(B1, IE1, BC1 등)과 섹션 헤더를 인식
- 본문/적용지침/사례/결론도출근거를 **별도 컬렉션**으로 분리하되, 메타데이터(`standard`, `part_type`, `paragraph_id`, `references`)로 상호 연결
- 정의된 용어를 별도 그래프로 구축하여 청크에 해당 용어가 등장할 때 정의를 자동 검색
- **하이브리드 검색**(벡터 유사도 + BM25 키워드)을 적용하여 "제16조 제2항"이나 "IFRS 9.4.1.2" 같은 정확한 인용 매칭을 보장
- 한국어 법률 텍스트는 **800-1,500 토큰** 청크 크기가 권장됨(복수의 한국어 기술 블로그 확인)

---

## 한국 세법과 K-IFRS의 구조적 차이가 청킹 설계를 좌우한다

두 문서 체계의 구조적 차이는 근본적이며, 하나의 RAG 시스템에서 양자를 모두 처리하려면 **이중 청킹 전략**이 필요하다.

한국 세법의 계층은 **8단계**(편>장>절>관>조>항>호>목)에 달하지만, 실제 세법(법인세법, 소득세법 등)에서 편(Part)은 거의 사용되지 않고 장·절·관·조·항·호·목이 핵심이다. **조(Article)**가 기본 단위로 제목을 갖고(예: "제40조(손익의 귀속사업연도)"), 항(①②③)·호(1. 2. 3.)·목(가. 나. 다.)이 이를 세분한다. 인용 형식은 "법인세법 제40조 제1항 제2호"이며, 전통적 법률 관행에서는 공백 없이 붙여 쓴다("제274조제1항제4호").

K-IFRS의 계층은 이보다 평탄하다. **문단(Paragraph)**이 기본 단위이며, 섹션 제목으로 그룹화될 뿐 조·항·호 같은 다단계 하위 구조가 없다. 번호 체계도 단순 순번(1, 2, 3...)이거나 장 기반 점 표기(4.1.1, 5.7.1)다.

가장 중요한 구조적 차이는 **위임(delegation) 구조**에 있다. 세법은 법률→시행령(대통령령)→시행규칙(부령)의 **3단 위임 체계**를 갖는다. 법인세법 제40조가 "대통령령으로 정하는 바에 따라"라고 하면 법인세법 시행령 제69조가 세부 사항을 규정하고, 시행규칙이 서식과 절차를 정한다. 이 세 단계는 하나의 완결된 규범 단위를 형성하므로, RAG 시스템에서 **반드시 연결되어야** 한다. 국가법령정보센터(law.go.kr)의 "3단비교" 기능이 이 매핑을 시각화해 준다.

반면 K-IFRS는 기준서 본문+적용지침이 동일한 규범력으로 **하나의 문서 내에** 존재하며, 외부 위임이 없다. 해석은 IFRIC 해석서, KASB 질의회신, 금감원 질의회신 등을 통해 이루어지지만, 이들은 세법의 시행령처럼 법적 위임 관계에 있지 않다.

| 설계 차원 | 한국 세법 접근 | K-IFRS 접근 |
|---------|-----------|-----------|
| **청크 경계** | 조(Article) 단위 — 항/호/목을 포함하여 하나의 청크 | 문단(Paragraph) 또는 문단 그룹 |
| **문서 간 연결** | 3단 위임 필수 (법률↔시행령↔시행규칙) | 본문↔적용지침↔사례↔BC (권위 수준 태그) |
| **버전 관리** | 거의 매년 개정, 부칙 경과조치 추적 필수 | 상대적으로 덜 빈번, IASB 시행일 추적 |
| **권위 태깅** | 3단 모두 법적 구속력 (위계적) | 본문+AG 의무 / IE+BC 비의무 |
| **해석 레이어** | 판례·예규·통칙을 특정 조문에 연결 | IFRIC 해석서·의제결정·질의회신 |
| **검색 패턴** | 조문 번호 + 세목으로 검색 | 주제/개념 + 기준서 번호로 검색 |

세법 청크의 메타데이터 스키마는 `law_name`, `law_tier`(법률/시행령/시행규칙), `chapter`, `section`, `article_no`, `article_title`, `delegated_to`, `effective_date`, `related_interpretations`를 포함해야 한다. K-IFRS 청크는 `standard_no`, `original_ifrs`, `component_type`(본문/적용지침/사례/BC), `is_mandatory`, `paragraph_range`, `cross_references`, `is_korean_specific`(한 접두사 여부)을 포함해야 한다.

---

## 실무 구현을 위한 핵심 권장사항

K-IFRS와 한국 세법을 동시에 다루는 RAG 시스템 구축 시, 다음 아키텍처가 효과적이다.

**파싱 단계**에서 문서 유형별 정규식 파서를 구축한다. 세법용은 `제\d+조(의\d+)?(\s*제\d+항)?(\s*제\d+호)?(\s*[가-힣]목)?` 패턴, K-IFRS용은 `제1\d{3}호\s*문단\s*\d+(\.\d+)*` 또는 `B\d+\.\d+\.\d+` 패턴이 필요하다. 가지번호(제40조의2)가 독립 조문이지 제40조의 하위가 아니라는 점에 주의해야 한다.

**청킹 단계**에서는 LangChain의 RecursiveCharacterTextSplitter에 한국어 법률/IFRS 구조에 맞는 커스텀 구분자를 적용하되, LlamaIndex의 HierarchicalNodeParser로 부모-자식 관계를 구현한다. 조건문(if/unless/except when)이나 호·목 목록은 절대 분할하지 않는다.

**인덱싱 단계**에서는 하이브리드 검색(벡터 + BM25)을 적용한다. 법률 인용("제40조 제1항")의 정확 매칭에는 BM25가, 개념적 질의("리스 인식 요건")에는 벡터 검색이 각각 강점을 발휘한다. 한국어 임베딩 모델은 영어 대비 품질이 낮으므로, multilingual-e5-large나 Ko-SBERT를 K-IFRS/세법 코퍼스로 **파인튜닝**하는 것을 권장한다.

**검색 단계**에서는 cross-reference resolution을 구현한다. 검색된 세법 조문이 "시행령 제69조에서 정하는 바에 따라"를 포함하면 자동으로 해당 시행령 조문을 추가 검색하고, K-IFRS 문단이 "적용지침 B22-B28 참조"를 포함하면 해당 B문단들을 함께 반환한다. 그래프 DB(Neo4j 등)로 기준서 간 관계와 법률-시행령-시행규칙 위임 관계를 모델링하면, 복잡한 다중 홉(multi-hop) 질의에 대응할 수 있다.

**평가 단계**에서는 LegalBench-RAG 방법론을 참고하되, 한국어 법률/회계 도메인 특화 테스트 셋을 구축해야 한다. 단순 nDCG@k 외에 Document-Level Retrieval Mismatch(DRM), cross-reference coverage(참조 조문 포함률), authority-level accuracy(규범적/비규범적 구분 정확도)를 추적 지표로 삼는 것이 바람직하다.

---

## 주요 참고 문헌과 기술 자료

법률·회계 문서 RAG에 관한 학술 연구가 빠르게 축적되고 있다. "LegalBench-RAG: A Benchmark for Retrieval-Augmented Generation in the Legal Domain"(2024, arxiv 2408.10343)은 법률 RAG 벤치마크의 기초를 놓았고, Ferraris 등의 "Legal Chunking: Evaluating Methods for Effective Legal Text Retrieval"(IOS Press, 2024)은 GDPR 텍스트에 대해 단순 분할·재귀 분할·의미 분할을 비교했다. "RegGuard"(2026, arxiv 2601.17826)는 HiSACC와 ReLACE를 통해 제약 규제 문서의 검색 정확도를 개선했고, "RAGulating Compliance"(Agarwal 등, 2025, arxiv 2508.09893)는 규제 트리플릿 지식그래프와 RAG를 결합한 다중 에이전트 프레임워크를 제시했다. IFRS 도메인에서는 IFRS 지속가능성보고 기준서 RAG 시스템 연구(2025, arxiv 2502.04095)가 보고서 섹션 계층을 보존하는 맞춤형 멀티모달 파이프라인을 구현했다. WhyHow.AI의 recursive retrieval 접근(2024, GitHub 공개)과 TrueLaw AI의 Contextual Legal RAG 블로그(2024)도 실무적 통찰을 제공한다.

## Conclusion

K-IFRS와 한국 세법은 문서 구조가 근본적으로 다르며, **하나의 청킹 전략으로 양자를 동시에 처리하는 것은 비효율적**이다. 세법은 조(Article)를 원자 단위로 하여 3단 위임 체계를 그래프로 연결해야 하고, K-IFRS는 문단을 원자 단위로 하여 본문-적용지침-사례-BC의 권위 수준을 태깅하고 상호참조를 해결해야 한다. 양 체계 모두에서 cross-reference resolution이 검색 품질의 핵심 병목이며, 이를 해결하기 위한 그래프 기반 접근과 재귀적 검색이 가장 유망한 방향이다. 실무적으로는 structure-aware hierarchical chunking + 하이브리드 검색 + 메타데이터 강화 + 도메인 파인튜닝 임베딩의 조합이 현재 최선의 아키텍처다.