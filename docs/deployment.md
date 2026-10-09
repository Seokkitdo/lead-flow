# 배포와 운영

## 구성

직원 웹과 관리자 웹은 독립 정적 빌드이다. Caddy가 두 도메인의 TLS를 종료하고 `/api/*`를 내부 FastAPI로 전달한다. PostgreSQL과 API 포트는 인터넷에 공개하지 않는다. Caddy만 80/443을 공개한다. 쿠키는 각 호스트에 한정되므로 서로 다른 도메인에서는 각각 로그인한다. 두 진입점 모두 계정 권한에 따라 관리자 또는 직원 화면을 제공한다.

Docker Compose의 실행 순서는 PostgreSQL healthy → 단일 migration 서비스 완료 → API healthy → gateway이다. 마이그레이션이 실패하면 새 API 실행이 차단된다. 동일 DB에 여러 migration 작업을 동시에 실행하지 않는다.

## GitHub Actions 자동 배포

Vultr의 소형 서버에서는 GitHub Actions에서 이미지를 빌드하고 서버는 이미지 실행만 맡는다. `.github/workflows/ci.yml`은 `main`의 검증 성공 후 GHCR에 이미지를 올리고 배포 전용 SSH 계정으로 갱신한다. `DEPLOY_ENABLED` 변수를 `true`로 설정하기 전에는 검증과 이미지 발행까지만 실행하고 서버 배포는 대기한다. PR과 `feature/**`는 운영 이미지 발행·배포를 실행하지 않는다. 수동 재실행은 Actions의 `verify` → Run workflow에서 `main`을 선택한다.

### 최초 서버 준비

1. 관리자 SSH 키로 서버에 접속하고 `cloud-init status`가 `done`인지 확인한다.
2. 자동 배포 전용 Ed25519 키를 따로 만든다. 개인 Mac 접속용 키를 재사용하지 않는다. 자동 배포 키는 대화형 암호 입력 없이 사용할 수 있게 만들고 개인키 파일 권한을 `600`으로 유지한다.
3. 서버에 `scripts/setup-production-host.sh`와 배포 전용 **공개키**를 복사한 뒤 root로 `bash setup-production-host.sh /path/to/deploy-key.pub`를 실행한다. 공식 Docker apt 저장소를 사용하며 `leadflow-deploy` 계정과 `/opt/leadflow`를 준비한다. 운영 Docker Compose는 v2.24 이상을 사용한다.
4. `/opt/leadflow/.env`를 `.env.example` 형식으로 작성한다. 긴 임의 hex DB 비밀번호와 서로 다른 실제 웹·관리자 도메인을 넣는다. 소유자는 `leadflow-deploy`, 파일 권한은 `600`으로 한다. 이 파일은 Git이나 Actions 로그에 올리지 않는다.
5. 두 도메인의 DNS A 레코드를 서버 IPv4로 연결한다. IPv6를 별도로 연결하지 않았다면 잘못된 AAAA 레코드를 두지 않는다. HTTPS 인증서 발급을 위해 TCP 80/443을 허용한다. API 8000과 PostgreSQL 5432는 공개하지 않는다.
6. 배포 계정에 Docker 접근 권한이 있으므로 해당 SSH 키와 GitHub의 쓰기 권한은 서버 관리자 권한에 준해 관리한다. 키에는 `restrict` 옵션을 붙여 터널·포트 전달·PTY를 비활성화하지만 배포 명령 실행은 허용한다.

GitHub Actions 실행기도 SSH 포트에 접근할 수 있어야 한다. Vultr 방화벽의 22번 포트를 개인 IP에만 허용한 상태에서는 Actions의 SSH 연결이 실패한다. 실제 방화벽 정책을 확인하고, 조직의 고정 IP 실행기 또는 사설망 연결을 쓰는 경우 해당 경로를 허용한다. 인터넷에서 SSH 접속을 허용하는 구성이라면 관리자 키 접속을 확인한 후 암호 로그인을 비활성화하고 배포 전용 키를 사용한다.

### GitHub 설정

저장소의 Settings → Secrets and variables → Actions → Secrets에 다음 저장소 Secrets를 등록한다. 유료 플랜의 환경 보호 기능을 전제로 하지 않는다.

| 이름                 | 값                                                               |
| -------------------- | ---------------------------------------------------------------- |
| `DEPLOY_HOST`        | 서버 IP 또는 SSH 호스트명                                        |
| `DEPLOY_USER`        | `leadflow-deploy`                                                |
| `DEPLOY_SSH_KEY`     | 배포 전용 개인키 전체 내용                                       |
| `DEPLOY_KNOWN_HOSTS` | 신뢰할 수 있는 최초 접속/서버 콘솔로 확인한 서버 SSH 호스트키 줄 |

호스트키 검증을 끄거나 Actions 실행 때마다 확인 없이 `ssh-keyscan` 결과를 신뢰하지 않는다. 서버를 재설치했다면 콘솔에서 새 지문을 확인한 뒤 Secret을 갱신한다. 별도의 Vultr API 키는 필요하지 않다.

서버 준비, DNS, 외부 백업 저장소 준비를 마치면 Settings → Secrets and variables → Actions → Variables에 `DEPLOY_ENABLED=true`를 등록한다. GHCR 업로드/다운로드는 해당 Actions 작업의 `GITHUB_TOKEN`으로 인증한다. 서버에는 작업 중에만 임시 Docker 인증 파일을 만들고 종료 시 지운다. 장기 GitHub 토큰을 서버에 보관하지 않는다.

### 배포 순서와 실패 처리

1. `pnpm verify`, 격리된 PostgreSQL의 migration 왕복·백업 복원, 컨테이너 빌드와 Caddy 검증을 통과한다.
2. `main` 커밋으로 API·gateway 이미지를 빌드하고 GHCR에 저장한다. 서버에는 변경 가능한 `latest` 태그 대신 이미지 digest를 전달한다.
3. `/opt/leadflow/releases/<commit>`에 `compose.production.yaml`과 `deploy.sh`를 전송한다. 운영 `.env`는 서버에 유지한다.
4. 서버 파일 잠금으로 동시 배포를 막고 이미지를 내려받는다. PostgreSQL을 확인한 다음 DB 전체를 백업하고 격리된 임시 DB에 복원한다. 복원 실패 시 migration을 실행하지 않는다.
5. 매 배포마다 새 migration 컨테이너를 단 한 번 실행한다. 성공한 경우에만 API·gateway를 교체하고 두 도메인의 HTTPS `/api/health`와 웹 진입점을 확인한다.
6. 성공한 이미지 digest는 `/opt/leadflow/current-images.env`, 직전 성공본은 `previous-images.env`에 기록한다. `current`는 성공한 배포 디렉터리를 가리킨다. 상태 확인에 실패하면 성공 표시를 남기지 않는다.

자동 배포는 DB와 앱의 하위 호환성을 보장하지 않는다. 비호환 migration은 점검 시간을 잡고 실행한다. 실패 시 DB를 자동 downgrade하거나 이전 DB로 덮어쓰지 않는다. migration이 이미 적용된 뒤 앱 교체가 실패하면 현재 DB와 이전 앱의 호환성을 먼저 확인해야 한다. 단일 서버이므로 짧은 중단이 생길 수 있다.

관리자 생성은 최초 정상 배포 뒤 서버에서 실행한다. `.env`와 성공한 이미지 digest 파일을 함께 사용한다.

```sh
cd /opt/leadflow
docker compose --env-file .env --env-file current-images.env -f current/compose.production.yaml exec api python -m app.cli bootstrap-admin --login-id admin --name 관리자
```

백업 파일은 `/opt/leadflow/backups`에 권한 제한 상태로 남긴다. 이것은 **같은 서버 안의 배포 직전 백업**이며 외부 백업을 대체하지 않는다. 실제 고객 데이터 운영 전 암호화된 외부 저장소로의 정기 백업·보존 기간·복구 검증을 따로 구성한다. 이 스크립트는 백업이나 이전 이미지를 자동 삭제하지 않으므로 디스크 사용량을 모니터링하고 보존 정책에 따라 정리한다.

## 최초 배포

Linux 서버, Docker Compose v2, 영속 디스크, 서버를 가리키는 서로 다른 웹·어드민 DNS가 필요하다.

1. `.env.example`을 `.env`로 복사한다. `POSTGRES_PASSWORD`는 `openssl rand -hex 32` 등으로 만든 충분히 긴 URL-safe 값으로 교체한다. URL 예약 문자를 포함하면 DB URL에 percent-encoding이 필요하므로 예제에서는 hex를 사용한다.
2. `WEB_DOMAIN`, `ADMIN_DOMAIN`을 실제 도메인으로 바꾼다. 프로토콜이나 경로는 넣지 않는다.
3. `pnpm verify`와 PostgreSQL migration 검증을 통과한 소스를 사용한다.
4. `docker compose config --quiet`로 환경변수와 구성을 검사한다.
5. `docker compose up -d --build`로 실행한다.
6. `docker compose ps`와 `docker compose logs --tail 100 migrate api gateway`로 초기화 성공을 확인한다.
7. 관리자를 명시적으로 생성한다. 암호를 커맨드 인자·로그·Git에 기록하지 않는다.

```sh
docker compose exec api python -m app.cli bootstrap-admin --login-id admin --name 관리자
```

두 HTTPS 주소에서 로그인하고 직원 생성 → 고객 등록 → 배분 → 직원 업무 기록을 확인한다. API health는 `/api/health`이다. 부하와 운영 정책에 맞는 모니터링·알림 대상도 연결한다.

## 계정 복구

직원 비밀번호는 관리자가 직원 관리의 계정 관리 화면에서 새 비밀번호로 재설정한다. 관리자 비밀번호를 분실한 경우 서버 운영자가 아래 명령을 실행하고 12자 이상의 새 비밀번호를 두 번 입력한다. 입력 내용은 화면에 표시되지 않는다.

```sh
docker compose exec api python -m app.cli reset-admin-password --login-id admin
```

활성 관리자 계정만 복구할 수 있다. 기존 세션을 모두 종료하고 암호 변경 사실을 감사 이력에 남기며 암호 자체는 기록하지 않는다. 계정 역할·재직 상태와 기존 고객 데이터는 유지한다. 자동화 환경에서는 기존과 같이 `LEADFLOW_BOOTSTRAP_PASSWORD` 환경변수를 전달할 수 있다.

## 설정 경계

- `LEADFLOW_ENVIRONMENT=production`: Secure 쿠키와 운영 설정 적용.
- `LEADFLOW_DATABASE_URL`: PostgreSQL 연결 문자열. 애플리케이션 프로세스와 migration이 같은 DB를 사용해야 한다.
- `LEADFLOW_ALLOWED_ORIGINS`: 쉼표로 구분한 정확한 HTTPS origin 두 개.
- `LEADFLOW_SESSION_HOURS`: 세션 만료 시간, 기본 12시간.
- 프론트에는 비밀키를 넣지 않는다. 브라우저는 같은 origin의 `/api`만 호출한다.
- 초기 구성은 단일 API 프로세스이다. 다중 복제 시 로그인 시도 제한을 공유 저장소로 옮기고 세션·DB 연결·migration 실행 주체를 점검한다.

## 업데이트

1. 검증된 커밋/태그와 이전 이미지 식별자를 기록하고 DB 백업을 만든다.
2. migration의 하위 호환성과 데이터 변화량을 검토한다. 비호환 migration은 점검 시간을 잡는다.
3. `docker compose build` 후 `docker compose up -d`를 실행한다.
4. API health와 웹/어드민 핵심 흐름을 확인한다.

Compose는 단일 서버 배포 구성으로 무중단 배포나 HA를 보장하지 않는다. 운영 규모가 커지면 관리형 PostgreSQL, 이미지 레지스트리와 별도 배포 파이프라인으로 확장한다.

## 백업과 복구

`postgres-data`는 반드시 영속 보관한다. 고객 데이터 백업은 접근 제한·암호화가 적용된 별도 저장소에 보관하고 보존 기간을 정한다.

```sh
# 서버에서 실행. backups 디렉터리는 접근 권한을 제한한다.
mkdir -p backups
chmod 700 backups
docker compose exec -T db pg_dump -U leadflow -d leadflow -Fc > backups/leadflow.dump
```

복구는 먼저 **격리된 새 DB**에서 검증한다. 기존 운영 DB를 덮어쓰는 명령을 자동 실행하지 않는다. 새 DB에 `pg_restore --no-owner`로 복원하고 migration 버전·사용자 수·고객 수·최근 활동·권한 흐름을 검증한 뒤 연결 전환을 진행한다.

앱 롤백은 이전 이미지와 호환되는 DB 스키마인지 확인한 뒤 실행한다. 배포 실패를 이유로 migration을 무조건 downgrade하지 않는다. DB downgrade 검증은 테스트용 DB에서만 수행한다.

## 출시 전 남은 결정

호스팅 계정·도메인·백업 저장소·모니터링 알림·실제 운영 관리자, 고객 보유/파기 정책을 확정해야 한다. 로컬 및 CI 검증은 실제 운영 인프라에서의 배포·복구 검증을 대체하지 않는다.

## 참고

[FastAPI Docker 배포](https://fastapi.tiangolo.com/deployment/docker/), [Tailwind Vite 연동](https://tailwindcss.com/docs/installation/using-vite), [TanStack Svelte Query](https://tanstack.com/query/latest/docs/framework/svelte/overview).
