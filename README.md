# LeadFlow

고객 유입·배분·상담 활동을 관리하는 내부 CRM. 직원 웹과 관리자 웹, Python API를 하나의 pnpm 모노레포에서 관리합니다.

```text
apps/
  web/          Svelte 직원 웹 (5173)
  admin/        Svelte 관리자 웹 (5174)
  api/          FastAPI · SQLAlchemy · Alembic (8000)
packages/
  ui/           디자인 토큰과 공통 Svelte 컴포넌트
  crm/          공유 CRM 화면과 업무 처리
  api-client/   API 타입과 요청 처리
infra/          Docker 빌드 · HTTPS 게이트웨이
scripts/        디자인 검사와 테스트 서버
```

## 로컬 시작

Node.js 20.19+ 또는 22+, pnpm 10.29.2, Python 3.12+, uv가 필요합니다.

```sh
pnpm install --frozen-lockfile
cd apps/api
uv sync --locked
uv run alembic upgrade head
# 아래 명령에서 직접 정한 12자 이상의 암호를 입력합니다.
read -s LEADFLOW_BOOTSTRAP_PASSWORD
export LEADFLOW_BOOTSTRAP_PASSWORD
uv run python -m app.cli bootstrap-admin --login-id admin --name 관리자
unset LEADFLOW_BOOTSTRAP_PASSWORD
cd ../..
```

터미널 두 개에서 각각 실행합니다.

```sh
pnpm dev:api
```

```sh
pnpm dev
```

### 접속 주소와 로그인

| 구분   | 개발 PC에서 접속      | 같은 네트워크의 다른 기기에서 접속 | 주요 메뉴                   |
| ------ | --------------------- | ---------------------------------- | --------------------------- |
| 관리자 | http://localhost:5174 | http://192.168.1.128:5174          | 고객 DB·고객 배분·직원 관리 |
| 직원   | http://localhost:5173 | http://192.168.1.128:5173          | 내 담당 고객·상담 활동 기록 |

`192.168.1.128`은 현재 개발 PC의 내부 IP입니다. IP가 바뀌면 해당 주소도 변경해야 합니다. 개발 API 문서는 개발 PC에서 http://localhost:8000/api/docs 로 접속합니다.

내부 IP로 접속할 때는 `apps/api/.env`의 `LEADFLOW_ALLOWED_ORIGINS`에도 직원·관리자 주소를 등록하고 API를 재시작해야 합니다. 누락하면 로그인 요청이 `403 Untrusted origin`으로 차단됩니다. 현재 개발 환경의 설정 예시는 다음과 같습니다.

```dotenv
LEADFLOW_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:3500,http://localhost:3501,http://127.0.0.1:5173,http://127.0.0.1:5174,http://192.168.1.128:5173,http://192.168.1.128:5174
```

관리자 계정은 초기 설정 명령으로 생성하고 비밀번호를 직접 지정합니다. 실제 계정 비밀번호는 문서나 Git에 기록하지 않습니다.

**관리자 계정으로 로그인해도 `5173`에 접속하면 직원 화면이 표시됩니다.** 고객 배분·직원 관리는 관리자 주소인 `5174`에서 진행합니다.

관리자 화면에서 직원 계정을 만든 뒤 고객을 등록·배분합니다. 직원은 자기 담당 고객만 조회하고 연락 활동·상태·재통화 일시를 기록할 수 있습니다. 기본 로그인 암호는 없습니다. 로컬 DB는 `apps/api/leadflow.db`에 저장되며 Git에서 제외됩니다.

## 검증

```sh
pnpm check                 # Svelte/TS 및 디자인 규칙
pnpm build                 # 직원/관리자 빌드
pnpm test:api              # 권한·세션·업무 로직 회귀 테스트
pnpm exec playwright install chromium
pnpm test:e2e              # 격리 DB + 실제 API/브라우저 통합 검증
pnpm verify                # 위 품질 게이트를 순서대로 실행
```

## 문서

- [기획안](docs/product-spec.md)
- [디자인 시스템과 하네스](docs/design-system.md)
- [구현 범위와 진행 상태](docs/implementation-plan.md)
- [배포·백업·복구](docs/deployment.md)
- [개발 규칙](AGENTS.md)

운영은 PostgreSQL과 Docker Compose를 기준으로 구성했습니다. 실제 도메인·호스팅 계정은 아직 연결하지 않았습니다. CSV, 알림, CTI, 카카오 실제 발송은 후속 단계입니다.
