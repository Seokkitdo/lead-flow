# LeadFlow 구현 계획

원본 요구사항: [product-spec.md](product-spec.md)

## 이번 구현 범위

- [x] pnpm 모노레포: 직원 웹, 관리자 웹, Python API, 공통 UI와 API 계약
- [x] 인증·재직 상태·서버 접근 통제, 고객 CRUD와 중복 확인
- [x] 단일/일괄 균등 배분, 활동·상태·배분의 트랜잭션과 타임라인
- [x] 검색·필터·페이지네이션·대시보드·직원 관리
- [x] 디자인 토큰·공통 컴포넌트·개발 규칙·자동 검사
- [x] API 회귀 테스트·프론트 타입 검사·빌드·실제 사용자 흐름 검증
- [x] PostgreSQL 마이그레이션·Docker 배포 구성·CI·운영 가이드

## 결정 사항

- 한 조직의 내부 CRM을 전제로 한다. 조직별 테넌트 분리는 현재 요구 범위 밖이다.
- 웹과 어드민은 별도 빌드이며 같은 API와 공통 디자인 시스템을 사용한다.
- Svelte 5 + TanStack Svelte Query + Tailwind CSS 4, Python FastAPI + SQLAlchemy + Alembic.
- 운영 PostgreSQL, 로컬 빠른 실행과 단위 검증 SQLite. 두 DB의 API 회귀 테스트와 마이그레이션을 검증한다.
- 인증 세션은 서버 DB에 저장하고 HttpOnly 쿠키 사용. 프론트 저장소에 인증 토큰을 보관하지 않는다.
- 시간 저장 UTC, 업무 기준과 표시는 Asia/Seoul. 입력의 시간대를 명시한다.
- 배포 대상 미정: 특정 클라우드에 종속하지 않는 Docker Compose + Caddy TLS 진입점.
- 실서비스 배포, 도메인 연결, 운영 계정/개인정보 입력은 후속 작업.
- Excel·CSV·알림·CTI·카카오 실제 발송은 원 기획의 Phase 2/3으로 남긴다.

## 병렬 작업 경계

API 구현과 UI 구현을 API 계약 합의 후 병렬 진행한다. 루트 구성·하네스·배포 문서는 별도로 작업한다. 최종 통합 검증은 순차 진행한다.

## 검증 결과와 남은 경계

- SQLite API 8개, PostgreSQL API 8개 통과. PostgreSQL 테스트는 요청마다 별도 임시 스키마를 사용한다.
- 실제 API를 사용한 브라우저 통합 흐름 2개 통과: 등록·중복·배분·모바일 재통화 기록·재배분 권한 차단·비활성 세션 차단.
- 두 프론트엔드 Svelte 검사 오류/경고 0, 배포 빌드 통과.
- PostgreSQL migration upgrade/check/downgrade/upgrade 통과. Docker Compose 설정 검사 통과.
- 로컬 Docker 엔진이 실행되지 않아 실제 컨테이너 빌드/구동은 미검증. CI에 컨테이너 빌드와 Caddy 설정 검증을 포함했다.
- 실서비스 배포는 수행하지 않았다. 도메인·운영 비밀값·백업 저장소가 필요하다.
- 활동은 수정/삭제 API 없이 누적 보존한다. 정정/취소를 위한 후속 데이터 설계는 `apps/api/ACTIVITY_HISTORY.md`에 정의했다. 현재는 원 기록을 남기고 정정 메모를 추가한다.
