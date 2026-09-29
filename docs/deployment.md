# 배포와 운영

## 구성

직원 웹과 관리자 웹은 독립 정적 빌드이다. Caddy가 두 도메인의 TLS를 종료하고 `/api/*`를 내부 FastAPI로 전달한다. PostgreSQL과 API 포트는 인터넷에 공개하지 않는다. Caddy만 80/443을 공개한다. 쿠키는 각 호스트에 한정되므로 웹과 어드민에서 각각 로그인한다.

Docker Compose의 실행 순서는 PostgreSQL healthy → 단일 migration 서비스 완료 → API healthy → gateway이다. 마이그레이션이 실패하면 새 API 실행이 차단된다. 동일 DB에 여러 migration 작업을 동시에 실행하지 않는다.

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
read -s LEADFLOW_BOOTSTRAP_PASSWORD
export LEADFLOW_BOOTSTRAP_PASSWORD
docker compose exec -e LEADFLOW_BOOTSTRAP_PASSWORD api python -m app.cli bootstrap-admin --login-id admin --name 관리자
unset LEADFLOW_BOOTSTRAP_PASSWORD
```

두 HTTPS 주소에서 로그인하고 직원 생성 → 고객 등록 → 배분 → 직원 업무 기록을 확인한다. API health는 `/api/health`이다. 부하와 운영 정책에 맞는 모니터링·알림 대상도 연결한다.

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
