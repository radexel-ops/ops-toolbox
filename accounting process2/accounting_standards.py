"""
회계기준 참조 및 정책 검증 엔진
================================
회사의 실무지침이 회계기준(K-GAAP, K-IFRS)에 부합하는지 검증합니다.

검증 유형:
1. MANDATORY (필수): 반드시 준수해야 하는 회계기준
2. RECOMMENDED (권장): 준수가 권장되는 모범 사례
3. DISCRETIONARY (재량): 회사가 선택할 수 있는 회계정책
4. STRATEGIC (전략적): 회사 전략에 따라 결정할 사항

대용량 지침 처리:
- 섹션별 청크 분할 검증
- 컨텍스트 유지를 위한 요약 전달
- 계층적 검증 (카테고리 → 세부항목)
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# AI 서비스 임포트
try:
    from ai_service import AccountingAI
    HAS_AI = True
except ImportError:
    HAS_AI = False

from config import SCRIPT_DIR


class RuleType(Enum):
    """규칙 유형"""
    MANDATORY = "mandatory"      # 필수 준수 (위반 시 오류)
    RECOMMENDED = "recommended"  # 권장 사항 (미준수 시 경고)
    DISCRETIONARY = "discretionary"  # 회사 재량 (정보 제공)
    STRATEGIC = "strategic"      # 전략적 선택 (참고 사항)


class ValidationSeverity(Enum):
    """검증 결과 심각도"""
    ERROR = "error"        # 회계기준 위반 (빨강)
    WARNING = "warning"    # 권장사항 미준수 (주황)
    INFO = "info"          # 재량/전략적 선택 (파랑)
    PASS = "pass"          # 적합 (녹색)


@dataclass
class ValidationResult:
    """검증 결과"""
    section: str              # 검증 섹션
    rule_type: RuleType       # 규칙 유형
    severity: ValidationSeverity  # 심각도
    title: str                # 제목
    message: str              # 상세 메시지
    standard_ref: str         # 회계기준 참조 (예: "K-GAAP 제5장")
    suggestion: str           # 개선 제안
    is_company_choice: bool   # 회사 재량 여부


# ==========================================
# 회계기준 참조 데이터
# ==========================================
# 중소기업회계기준 (K-GAAP for SMEs) 핵심 규정

ACCOUNTING_STANDARDS = {
    "_metadata": {
        "version": "1.0.0",
        "base_standard": "중소기업회계기준",
        "effective_date": "2024-01-01",
        "description": "중소기업회계기준 핵심 규정 및 검증 룰"
    },

    # ==========================================
    # 자산 인식 기준
    # ==========================================
    "asset_recognition": {
        "title": "자산 인식 기준",
        "standard_ref": "중소기업회계기준 제5장",
        "rules": [
            {
                "id": "AR001",
                "type": "mandatory",
                "description": "자산은 미래 경제적 효익이 기업에 유입될 가능성이 높고, 원가를 신뢰성 있게 측정할 수 있을 때 인식",
                "check_points": ["미래효익_유입가능성", "원가_신뢰성측정"],
                "violation_example": "단순 수선유지비를 자산으로 인식"
            },
            {
                "id": "AR002",
                "type": "discretionary",
                "description": "자본화 기준금액은 회사가 정할 수 있음 (일반적으로 100만원~500만원)",
                "check_points": ["자본화_기준금액"],
                "typical_range": {"min": 500000, "max": 5000000},
                "note": "업종, 규모에 따라 합리적으로 설정"
            }
        ]
    },

    # ==========================================
    # 유형자산
    # ==========================================
    "tangible_assets": {
        "title": "유형자산",
        "standard_ref": "중소기업회계기준 제10장",
        "rules": [
            {
                "id": "TA001",
                "type": "mandatory",
                "description": "유형자산은 물리적 형체가 있고, 1년 이상 사용할 목적으로 보유하는 자산",
                "check_points": ["물리적형체", "사용기간_1년이상"]
            },
            {
                "id": "TA002",
                "type": "mandatory",
                "description": "취득원가 = 구입가격 + 취득부대비용 + 설치비용",
                "check_points": ["취득원가_구성"]
            },
            {
                "id": "TA003",
                "type": "discretionary",
                "description": "감가상각방법 선택 (정액법, 정률법, 생산량비례법 등)",
                "check_points": ["감가상각방법"],
                "options": ["정액법", "정률법", "생산량비례법"],
                "note": "자산의 경제적 효익 소비 패턴에 따라 선택"
            },
            {
                "id": "TA004",
                "type": "discretionary",
                "description": "내용연수는 자산별로 합리적으로 추정",
                "check_points": ["내용연수"],
                "typical_ranges": {
                    "기계장치": {"min": 5, "max": 15},
                    "차량운반구": {"min": 4, "max": 6},
                    "비품": {"min": 4, "max": 10},
                    "구축물": {"min": 10, "max": 40}
                },
                "note": "세법상 내용연수를 참고하되, 실제 사용기간 고려"
            },
            {
                "id": "TA005",
                "type": "recommended",
                "description": "후속원가 중 자산의 미래 경제적효익을 증가시키는 지출은 자본화",
                "check_points": ["후속원가_자본화기준"],
                "note": "단순 수선유지는 비용처리"
            }
        ]
    },

    # ==========================================
    # 무형자산
    # ==========================================
    "intangible_assets": {
        "title": "무형자산",
        "standard_ref": "중소기업회계기준 제11장",
        "rules": [
            {
                "id": "IA001",
                "type": "mandatory",
                "description": "무형자산은 식별가능하고, 기업이 통제하며, 미래경제적효익이 있어야 함",
                "check_points": ["식별가능성", "통제", "미래경제적효익"]
            },
            {
                "id": "IA002",
                "type": "mandatory",
                "description": "개발비 자산화 5요건을 모두 충족해야 무형자산 인식",
                "check_points": ["개발비_5요건"],
                "requirements": [
                    "기술적 실현가능성",
                    "완성하여 사용·판매 의도",
                    "사용·판매 능력",
                    "미래경제적효익 창출 방법",
                    "개발완료 자원의 충분성"
                ]
            },
            {
                "id": "IA003",
                "type": "mandatory",
                "description": "연구단계 지출은 발생시점에 비용 처리",
                "check_points": ["연구비_비용처리"]
            },
            {
                "id": "IA004",
                "type": "discretionary",
                "description": "무형자산 내용연수 (유한/비한정)",
                "check_points": ["무형자산_내용연수"],
                "typical_ranges": {
                    "특허권": {"min": 5, "max": 20},
                    "소프트웨어": {"min": 3, "max": 10},
                    "개발비": {"min": 3, "max": 10}
                }
            }
        ]
    },

    # ==========================================
    # 재고자산
    # ==========================================
    "inventory": {
        "title": "재고자산",
        "standard_ref": "중소기업회계기준 제7장",
        "rules": [
            {
                "id": "INV001",
                "type": "mandatory",
                "description": "재고자산은 취득원가와 순실현가능가치 중 낮은 금액으로 측정",
                "check_points": ["저가법_적용"]
            },
            {
                "id": "INV002",
                "type": "discretionary",
                "description": "원가흐름 가정 선택 (선입선출법, 가중평균법 등)",
                "check_points": ["원가흐름가정"],
                "options": ["선입선출법", "가중평균법", "개별법"],
                "note": "일관성 있게 적용해야 함"
            }
        ]
    },

    # ==========================================
    # 수익 인식
    # ==========================================
    "revenue_recognition": {
        "title": "수익 인식",
        "standard_ref": "중소기업회계기준 제16장",
        "rules": [
            {
                "id": "RR001",
                "type": "mandatory",
                "description": "수익은 재화의 소유에 따른 위험과 보상이 이전될 때 인식",
                "check_points": ["수익인식시점"]
            }
        ]
    },

    # ==========================================
    # 회계정책 일관성
    # ==========================================
    "consistency": {
        "title": "회계정책 일관성",
        "standard_ref": "중소기업회계기준 제3장",
        "rules": [
            {
                "id": "CON001",
                "type": "mandatory",
                "description": "회계정책은 매기 일관성 있게 적용해야 함",
                "check_points": ["회계정책_일관성"]
            },
            {
                "id": "CON002",
                "type": "mandatory",
                "description": "회계정책 변경 시 비교재무제표 재작성 또는 주석 공시",
                "check_points": ["회계정책변경_공시"]
            }
        ]
    },

    # ==========================================
    # 의료기기/R&D 특수 사항
    # ==========================================
    "medical_device_rd": {
        "title": "의료기기/R&D 특수사항",
        "standard_ref": "업종별 회계처리 지침",
        "rules": [
            {
                "id": "MD001",
                "type": "recommended",
                "description": "의료기기 인허가 비용은 개발비 요건 충족 시 자산화 가능",
                "check_points": ["인허가비용_처리"],
                "note": "식약처 허가 관련 직접비용"
            },
            {
                "id": "MD002",
                "type": "strategic",
                "description": "임상시험 비용의 자산화 여부는 상업화 가능성에 따라 판단",
                "check_points": ["임상시험비용"],
                "note": "보수주의 관점에서 비용처리가 일반적"
            },
            {
                "id": "MD003",
                "type": "discretionary",
                "description": "시제품 제작비용의 자산화/비용화 선택",
                "check_points": ["시제품비용"],
                "options": ["자산화 (개발비)", "비용화 (경상연구개발비)"],
                "note": "상업화 단계와 재사용 가능성 고려"
            }
        ]
    }
}


class PolicyValidator:
    """
    회계정책 검증기

    대용량 지침 파일을 섹션별로 나누어 검증하고,
    AI를 활용하여 맥락을 이해한 심층 검증을 수행합니다.
    """

    def __init__(self, ai_model: str = None):
        """
        Args:
            ai_model: 사용할 AI 모델명 (None이면 기본 모델)
        """
        self.standards = ACCOUNTING_STANDARDS
        self.ai = None
        if HAS_AI:
            try:
                from ai_service import AccountingAI
                self.ai = AccountingAI(ai_model)
            except Exception as e:
                print(f"AI 초기화 실패: {e}")

    def validate_guidelines(self, guidelines: Dict,
                           sections: List[str] = None,
                           deep_check: bool = True) -> List[ValidationResult]:
        """
        실무지침 전체 검증

        Args:
            guidelines: 실무지침 데이터
            sections: 검증할 섹션 목록 (None이면 전체)
            deep_check: AI를 사용한 심층 검증 여부

        Returns:
            List[ValidationResult]: 검증 결과 목록
        """
        results = []

        # 1. 회사 프로필 검증
        if not sections or "company_profile" in sections:
            results.extend(self._validate_company_profile(guidelines))

        # 2. 분류 카테고리 검증
        if not sections or "classification_categories" in sections:
            results.extend(self._validate_categories(guidelines))

        # 3. 의사결정 트리 검증 (섹션별 청크)
        if not sections or "master_decision_tree" in sections:
            results.extend(self._validate_decision_tree(guidelines))

        # 4. AI 심층 검증 (선택적)
        if deep_check and self.ai:
            results.extend(self._ai_deep_validation(guidelines, sections))

        return results

    def validate_changes(self, old_guidelines: Dict, new_guidelines: Dict) -> List[ValidationResult]:
        """
        변경된 부분만 검증 (YAML 수정 감지 시 사용)

        Args:
            old_guidelines: 이전 지침
            new_guidelines: 새 지침

        Returns:
            List[ValidationResult]: 변경 부분 검증 결과
        """
        results = []
        changes = self._detect_changes(old_guidelines, new_guidelines)

        if not changes:
            results.append(ValidationResult(
                section="변경사항",
                rule_type=RuleType.DISCRETIONARY,
                severity=ValidationSeverity.INFO,
                title="변경사항 없음",
                message="이전 버전과 동일합니다.",
                standard_ref="",
                suggestion="",
                is_company_choice=False
            ))
            return results

        # 변경된 섹션만 검증
        for change in changes:
            section_results = self._validate_single_change(change, new_guidelines)
            results.extend(section_results)

        return results

    def _validate_company_profile(self, guidelines: Dict) -> List[ValidationResult]:
        """회사 프로필 검증"""
        results = []
        profile = guidelines.get("company_profile", {})

        # 자본화 기준금액 검증
        threshold = profile.get("자본화_기준금액", 0)
        ar002 = self._get_rule("asset_recognition", "AR002")

        if ar002:
            typical = ar002.get("typical_range", {})
            min_val = typical.get("min", 500000)
            max_val = typical.get("max", 5000000)

            if threshold < min_val:
                results.append(ValidationResult(
                    section="회사 프로필",
                    rule_type=RuleType.DISCRETIONARY,
                    severity=ValidationSeverity.INFO,
                    title="자본화 기준금액이 낮음",
                    message=f"현재 설정: {threshold:,}원. 일반적 범위: {min_val:,}~{max_val:,}원",
                    standard_ref="중소기업회계기준 제5장",
                    suggestion="자산 관리 부담이 증가할 수 있습니다. 회사 상황에 맞게 설정하세요.",
                    is_company_choice=True
                ))
            elif threshold > max_val:
                results.append(ValidationResult(
                    section="회사 프로필",
                    rule_type=RuleType.RECOMMENDED,
                    severity=ValidationSeverity.WARNING,
                    title="자본화 기준금액이 높음",
                    message=f"현재 설정: {threshold:,}원. 일반적 범위: {min_val:,}~{max_val:,}원",
                    standard_ref="중소기업회계기준 제5장",
                    suggestion="고가 자산이 비용처리되어 재무제표 왜곡 가능성이 있습니다.",
                    is_company_choice=True
                ))
            else:
                results.append(ValidationResult(
                    section="회사 프로필",
                    rule_type=RuleType.DISCRETIONARY,
                    severity=ValidationSeverity.PASS,
                    title="자본화 기준금액 적정",
                    message=f"현재 설정: {threshold:,}원 - 일반적 범위 내",
                    standard_ref="중소기업회계기준 제5장",
                    suggestion="",
                    is_company_choice=True
                ))

        # 감가상각방법 검증
        policy = profile.get("자본화_정책", {})
        depreciation_method = policy.get("감가상각방법", "")

        ta003 = self._get_rule("tangible_assets", "TA003")
        if ta003 and depreciation_method:
            valid_methods = ta003.get("options", [])
            if depreciation_method in valid_methods:
                results.append(ValidationResult(
                    section="회사 프로필",
                    rule_type=RuleType.DISCRETIONARY,
                    severity=ValidationSeverity.PASS,
                    title="감가상각방법 적정",
                    message=f"'{depreciation_method}' 사용 - 회계기준상 인정되는 방법",
                    standard_ref="중소기업회계기준 제10장",
                    suggestion="자산의 경제적효익 소비패턴과 일치하는지 주기적으로 검토하세요.",
                    is_company_choice=True
                ))

        # 내용연수 검증
        useful_life = policy.get("내용연수", {})
        ta004 = self._get_rule("tangible_assets", "TA004")

        if ta004 and useful_life:
            typical_ranges = ta004.get("typical_ranges", {})
            for asset_type, years in useful_life.items():
                try:
                    years_int = int(years.replace("년", ""))
                    if asset_type in typical_ranges:
                        range_info = typical_ranges[asset_type]
                        min_years = range_info.get("min", 1)
                        max_years = range_info.get("max", 50)

                        if years_int < min_years or years_int > max_years:
                            results.append(ValidationResult(
                                section="회사 프로필",
                                rule_type=RuleType.RECOMMENDED,
                                severity=ValidationSeverity.WARNING,
                                title=f"{asset_type} 내용연수 검토 필요",
                                message=f"현재: {years_int}년, 일반 범위: {min_years}~{max_years}년",
                                standard_ref="중소기업회계기준 제10장",
                                suggestion="세법상 내용연수 및 실제 사용기간을 고려하여 재검토하세요.",
                                is_company_choice=True
                            ))
                except (ValueError, AttributeError):
                    pass

        return results

    def _validate_categories(self, guidelines: Dict) -> List[ValidationResult]:
        """분류 카테고리 검증"""
        results = []
        categories = guidelines.get("classification_categories", {})

        # 필수 카테고리 존재 여부
        required_categories = ["1_유형자산", "2_건설중인자산", "3_무형자산", "4_기타"]
        for cat in required_categories:
            if cat not in categories:
                results.append(ValidationResult(
                    section="분류 카테고리",
                    rule_type=RuleType.MANDATORY,
                    severity=ValidationSeverity.ERROR,
                    title=f"필수 카테고리 누락: {cat}",
                    message="회계처리에 필요한 기본 카테고리가 없습니다.",
                    standard_ref="중소기업회계기준",
                    suggestion=f"'{cat}' 카테고리를 추가하세요.",
                    is_company_choice=False
                ))

        return results

    def _validate_decision_tree(self, guidelines: Dict) -> List[ValidationResult]:
        """의사결정 트리 검증 (섹션별 청크 처리)"""
        results = []
        tree = guidelines.get("master_decision_tree", {})

        if not tree:
            results.append(ValidationResult(
                section="의사결정 트리",
                rule_type=RuleType.MANDATORY,
                severity=ValidationSeverity.ERROR,
                title="의사결정 트리 없음",
                message="분류를 위한 의사결정 트리가 정의되지 않았습니다.",
                standard_ref="",
                suggestion="master_decision_tree 섹션을 추가하세요.",
                is_company_choice=False
            ))
            return results

        # 개발비 5요건 검증
        step4b = tree.get("STEP4B_무형자산분류", {})
        dev_cost_check = step4b.get("개발비_검토", {})
        requirements = dev_cost_check.get("5요건", [])

        ia002 = self._get_rule("intangible_assets", "IA002")
        if ia002:
            required_reqs = ia002.get("requirements", [])
            if len(requirements) < len(required_reqs):
                results.append(ValidationResult(
                    section="의사결정 트리 - 개발비",
                    rule_type=RuleType.MANDATORY,
                    severity=ValidationSeverity.WARNING,
                    title="개발비 자산화 요건 확인 필요",
                    message=f"현재 {len(requirements)}개 요건 정의됨. 표준: {len(required_reqs)}개",
                    standard_ref="중소기업회계기준 제11장",
                    suggestion="개발비 자산화 5요건이 모두 포함되어 있는지 확인하세요.",
                    is_company_choice=False
                ))
            else:
                results.append(ValidationResult(
                    section="의사결정 트리 - 개발비",
                    rule_type=RuleType.MANDATORY,
                    severity=ValidationSeverity.PASS,
                    title="개발비 자산화 요건 적정",
                    message="개발비 5요건이 올바르게 정의되어 있습니다.",
                    standard_ref="중소기업회계기준 제11장",
                    suggestion="",
                    is_company_choice=False
                ))

        return results

    def _ai_deep_validation(self, guidelines: Dict,
                           sections: List[str] = None) -> List[ValidationResult]:
        """
        AI를 활용한 심층 검증

        대용량 지침을 처리하기 위해:
        1. 섹션별로 분할
        2. 각 섹션에 대해 관련 회계기준과 함께 AI에 전달
        3. 컨텍스트 요약을 포함하여 맥락 유지
        """
        results = []

        if not self.ai:
            return results

        # 컨텍스트 요약 생성
        context_summary = self._create_context_summary(guidelines)

        # 검증할 섹션 목록
        sections_to_check = sections or [
            "company_profile",
            "classification_categories",
            "master_decision_tree"
        ]

        for section_name in sections_to_check:
            section_data = guidelines.get(section_name, {})
            if not section_data:
                continue

            # 섹션이 너무 크면 하위 항목별로 분할
            if self._is_large_section(section_data):
                sub_results = self._validate_large_section_chunked(
                    section_name, section_data, context_summary
                )
                results.extend(sub_results)
            else:
                sub_results = self._validate_section_with_ai(
                    section_name, section_data, context_summary
                )
                results.extend(sub_results)

        return results

    def _create_context_summary(self, guidelines: Dict) -> str:
        """전체 지침의 컨텍스트 요약 생성"""
        profile = guidelines.get("company_profile", {})

        summary = f"""[회사 회계정책 요약]
- 회계기준: {profile.get('회계기준', '알 수 없음')}
- 업종: {profile.get('업종', '알 수 없음')}
- 자본화 기준: {profile.get('자본화_기준금액', 0):,}원
- 감가상각: {profile.get('자본화_정책', {}).get('감가상각방법', '알 수 없음')}
- 회계방향: {profile.get('회계방향', {}).get('기본원칙', '알 수 없음')}
"""
        return summary

    def _is_large_section(self, section_data: Dict, threshold: int = 5000) -> bool:
        """섹션이 큰지 확인 (JSON 문자열 길이 기준)"""
        return len(json.dumps(section_data, ensure_ascii=False)) > threshold

    def _validate_large_section_chunked(self, section_name: str,
                                        section_data: Dict,
                                        context_summary: str) -> List[ValidationResult]:
        """대용량 섹션을 청크로 나누어 검증"""
        results = []

        # 딕셔너리의 각 키를 하위 섹션으로 분할
        for sub_key, sub_data in section_data.items():
            sub_results = self._validate_section_with_ai(
                f"{section_name}.{sub_key}",
                sub_data,
                context_summary
            )
            results.extend(sub_results)

        return results

    def _validate_section_with_ai(self, section_name: str,
                                  section_data: Dict,
                                  context_summary: str) -> List[ValidationResult]:
        """AI를 사용하여 개별 섹션 검증"""
        results = []

        if not self.ai:
            return results

        # 관련 회계기준 찾기
        relevant_standards = self._get_relevant_standards(section_name)

        prompt = f"""당신은 대한민국 회계기준 전문가입니다.
아래 회사의 회계정책 섹션이 회계기준에 부합하는지 검증해주세요.

{context_summary}

[검증 대상 섹션: {section_name}]
```json
{json.dumps(section_data, ensure_ascii=False, indent=2)[:3000]}
```

[관련 회계기준]
{relevant_standards}

[검증 지침]
1. 필수 준수 사항(MANDATORY) 위반 여부 확인
2. 권장 사항(RECOMMENDED) 준수 여부 확인
3. 회사 재량(DISCRETIONARY) 사항은 적정성만 검토
4. 업종 특성(의료기기/R&D) 고려

[출력 형식 - JSON]
{{
    "findings": [
        {{
            "type": "mandatory|recommended|discretionary|strategic",
            "severity": "error|warning|info|pass",
            "title": "검증 결과 제목",
            "message": "상세 설명",
            "standard_ref": "관련 회계기준 (예: 중소기업회계기준 제10장)",
            "suggestion": "개선 제안 (있는 경우)",
            "is_company_choice": true|false
        }}
    ],
    "overall_assessment": "전체 평가 요약"
}}
"""

        try:
            response = self.ai.analyze(prompt, history=[])

            if response.get("status") != "ERROR":
                findings = response.get("findings", [])
                for finding in findings:
                    results.append(ValidationResult(
                        section=section_name,
                        rule_type=RuleType(finding.get("type", "discretionary")),
                        severity=ValidationSeverity(finding.get("severity", "info")),
                        title=finding.get("title", "검증 결과"),
                        message=finding.get("message", ""),
                        standard_ref=finding.get("standard_ref", ""),
                        suggestion=finding.get("suggestion", ""),
                        is_company_choice=finding.get("is_company_choice", False)
                    ))
        except Exception as e:
            print(f"AI 검증 오류 ({section_name}): {e}")

        return results

    def _get_relevant_standards(self, section_name: str) -> str:
        """섹션에 관련된 회계기준 추출"""
        relevant = []

        section_mapping = {
            "company_profile": ["asset_recognition", "consistency"],
            "classification_categories": ["tangible_assets", "intangible_assets"],
            "master_decision_tree": ["tangible_assets", "intangible_assets", "inventory", "medical_device_rd"],
            "STEP4A": ["tangible_assets"],
            "STEP4B": ["intangible_assets"],
            "개발": ["intangible_assets", "medical_device_rd"]
        }

        for key, categories in section_mapping.items():
            if key.lower() in section_name.lower():
                for cat in categories:
                    if cat in self.standards:
                        cat_data = self.standards[cat]
                        relevant.append(f"[{cat_data.get('title', cat)}]")
                        relevant.append(f"참조: {cat_data.get('standard_ref', '')}")
                        for rule in cat_data.get("rules", [])[:3]:  # 상위 3개 규칙만
                            relevant.append(f"- {rule.get('description', '')}")
                        relevant.append("")

        return "\n".join(relevant) if relevant else "일반 회계기준 적용"

    def _get_rule(self, category: str, rule_id: str) -> Optional[Dict]:
        """특정 규칙 조회"""
        cat_data = self.standards.get(category, {})
        for rule in cat_data.get("rules", []):
            if rule.get("id") == rule_id:
                return rule
        return None

    def _detect_changes(self, old: Dict, new: Dict, path: str = "") -> List[Dict]:
        """두 딕셔너리 간 변경사항 감지"""
        changes = []

        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key

            if key not in old:
                changes.append({"path": current_path, "type": "added", "value": new[key]})
            elif key not in new:
                changes.append({"path": current_path, "type": "removed", "value": old[key]})
            elif old[key] != new[key]:
                if isinstance(old[key], dict) and isinstance(new[key], dict):
                    changes.extend(self._detect_changes(old[key], new[key], current_path))
                else:
                    changes.append({
                        "path": current_path,
                        "type": "modified",
                        "old_value": old[key],
                        "new_value": new[key]
                    })

        return changes

    def _validate_single_change(self, change: Dict, guidelines: Dict) -> List[ValidationResult]:
        """단일 변경사항 검증"""
        results = []
        path = change.get("path", "")
        change_type = change.get("type", "")

        # 변경 유형에 따른 기본 결과
        if change_type == "added":
            results.append(ValidationResult(
                section=path,
                rule_type=RuleType.DISCRETIONARY,
                severity=ValidationSeverity.INFO,
                title="항목 추가됨",
                message=f"새로운 항목이 추가되었습니다.",
                standard_ref="",
                suggestion="추가된 항목이 회계기준에 부합하는지 확인하세요.",
                is_company_choice=True
            ))
        elif change_type == "removed":
            results.append(ValidationResult(
                section=path,
                rule_type=RuleType.RECOMMENDED,
                severity=ValidationSeverity.WARNING,
                title="항목 삭제됨",
                message=f"기존 항목이 삭제되었습니다.",
                standard_ref="",
                suggestion="삭제로 인해 분류에 영향이 없는지 확인하세요.",
                is_company_choice=True
            ))
        elif change_type == "modified":
            results.append(ValidationResult(
                section=path,
                rule_type=RuleType.DISCRETIONARY,
                severity=ValidationSeverity.INFO,
                title="항목 수정됨",
                message=f"값이 변경되었습니다: {change.get('old_value')} → {change.get('new_value')}",
                standard_ref="",
                suggestion="변경이 회계기준과 일관성을 유지하는지 확인하세요.",
                is_company_choice=True
            ))

        return results


def format_validation_results(results: List[ValidationResult]) -> Dict:
    """
    검증 결과를 UI 표시용으로 포맷팅

    Returns:
        Dict: 심각도별 그룹화된 결과
    """
    formatted = {
        "errors": [],      # 필수 위반 (빨강)
        "warnings": [],    # 권장사항 미준수 (주황)
        "info": [],        # 재량/전략적 (파랑)
        "passed": [],      # 적합 (녹색)
        "summary": {
            "total": len(results),
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "passed": 0
        }
    }

    for result in results:
        item = {
            "section": result.section,
            "title": result.title,
            "message": result.message,
            "standard_ref": result.standard_ref,
            "suggestion": result.suggestion,
            "is_company_choice": result.is_company_choice,
            "rule_type": result.rule_type.value
        }

        if result.severity == ValidationSeverity.ERROR:
            formatted["errors"].append(item)
            formatted["summary"]["errors"] += 1
        elif result.severity == ValidationSeverity.WARNING:
            formatted["warnings"].append(item)
            formatted["summary"]["warnings"] += 1
        elif result.severity == ValidationSeverity.INFO:
            formatted["info"].append(item)
            formatted["summary"]["info"] += 1
        else:
            formatted["passed"].append(item)
            formatted["summary"]["passed"] += 1

    return formatted
