# LeadFlow 개발 규칙

## 구조

- `apps/web`: 직원용 앱. `apps/admin`: 관리자 앱. `apps/api`: FastAPI 서버.
- `packages/ui`: 디자인 토큰·공통 컴포넌트. `packages/crm`: 공통 CRM 화면. `packages/api-client`: API 계약·요청.
- 구현 전에 `docs/product-spec.md`, `docs/design-system.md`를 확인한다.

## 디자인 하네스

- 화면 색상은 `packages/ui/src/theme.css`의 의미 기반 토큰에서 가져온다.
- 앱/기능 컴포넌트에 hex/rgb/hsl 색상, 임의 Tailwind 색상, inline style을 추가하지 않는다.
- 공통 버튼·배지·필드·빈 상태를 재사용한다. 신규 패턴은 공통 UI에 먼저 정의한다.
- 입력에는 label, 비동기 작업에는 pending/error/empty/success 상태를 제공한다.
- 키보드 포커스를 보존하고 작은 화면에서 고객 상세를 전체 폭으로 보여준다.
- UI 변경 후 `pnpm check`, `pnpm build`, 관련 `pnpm test:e2e`를 실행한다.

## 데이터·보안

- 직원 접근 제한은 API의 현재 담당자 검사로 적용한다. UI 분기는 보안 경계가 아니다.
- 비활성/퇴사 계정은 기존 세션까지 차단한다. 과거 작성자·이력은 남긴다.
- 현재 상태 변경과 이력 생성은 같은 DB 트랜잭션에서 처리한다.
- 수정 충돌은 version으로 검출한다. 실패한 mutation을 자동 재시도하지 않는다.
- 날짜는 UTC 저장, Asia/Seoul 표시. naive datetime을 API에 보내지 않는다.
- 인증 정보·고객 개인정보를 로그나 Git에 넣지 않는다. 테스트 데이터는 합성 데이터만 사용한다.
- 카카오 활동은 직원의 수동 전달 기록이다. 실제 전송 성공처럼 표시하지 않는다.

## 검증·배포

- `pnpm verify`가 통합 진입점이다. 배포 전 PostgreSQL 마이그레이션과 백업 복원도 확인한다.
- DB 변경은 Alembic migration으로 관리한다. 운영 시작 시 create_all 금지.
- 배포와 장애 복구 절차는 `docs/deployment.md`에 유지한다.
- 테스트 실패를 우회하거나 검증하지 않은 배포 성공을 주장하지 않는다.
