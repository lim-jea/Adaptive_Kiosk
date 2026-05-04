# 백엔드 코드 검토 로그

> 검토 계획: [00_REVIEW_PLAN.md](./00_REVIEW_PLAN.md)
> 변경 요청: [02_CHANGE_REQUESTS.md](./02_CHANGE_REQUESTS.md)
> 일자별 작업 로그: [08_TODAY_WORKLOG_2026-05-05.md](./08_TODAY_WORKLOG_2026-05-05.md)
> backend 적용 가이드: [09_BACKEND_INTEGRATION_PLAN.md](./09_BACKEND_INTEGRATION_PLAN.md)

각 단위 검토는 아래 템플릿 형식으로 누적 기록한다.

---

## 작성 템플릿

```markdown
## [Phase X.Y] <대상 파일/모듈>

- **검토일**: YYYY-MM-DD
- **검토 범위**: <어디부터 어디까지>
- **요약**: 한 줄 결론.

### 확인 사항 (정상)
- ...

### 의문 / 결정 필요
- (Q1) ...
  - (A1) ...

### 수정 제안
- [ ] 즉시: <간단 정리>
- [ ] 보류 → CHANGE-### : <큰 변경>

### 사용자 Q&A
- **Q.** ...
- **A.** ...

### 결과
- 즉시 적용한 항목: ...
- CHANGE_REQUESTS로 이동한 항목: ...
- 다음 단계 영향: ...
```

---

# Phase 1 — 공통 인프라

> 오늘 목표: 1.1 ~ 1.8 완료.

## [Phase 1.1] backend/main.py

(검토 진행 시 기록)

---

## [Phase 1.2] backend/core/config.py

(검토 진행 시 기록)

---

## [Phase 1.3] backend/core/database.py

(검토 진행 시 기록)

---

## [Phase 1.4] backend/core/security.py

(검토 진행 시 기록)

---

## [Phase 1.5] backend/core/enums.py

(검토 진행 시 기록)

---

## [Phase 1.6] backend/model.py

(검토 진행 시 기록)

---

## [Phase 1.7] backend/schemas.py

(검토 진행 시 기록)

---

## [Phase 1.8] backend/api/v1/router.py

(검토 진행 시 기록)

---

# Phase 2 — 도메인별 (다음 세션)

> 진행 시 단위마다 위 템플릿 복제해서 추가.

## [Phase 2.1] Kiosk

## [Phase 2.2] Session

## [Phase 2.3] Menu

## [Phase 2.4] Option

## [Phase 2.5] Cart

## [Phase 2.6] Order

## [Phase 2.7] Analytics

## [Phase 2.8] Recommendation

## [Phase 2.9] Vision / Face

## [Phase 2.10] Voice / Chat

## [Phase 2.11] Trend

## [Phase 2.12] Logs
