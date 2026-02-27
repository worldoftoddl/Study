# K-IFRS 표준계정과목 체계

> **데이터 출처**: DART XBRL 택소노미 (K-IFRS 2024) 기반 구조  
> **Balance 속성**: XBRL `xbrli:balance` 규격 + CPA 규칙 기반  
> **접두사 규칙**: `ifrs-full_` = IFRS 글로벌 표준, `dart_` = DART 한국 확장  
> **is_abstract**: ○ 표시된 계정은 분류용이므로 분개에 직접 사용 불가

---

## 재무상태표 (BS) — 자산

### 유동자산

| ID | 계정과목명 | 영문명 | Balance | Abstract | 상위계정 | 비고 |
|----|-----------|--------|---------|----------|---------|------|
| ifrs-full_Assets | 자산 | Assets | debit | ○ | — | 최상위 |
| ifrs-full_CurrentAssets | 유동자산 | Current assets | debit | ○ | Assets | |
| ifrs-full_CashAndCashEquivalents | 현금및현금성자산 | Cash and cash equivalents | debit | | CurrentAssets | |
| ifrs-full_ShortTermDepositsNotClassifiedAsCashEquivalents | 단기금융상품 | Short-term deposits | debit | | CurrentAssets | |
| ifrs-full_CurrentFinancialAssetsAtFairValueThroughProfitOrLoss | 당기손익-공정가치 측정 금융자산(유동) | Current financial assets at FVTPL | debit | | CurrentAssets | |
| ifrs-full_CurrentFinancialAssetsAtFairValueThroughOtherComprehensiveIncome | 기타포괄손익-공정가치 측정 금융자산(유동) | Current financial assets at FVOCI | debit | | CurrentAssets | |
| ifrs-full_TradeAndOtherCurrentReceivables | 매출채권 및 기타유동채권 | Trade and other current receivables | debit | | CurrentAssets | |
| ifrs-full_TradeReceivables | 매출채권 | Trade receivables | debit | | TradeAndOtherCurrentReceivables | |
| dart_ShortTermLoansReceivable | 단기대여금 | Short-term loans receivable | debit | | TradeAndOtherCurrentReceivables | |
| dart_AccruedRevenues | 미수수익 | Accrued revenues | debit | | TradeAndOtherCurrentReceivables | |
| dart_AdvancePayments | 선급금 | Advance payments | debit | | TradeAndOtherCurrentReceivables | |
| ifrs-full_AllowanceAccountForCreditLossesOfTradeReceivables | 매출채권 대손충당금 | Allowance for credit losses | **credit** | | TradeReceivables | ⚠️ **contra_asset** |
| dart_PrepaidExpenses | 선급비용 | Prepaid expenses | debit | | CurrentAssets | |
| ifrs-full_Inventories | 재고자산 | Inventories | debit | | CurrentAssets | |
| dart_RawMaterials | 원재료 | Raw materials | debit | | Inventories | |
| dart_WorkInProgress | 재공품 | Work in progress | debit | | Inventories | |
| dart_FinishedGoods | 제품 | Finished goods | debit | | Inventories | |
| dart_Merchandise | 상품 | Merchandise | debit | | Inventories | |
| ifrs-full_AllowanceForWritedownOfInventories | 재고자산평가충당금 | Allowance for write-down of inventories | **credit** | | Inventories | ⚠️ **contra_asset** |
| ifrs-full_OtherCurrentAssets | 기타유동자산 | Other current assets | debit | | CurrentAssets | |
| ifrs-full_CurrentTaxAssets | 당기법인세자산 | Current tax assets | debit | | CurrentAssets | |
| ifrs-full_NoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSale | 매각예정비유동자산 | Non-current assets held for sale | debit | | CurrentAssets | |
| ifrs-full_ContractAssets | 계약자산 | Contract assets | debit | | CurrentAssets | |
| dart_VATReceivable | 부가세대급금 | VAT receivable | debit | | CurrentAssets | |

### 비유동자산

| ID | 계정과목명 | 영문명 | Balance | Abstract | 상위계정 | 비고 |
|----|-----------|--------|---------|----------|---------|------|
| ifrs-full_NoncurrentAssets | 비유동자산 | Non-current assets | debit | ○ | Assets | |
| ifrs-full_PropertyPlantAndEquipment | 유형자산 | Property, plant and equipment | debit | | NoncurrentAssets | |
| dart_Land | 토지 | Land | debit | | PPE | |
| dart_Buildings | 건물 | Buildings | debit | | PPE | |
| dart_Machinery | 기계장치 | Machinery | debit | | PPE | |
| dart_Vehicles | 차량운반구 | Vehicles | debit | | PPE | |
| dart_OfficeEquipment | 비품 | Office equipment | debit | | PPE | |
| dart_ConstructionInProgress | 건설중인자산 | Construction in progress | debit | | PPE | |
| ifrs-full_AccumulatedDepreciationAndAmortisationPropertyPlantAndEquipment | 유형자산 감가상각누계액 | Accumulated depreciation of PPE | **credit** | | PPE | ⚠️ **contra_asset** |
| ifrs-full_RightOfUseAssets | 사용권자산 | Right-of-use assets | debit | | NoncurrentAssets | |
| ifrs-full_InvestmentProperty | 투자부동산 | Investment property | debit | | NoncurrentAssets | |
| ifrs-full_IntangibleAssetsOtherThanGoodwill | 무형자산 | Intangible assets other than goodwill | debit | | NoncurrentAssets | |
| ifrs-full_Goodwill | 영업권 | Goodwill | debit | | NoncurrentAssets | |
| dart_DevelopmentCosts | 개발비 | Development costs | debit | | IntangibleAssets | |
| dart_SoftwareCosts | 소프트웨어 | Software | debit | | IntangibleAssets | |
| ifrs-full_InvestmentsAccountedForUsingEquityMethod | 관계기업 및 공동기업 투자 | Investments in associates/JV | debit | | NoncurrentAssets | |
| ifrs-full_NoncurrentFinancialAssetsAtFairValueThroughProfitOrLoss | 당기손익-공정가치 측정 금융자산(비유동) | Non-current financial assets at FVTPL | debit | | NoncurrentAssets | |
| ifrs-full_NoncurrentFinancialAssetsAtFairValueThroughOtherComprehensiveIncome | 기타포괄손익-공정가치 측정 금융자산(비유동) | Non-current financial assets at FVOCI | debit | | NoncurrentAssets | |
| ifrs-full_NoncurrentFinancialAssetsAtAmortisedCost | 상각후원가 측정 금융자산(비유동) | Non-current financial assets at amortised cost | debit | | NoncurrentAssets | |
| dart_LongTermLoansReceivable | 장기대여금 | Long-term loans receivable | debit | | NoncurrentAssets | |
| ifrs-full_DeferredTaxAssets | 이연법인세자산 | Deferred tax assets | debit | | NoncurrentAssets | |
| dart_LongTermPrepaidExpenses | 장기선급비용 | Long-term prepaid expenses | debit | | NoncurrentAssets | |
| dart_Deposits | 보증금 | Deposits | debit | | NoncurrentAssets | |
| ifrs-full_OtherNoncurrentAssets | 기타비유동자산 | Other non-current assets | debit | | NoncurrentAssets | |

---

## 재무상태표 (BS) — 부채

### 유동부채

| ID | 계정과목명 | 영문명 | Balance | Abstract | 상위계정 | 비고 |
|----|-----------|--------|---------|----------|---------|------|
| ifrs-full_Liabilities | 부채 | Liabilities | credit | ○ | — | 최상위 |
| ifrs-full_CurrentLiabilities | 유동부채 | Current liabilities | credit | ○ | Liabilities | |
| ifrs-full_TradeAndOtherCurrentPayables | 매입채무 및 기타유동채무 | Trade and other current payables | credit | | CurrentLiabilities | |
| ifrs-full_TradePayables | 매입채무 | Trade payables | credit | | TradeAndOtherCurrentPayables | |
| dart_AccruedExpenses | 미지급비용 | Accrued expenses | credit | | TradeAndOtherCurrentPayables | |
| dart_OtherPayables | 미지급금 | Other payables | credit | | TradeAndOtherCurrentPayables | |
| dart_AdvancesReceived | 선수금 | Advances received | credit | | CurrentLiabilities | |
| dart_UnearnedRevenues | 선수수익 | Unearned revenues | credit | | CurrentLiabilities | |
| ifrs-full_ContractLiabilities | 계약부채 | Contract liabilities | credit | | CurrentLiabilities | |
| ifrs-full_ShorttermBorrowings | 단기차입금 | Short-term borrowings | credit | | CurrentLiabilities | |
| ifrs-full_CurrentPortionOfLongtermBorrowings | 유동성장기부채 | Current portion of long-term borrowings | credit | | CurrentLiabilities | |
| ifrs-full_CurrentLeaseLiabilities | 유동 리스부채 | Current lease liabilities | credit | | CurrentLiabilities | |
| ifrs-full_CurrentTaxLiabilities | 당기법인세부채 | Current tax liabilities | credit | | CurrentLiabilities | |
| ifrs-full_CurrentProvisions | 유동충당부채 | Current provisions | credit | | CurrentLiabilities | |
| ifrs-full_OtherCurrentLiabilities | 기타유동부채 | Other current liabilities | credit | | CurrentLiabilities | |
| dart_VATPayable | 부가세예수금 | VAT payable | credit | | CurrentLiabilities | |
| dart_WithholdingTaxPayable | 예수금(원천세) | Withholding tax payable | credit | | CurrentLiabilities | |
| dart_DividendsPayable | 미지급배당금 | Dividends payable | credit | | CurrentLiabilities | |

### 비유동부채

| ID | 계정과목명 | 영문명 | Balance | Abstract | 상위계정 | 비고 |
|----|-----------|--------|---------|----------|---------|------|
| ifrs-full_NoncurrentLiabilities | 비유동부채 | Non-current liabilities | credit | ○ | Liabilities | |
| ifrs-full_LongtermBorrowings | 장기차입금 | Long-term borrowings | credit | | NoncurrentLiabilities | |
| ifrs-full_BondsIssued | 사채 | Bonds issued | credit | | NoncurrentLiabilities | |
| dart_DiscountOnBondsPayable | 사채할인발행차금 | Discount on bonds payable | **debit** | | BondsIssued | ⚠️ **contra_liability** |
| ifrs-full_NoncurrentLeaseLiabilities | 비유동 리스부채 | Non-current lease liabilities | credit | | NoncurrentLiabilities | |
| ifrs-full_NoncurrentProvisions | 비유동충당부채 | Non-current provisions | credit | | NoncurrentLiabilities | |
| ifrs-full_DeferredTaxLiabilities | 이연법인세부채 | Deferred tax liabilities | credit | | NoncurrentLiabilities | |
| ifrs-full_NetDefinedBenefitLiability | 순확정급여부채 | Net defined benefit liability | credit | | NoncurrentLiabilities | |
| ifrs-full_OtherNoncurrentLiabilities | 기타비유동부채 | Other non-current liabilities | credit | | NoncurrentLiabilities | |

---

## 재무상태표 (BS) — 자본

| ID | 계정과목명 | 영문명 | Balance | Abstract | 상위계정 | 비고 |
|----|-----------|--------|---------|----------|---------|------|
| ifrs-full_Equity | 자본 | Equity | credit | ○ | — | 최상위 |
| ifrs-full_IssuedCapital | 자본금 | Issued capital | credit | | Equity | |
| ifrs-full_SharePremium | 주식발행초과금 | Share premium | credit | | Equity | |
| ifrs-full_RetainedEarnings | 이익잉여금 | Retained earnings | credit | | Equity | |
| ifrs-full_AccumulatedOtherComprehensiveIncome | 기타포괄손익누계액 | Accumulated OCI | credit | | Equity | |
| ifrs-full_OtherReserves | 기타자본항목 | Other reserves | credit | | Equity | |
| ifrs-full_TreasuryShares | 자기주식 | Treasury shares | **debit** | | OtherReserves | ⚠️ **contra_equity** |
| ifrs-full_NoncontrollingInterests | 비지배지분 | Non-controlling interests | credit | | Equity | |

---

## 손익계산서 (IS)

### 매출 및 매출원가

| ID | 계정과목명 | 영문명 | Balance | 상위계정 | 비고 |
|----|-----------|--------|---------|---------|------|
| ifrs-full_Revenue | 수익(매출액) | Revenue | credit | — | |
| dart_SalesOfGoods | 상품매출 | Sales of goods | credit | Revenue | |
| dart_SalesOfProducts | 제품매출 | Sales of products | credit | Revenue | |
| dart_ServiceRevenue | 용역매출 | Service revenue | credit | Revenue | |
| dart_SalesReturnsAndAllowances | 매출에누리와 환입 | Sales returns and allowances | **debit** | Revenue | ⚠️ **contra_revenue** |
| ifrs-full_CostOfSales | 매출원가 | Cost of sales | debit | — | |
| dart_CostOfGoodsSold | 상품매출원가 | Cost of goods sold | debit | CostOfSales | |
| dart_CostOfProductsSold | 제품매출원가 | Cost of products sold | debit | CostOfSales | |
| dart_InventoryValuationLoss | 재고자산평가손실 | Inventory valuation loss | debit | CostOfSales | |

### 판매비와관리비 (판관비)

| ID | 계정과목명 | Balance | 비고 |
|----|-----------|---------|------|
| ifrs-full_SellingGeneralAndAdministrativeExpense | 판매비와관리비 | debit | ○ Abstract |
| dart_SalariesExpense | 급여 | debit | |
| dart_RetirementBenefitExpense | 퇴직급여 | debit | |
| ifrs-full_DepreciationExpense | 감가상각비 | debit | |
| ifrs-full_AmortisationExpense | 무형자산상각비 | debit | |
| dart_RentExpense | 임차료 | debit | |
| dart_InsuranceExpense | 보험료 | debit | |
| dart_UtilitiesExpense | 수도광열비 | debit | |
| dart_AdvertisingExpense | 광고선전비 | debit | |
| dart_ResearchExpense | 경상연구개발비 | debit | |
| dart_BadDebtExpense | 대손상각비 | debit | |
| dart_TravelExpense | 여비교통비 | debit | |
| dart_CommunicationExpense | 통신비 | debit | |
| dart_SuppliesExpense | 소모품비 | debit | |
| dart_TaxesAndDues | 세금과공과 | debit | |
| dart_EntertainmentExpense | 접대비 | debit | |
| dart_FreightOutExpense | 운반비 | debit | |
| dart_ProfessionalFees | 지급수수료 | debit | |

### 영업외손익

| ID | 계정과목명 | Balance | 분류 |
|----|-----------|---------|------|
| ifrs-full_FinanceIncome | 금융수익 | credit | 수익 |
| ifrs-full_InterestRevenueForFinancialAssetsNotAtFairValue | 이자수익 | credit | 수익 |
| dart_DividendIncome | 배당금수익 | credit | 수익 |
| dart_ForeignExchangeGain | 외환차익 | credit | 수익 |
| dart_ForeignCurrencyTranslationGain | 외화환산이익 | credit | 수익 |
| dart_GainOnValuationOfFVTPL | 당기손익-공정가치 금융자산 평가이익 | credit | 수익 |
| dart_GainOnDisposalOfFVTPL | 당기손익-공정가치 금융자산 처분이익 | credit | 수익 |
| ifrs-full_FinanceCosts | 금융비용 | debit | 비용 |
| ifrs-full_InterestExpense | 이자비용 | debit | 비용 |
| dart_ForeignExchangeLoss | 외환차손 | debit | 비용 |
| dart_ForeignCurrencyTranslationLoss | 외화환산손실 | debit | 비용 |
| dart_LossOnValuationOfFVTPL | 당기손익-공정가치 금융자산 평가손실 | debit | 비용 |
| dart_LossOnDisposalOfFVTPL | 당기손익-공정가치 금융자산 처분손실 | debit | 비용 |
| ifrs-full_OtherIncome | 기타수익 | credit | 수익 |
| ifrs-full_GainOnDisposalOfPropertyPlantAndEquipment | 유형자산처분이익 | credit | 수익 |
| dart_GainOnDisposalOfIntangibleAssets | 무형자산처분이익 | credit | 수익 |
| dart_ReversalOfImpairmentLoss | 손상차손환입 | credit | 수익 |
| dart_ReversalOfAllowanceForDoubtfulAccounts | 대손충당금환입 | credit | 수익 |
| ifrs-full_GainsLossesOnDisposalsOfInvestmentProperties | 투자부동산처분손익 | credit | 수익 |
| ifrs-full_OtherExpense | 기타비용 | debit | 비용 |
| ifrs-full_LossOnDisposalOfPropertyPlantAndEquipment | 유형자산처분손실 | debit | 비용 |
| ifrs-full_ImpairmentLoss | 손상차손 | debit | 비용 |
| dart_DonationExpense | 기부금 | debit | 비용 |
| ifrs-full_ShareOfProfitLossOfAssociatesAccountedForUsingEquityMethod | 지분법이익(손실) | credit | 수익 |

### 법인세 및 당기순이익

| ID | 계정과목명 | Balance | 비고 |
|----|-----------|---------|------|
| ifrs-full_GrossProfit | 매출총이익 | credit | 소계 |
| ifrs-full_OperatingProfit | 영업이익 | credit | 소계 |
| ifrs-full_ProfitLossBeforeTax | 법인세비용차감전순이익 | credit | 소계 |
| ifrs-full_IncomeTaxExpenseContinuingOperations | 법인세비용 | debit | |
| ifrs-full_ProfitLoss | 당기순이익(손실) | credit | 소계 |

### 제조원가 관련

| ID | 계정과목명 | Balance |
|----|-----------|---------|
| dart_WagesAndSalariesManufacturing | 급여(제조) | debit |
| dart_DepreciationManufacturing | 감가상각비(제조) | debit |
| dart_RawMaterialsUsed | 원재료 사용액 | debit |

---

## 포괄손익계산서 (CIS)

| ID | 계정과목명 | Balance | Abstract |
|----|-----------|---------|----------|
| ifrs-full_OtherComprehensiveIncome | 기타포괄손익 | credit | ○ |
| ifrs-full_OtherComprehensiveIncomeNetOfTaxGainsLossesOnRevaluationOfPropertyPlantAndEquipment | 유형자산 재평가손익 | credit | |
| ifrs-full_OtherComprehensiveIncomeNetOfTaxExchangeDifferencesOnTranslation | 해외사업장 환산외환차이 | credit | |
| ifrs-full_OtherComprehensiveIncomeNetOfTaxGainsLossesOnRemeasurementsOfDefinedBenefitPlans | 확정급여제도 재측정손익 | credit | |
| ifrs-full_TotalComprehensiveIncome | 총포괄손익 | credit | 소계 |

---

## Contra(차감) 계정 요약

| 계정 | 원래 분류 | Balance | 설명 |
|------|----------|---------|------|
| 매출채권 대손충당금 | contra_asset | **credit** | 자산 차감 |
| 재고자산평가충당금 | contra_asset | **credit** | 자산 차감 |
| 유형자산 감가상각누계액 | contra_asset | **credit** | 자산 차감 |
| 사채할인발행차금 | contra_liability | **debit** | 부채 차감 |
| 자기주식 | contra_equity | **debit** | 자본 차감 |
| 매출에누리와 환입 | contra_revenue | **debit** | 수익 차감 |
