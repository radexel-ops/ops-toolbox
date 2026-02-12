# SW팀 Team Guidelines

> **이 문서는 SW팀의 AI 지침입니다. Master CLAUDE.md와 함께 AI 프롬프트에 병합됩니다.**

---

## 팀 소개

SW팀은 제품 소프트웨어 개발 및 유지보수를 담당합니다.

### 주요 업무
- 제품 소프트웨어 개발
- 사내 시스템 개발
- 기술 부채 관리
- 배포 및 운영

---

## AI 에이전트 지침

### 우선순위
1. **품질**: 버그 없는 코드
2. **유지보수성**: 깔끔한 아키텍처
3. **성능**: 최적화된 실행

### 코딩 컨벤션

#### Python
```python
# Type hints 필수
def process_data(data: list[dict]) -> dict:
    """함수 설명은 docstring으로"""
    pass

# 클래스명은 PascalCase
class DataProcessor:
    pass

# 상수는 UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
```

#### TypeScript
```typescript
// Interface 정의 필수
interface UserData {
  id: number;
  name: string;
}

// 함수는 arrow function 권장
const processUser = (user: UserData): void => {
  // implementation
};
```

### 주요 자동화 업무

#### 1. 코드 리뷰
- PR 자동 분석
- 보안 취약점 검사
- 코딩 컨벤션 검사

#### 2. 문서화
- API 문서 자동 생성
- README 업데이트
- 변경 로그 작성

#### 3. 테스트
- 테스트 케이스 생성
- 커버리지 리포트
- 성능 테스트 결과 분석

---

## Git 워크플로우

```
main ← develop ← feature/xxx
             ↑
         hotfix/xxx
```

1. **feature 브랜치**: 새 기능 개발
2. **develop**: 통합 브랜치
3. **main**: 프로덕션 배포
4. **hotfix**: 긴급 버그 수정

---

## 코드 품질 기준

| 항목 | 기준 | 도구 |
|------|------|------|
| 커버리지 | ≥ 80% | pytest-cov |
| 린트 | 에러 0 | flake8, eslint |
| 타입 검사 | 통과 | mypy, tsc |
| 복잡도 | ≤ 10 | radon |

---

*Last Updated: 2026-02-10*
