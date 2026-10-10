import { expect, test, type Page } from '@playwright/test';

const ADMIN = 'http://127.0.0.1:4174';
async function login(page: Page, path = '/') {
  await page.goto(ADMIN + path);
  await page.getByLabel('로그인 아이디', { exact: true }).fill('e2e-admin');
  await page.getByLabel('비밀번호', { exact: true }).fill('e2e-only-admin-password');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.getByRole('navigation', { name: '주 메뉴' })).toBeVisible();
}
async function customer(page: Page, name: string) {
  const response = await page.request.post(ADMIN + '/api/leads', {
    data: {
      name,
      phone: '010-5555-' + String(Math.floor(Math.random() * 10000)).padStart(4, '0'),
      source: 'ETC',
      acquired_at: '2030-10-01T00:00:00Z',
      allow_duplicate: true,
    },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test('메뉴·상세 탭·수정은 URL로 이동하고 새로고침과 뒤로 가기로 필터·포커스를 복원한다', async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await login(page, '/leads?status=NEW');
  const lead = await customer(page, '합성라우팅고객');
  await page.reload();
  await expect(page).toHaveURL(ADMIN + '/leads?status=NEW');
  await expect(page.getByLabel('상담 상태 필터')).toHaveValue('NEW');
  await page.getByLabel('고객 검색').fill('합성라우팅고객');
  await expect(page.getByRole('row').filter({ hasText: '합성라우팅고객' })).toHaveCount(1);
  const filtered = page.url();
  await page.getByRole('link', { name: '합성라우팅고객 010' }).click();
  await expect(page).toHaveURL(new RegExp(`/leads/${lead.id}\\?`));
  await expect(page.getByRole('heading', { name: '고객 상세', exact: true })).toBeFocused();
  await page.getByRole('link', { name: /전체 기록/ }).click();
  await expect(page).toHaveURL(new RegExp(`/leads/${lead.id}/timeline`));
  await page.reload();
  await expect(page.getByRole('link', { name: /전체 기록/ })).toHaveAttribute(
    'aria-current',
    'page',
  );
  await page.goBack();
  await expect(page.getByLabel('업무 메모')).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(filtered);
  await expect(page.getByLabel('고객 검색')).toHaveValue('합성라우팅고객');
  await expect(page.locator(`#lead-${lead.id}`)).toBeFocused();
  await page.goForward();
  await page.getByRole('button', { name: '정보 수정' }).click();
  await expect(page).toHaveURL(new RegExp(`/leads/${lead.id}/edit`));
  await page.reload();
  await expect(page.getByLabel('이름 *', { exact: true })).toHaveValue('합성라우팅고객');
  await page.getByLabel('이름 *', { exact: true }).fill('합성수정고객');
  page.once('dialog', (dialog) => dialog.dismiss());
  await page
    .getByRole('navigation', { name: '주 메뉴' })
    .getByRole('link', { name: '업무 현황' })
    .click();
  await expect(page).toHaveURL(new RegExp('/edit'));
  await expect(page.getByLabel('이름 *', { exact: true })).toHaveValue('합성수정고객');
  page.once('dialog', (dialog) => dialog.dismiss());
  await page.evaluate(() => history.back());
  await expect(page).toHaveURL(new RegExp('/edit'));
  await page.getByRole('button', { name: '변경 사항 저장' }).click();
  await expect(page.getByRole('heading', { name: '합성수정고객', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('고객 정보를 저장했습니다');
  await page.screenshot({
    path: testInfo.outputPath('routed-detail-desktop.png'),
    animations: 'disabled',
    fullPage: true,
  });
  await page
    .getByRole('navigation', { name: '주 메뉴' })
    .getByRole('link', { name: '직원 관리' })
    .click();
  await expect(page).toHaveURL(ADMIN + '/team');
  await page.getByRole('link', { name: '직원 등록', exact: true }).click();
  await expect(page).toHaveURL(ADMIN + '/team/new');
  await page.reload();
  await expect(page.getByRole('heading', { name: '새 직원 등록' })).toBeVisible();
  await page.getByRole('link', { name: '직원 목록으로' }).click();
  await page
    .getByRole('navigation', { name: '주 메뉴' })
    .getByRole('link', { name: '업무 현황' })
    .click();
  await page.getByRole('link', { name: /재통화 예정.*다시 연락/ }).click();
  await expect(page).toHaveURL(ADMIN + '/callbacks?window=all');
  await expect(page.getByRole('link', { name: '전체', exact: true })).toHaveAttribute(
    'aria-current',
    'page',
  );
  await page.goto(ADMIN + '/unknown-page');
  await expect(page.getByRole('heading', { name: '페이지를 찾을 수 없습니다' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('조회 오류와 저장 오류를 구분하고 입력 보존·중복 제출 차단·충돌 복구를 제공한다', async ({
  page,
}) => {
  await login(page);
  const lead = await customer(page, '합성상태고객');
  await page.route('**/api/users', (route) =>
    route.fulfill({ status: 503, json: { detail: '직원 조회 테스트 오류' } }),
  );
  await page.goto(ADMIN + '/team');
  await expect(page.getByRole('alert')).toContainText('직원 조회 테스트 오류');
  await expect(page.getByText('등록된 직원이 없습니다')).toHaveCount(0);
  await page.unroute('**/api/users');
  await page.getByRole('button', { name: '다시 시도' }).click();
  await expect(page.getByRole('row').filter({ hasText: 'e2e-admin' })).toBeVisible();
  await page.goto(`${ADMIN}/leads/${lead.id}`);
  await page.getByLabel('상담 상태').selectOption('CALLBACK');
  await page.getByLabel('재통화 일시').fill('2030-10-01T15:00');
  await page.getByLabel('업무 메모').fill('실패 후에도 보존할 합성 메모');
  let attempts = 0;
  let release: () => void = () => {};
  await page.route('**/api/leads/*/activities', async (route) => {
    attempts++;
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    await route.fulfill({ status: 500, json: { detail: '저장 테스트 오류' } });
  });
  await page.getByRole('button', { name: '업무 기록 저장' }).click();
  await expect(page.getByRole('button', { name: '저장 중…' })).toBeDisabled();
  await page
    .getByRole('navigation', { name: '주 메뉴' })
    .getByRole('link', { name: '업무 현황' })
    .click();
  await expect(page).toHaveURL(`${ADMIN}/leads/${lead.id}`);
  release();
  await expect(page.getByRole('alert')).toContainText('저장 테스트 오류');
  await expect(page.getByLabel('업무 메모')).toHaveValue('실패 후에도 보존할 합성 메모');
  await expect(page.getByLabel('상담 상태')).toHaveValue('CALLBACK');
  await expect(page.getByLabel('재통화 일시')).toHaveValue('2030-10-01T15:00');
  expect(attempts).toBe(1);
  await page.unroute('**/api/leads/*/activities');
  await page.request.post(`${ADMIN}/api/leads/${lead.id}/activities`, {
    data: {
      activity_type: 'MEMO',
      memo: '다른 사용자의 합성 변경',
      status: 'HOLD',
      version: lead.version,
    },
  });
  await page.getByRole('button', { name: '업무 기록 저장' }).click();
  await expect(page.getByRole('button', { name: '최신 정보 불러오기' })).toBeVisible();
  await expect(page.getByLabel('업무 메모')).toHaveValue('실패 후에도 보존할 합성 메모');
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '최신 정보 불러오기' }).click();
  await expect(page.getByLabel('상담 상태')).toHaveValue('HOLD');
  await expect(page.getByLabel('업무 메모')).toHaveValue('');
  await page.getByLabel('업무 메모').fill('충돌 확인 후 새 업무 기록');
  await page.getByRole('button', { name: '업무 기록 저장' }).click();
  await expect(page.getByRole('status')).toContainText('업무 기록을 저장했습니다');
});

test('인증 확인 실패는 재시도하고 세션 만료 후 원래 상세 주소로 복귀한다', async ({ page }) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ status: 503, json: { detail: '연결 테스트 오류' } }),
  );
  await page.goto(ADMIN + '/leads');
  await expect(page.getByRole('alert')).toContainText('연결 테스트 오류');
  await expect(page.getByLabel('비밀번호', { exact: true })).toHaveCount(0);
  await page.unroute('**/api/auth/me');
  await page.getByRole('button', { name: '다시 시도' }).click();
  await expect(page).toHaveURL(/\/login\?next=/);
  await page.getByLabel('로그인 아이디', { exact: true }).fill('e2e-admin');
  await page.getByLabel('비밀번호', { exact: true }).fill('e2e-only-admin-password');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page).toHaveURL(ADMIN + '/leads');
  const lead = await customer(page, '합성인증고객');
  await page.goto(`${ADMIN}/leads/${lead.id}/activity`);
  await page.getByLabel('업무 메모').fill('만료된 세션의 합성 메모');
  expect((await page.request.post(ADMIN + '/api/auth/logout', { data: {} })).ok()).toBeTruthy();
  await page.getByRole('button', { name: '업무 기록 저장' }).click();
  await expect(page).toHaveURL(/\/login\?next=/);
  await expect(page.getByRole('alert')).toContainText('로그인이 만료되었습니다');
  await page.getByLabel('로그인 아이디', { exact: true }).fill('e2e-admin');
  await page.getByLabel('비밀번호', { exact: true }).fill('e2e-only-admin-password');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page).toHaveURL(`${ADMIN}/leads/${lead.id}/activity`);
  await expect(page.getByLabel('업무 메모')).toBeVisible();
});

test('작은 화면의 상세 페이지와 모션 감소 설정, 권한 없는 직접 주소를 처리한다', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await login(page);
  const lead = await customer(page, '합성모바일고객');
  await page.goto(`${ADMIN}/leads/${lead.id}/timeline`);
  await expect(page.getByRole('heading', { name: '합성모바일고객', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(
    await page.locator('.page-enter').evaluate((el) => getComputedStyle(el).animationName),
  ).toBe('none');
  await page.screenshot({
    path: testInfo.outputPath('routed-mobile-timeline.png'),
    animations: 'disabled',
    fullPage: true,
  });
  // Both entry points choose the workspace from the authenticated role.
  await page.goto('http://127.0.0.1:4173/team');
  await expect(page.getByRole('heading', { name: '직원 관리.', exact: true })).toBeVisible();
  expect((await page.request.get('http://127.0.0.1:4173/api/users')).status()).toBe(200);
});

test('목록 페이지 번호를 복원하고 고객 수정 충돌은 최신 정보 확인 후에만 저장한다', async ({
  page,
}) => {
  await login(page);
  for (let index = 0; index < 16; index++)
    await customer(page, `합성페이지고객${String(index).padStart(2, '0')}`);
  await page.goto(ADMIN + '/leads?search=' + encodeURIComponent('합성페이지고객'));
  await page.getByRole('button', { name: '다음', exact: true }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.getByRole('link', { name: /합성페이지고객.*상세 보기/ }).click();
  const detailUrl = page.url();
  const id = new URL(detailUrl).pathname.split('/')[2];
  await page.getByRole('button', { name: '정보 수정' }).click();
  await page.getByLabel('이름 *', { exact: true }).fill('합성충돌수정고객');
  const latest = await (await page.request.get(`${ADMIN}/api/leads/${id}`)).json();
  expect(
    (
      await page.request.patch(`${ADMIN}/api/leads/${id}`, {
        data: { name: '합성다른사용자수정', version: latest.version },
      })
    ).ok(),
  ).toBeTruthy();
  await page.getByRole('button', { name: '변경 사항 저장' }).click();
  await expect(page.getByRole('button', { name: '최신 정보 불러오기' })).toBeVisible();
  await expect(page.getByLabel('이름 *', { exact: true })).toHaveValue('합성충돌수정고객');
  await expect(page.getByRole('button', { name: '변경 사항 저장' })).toBeDisabled();
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '최신 정보 불러오기' }).click();
  await expect(page.getByLabel('이름 *', { exact: true })).toHaveValue('합성다른사용자수정');
  await page.getByLabel('이름 *', { exact: true }).fill('합성페이지고객수정완료');
  await page.getByRole('button', { name: '변경 사항 저장' }).click();
  await expect(page.getByRole('heading', { name: '합성페이지고객수정완료' })).toBeVisible();
  await page.getByRole('link', { name: '목록으로', exact: true }).click();
  await expect(page).toHaveURL(/page=2/);
  await page.goBack();
  await expect(page.getByRole('heading', { name: '합성페이지고객수정완료' })).toBeVisible();
});

test('상세 화면의 로그아웃 오류를 표시하고 재시도 후 뒤로 가기도 인증을 요구한다', async ({
  page,
}) => {
  await login(page, '/leads/new');
  await page.route('**/api/auth/logout', (route) =>
    route.fulfill({ status: 503, json: { detail: '로그아웃 테스트 오류' } }),
  );
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('로그아웃 테스트 오류');
  await expect(page.getByRole('region', { name: '고객 등록', exact: true })).toBeVisible();
  await page.unroute('**/api/auth/logout');
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await expect(page).toHaveURL(ADMIN + '/login');
  await expect(page.getByLabel('비밀번호', { exact: true })).toBeVisible();
  await page.goto(ADMIN + '/leads/new');
  await expect(page).toHaveURL(/\/login\?next=/);
  await expect(page.getByRole('region', { name: '고객 등록', exact: true })).toHaveCount(0);
});
