import { expect, test, type Page } from '@playwright/test';

const ORIGIN = 'http://127.0.0.1:4174';
async function admin(page: Page) {
  expect(
    (
      await page.request.post(ORIGIN + '/api/auth/login', {
        data: { login_id: 'e2e-admin', password: 'e2e-only-admin-password' },
      })
    ).ok(),
  ).toBeTruthy();
}
async function fixture(page: Page) {
  await admin(page);
  const userResponse = await page.request.post(ORIGIN + '/api/users', {
    data: {
      login_id: `work-${Date.now()}`,
      name: '합성업무담당자',
      password: 'synthetic-password-123',
    },
  });
  expect(userResponse.ok()).toBeTruthy();
  const user = await userResponse.json();
  const leadResponse = await page.request.post(ORIGIN + '/api/leads', {
    data: { name: '합성재통화고객', phone: '010-0000-7890', allow_duplicate: true },
  });
  const lead = await leadResponse.json();
  expect(
    (
      await page.request.post(ORIGIN + '/api/leads/assign', {
        data: { lead_id: lead.id, user_id: user.id },
      })
    ).ok(),
  ).toBeTruthy();
  const latest = await (await page.request.get(ORIGIN + `/api/leads/${lead.id}`)).json();
  // An elapsed time today makes this customer appear in both today and overdue.
  const callback = new Date();
  callback.setUTCSeconds(0, 0);
  expect(
    (
      await page.request.post(ORIGIN + `/api/leads/${lead.id}/activities`, {
        data: {
          version: latest.version,
          activity_type: 'CALL_CONNECTED',
          memo: '합성 최초 상담',
          status: 'CALLBACK',
          callback_at: callback.toISOString(),
        },
      })
    ).ok(),
  ).toBeTruthy();
  return { user, lead };
}

test('관리자는 직원 업무 상세에서 필터링하고 고객 이력과 계정 관리로 이동한다', async ({
  page,
}) => {
  const { user, lead } = await fixture(page);
  await page.goto(ORIGIN + '/team');
  const row = page.getByRole('row').filter({ hasText: user.login_id });
  await row.getByRole('link', { name: '업무 상세', exact: true }).click();
  await expect(page).toHaveURL(ORIGIN + `/team/${user.id}/work`);
  await expect(page.getByRole('heading', { name: '직원 업무 상세', exact: true })).toBeVisible();
  await page.getByLabel('처리 여부').selectOption('true');
  await expect(page.getByRole('link', { name: lead.name, exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: '업무 상태', exact: true }).selectOption('CALLBACK');
  const listUrl = page.url();
  await page.reload();
  await expect(page.getByLabel('처리 여부')).toHaveValue('true');
  await page.getByRole('link', { name: lead.name, exact: true }).click();
  await expect(page.getByRole('heading', { name: lead.name, exact: true })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(listUrl);
  await expect(page.locator(`#work-lead-${lead.id}`)).toBeFocused();
  await page.getByRole('link', { name: '계정 관리', exact: true }).click();
  await expect(page.getByLabel('로그인 ID *', { exact: true })).toHaveValue(user.login_id);
  await page.goto(ORIGIN + `/team/${user.id}/work?status=COMPLETED`);
  await expect(page.getByText('해당하는 고객이 없습니다')).toBeVisible();
  await page.goto(ORIGIN + '/account');
  await page.getByLabel('연락처', { exact: true }).fill('010-0000-1234');
  await page.getByLabel('현재 비밀번호 *').fill('e2e-only-admin-password');
  await page.getByRole('button', { name: '계정 정보 저장' }).click();
  await expect(page.getByRole('status')).toContainText('계정 정보를 저장했습니다');
});

test('직원은 재통화 상세에서 원본을 보존해 정정하고 계정 비밀번호를 변경한다', async ({
  page,
  browser,
}, testInfo) => {
  const { user, lead } = await fixture(page);
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const staff = await context.newPage();
  expect(
    (
      await staff.request.post(ORIGIN + '/api/auth/login', {
        data: { login_id: user.login_id, password: 'synthetic-password-123' },
      })
    ).ok(),
  ).toBeTruthy();
  await staff.goto(ORIGIN + '/callbacks');
  await expect(staff.getByRole('link', { name: lead.name, exact: true })).toBeVisible();
  await staff.getByRole('link', { name: '기한 초과', exact: true }).click();
  await staff.reload();
  await expect(staff.getByRole('link', { name: '기한 초과', exact: true })).toHaveAttribute(
    'aria-current',
    'page',
  );
  await staff.getByRole('link', { name: lead.name, exact: true }).click();
  await staff.getByRole('link', { name: '기록 상세·정정', exact: true }).first().click();
  await staff.reload();
  await expect(staff.getByRole('heading', { name: '업무 기록 상세' })).toBeVisible();
  await staff.getByLabel('사유 *', { exact: true }).fill('합성 입력 오류');
  await staff.getByLabel('정정 내용 *', { exact: true }).fill('합성 정정된 상담');
  await staff.getByLabel('저장할 현재 상태').selectOption('HOLD');
  staff.once('dialog', (dialog) => dialog.dismiss());
  await staff.getByRole('link', { name: '전체 타임라인으로', exact: true }).click();
  await expect(staff.getByLabel('정정 내용 *', { exact: true })).toHaveValue('합성 정정된 상담');
  await staff.screenshot({ path: testInfo.outputPath('record-mobile.png'), fullPage: true });
  expect(
    await staff.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await staff.getByRole('button', { name: '정정·취소 기록 저장' }).click();
  await expect(staff.getByRole('status')).toContainText('원본을 보존');
  await staff.getByRole('link', { name: '전체 타임라인으로', exact: true }).click();
  await expect(staff.getByText('합성 최초 상담', { exact: true })).toBeVisible();
  await expect(staff.getByText(/합성 정정된 상담/)).toBeVisible();
  await staff.getByRole('link', { name: '목록으로', exact: true }).click();
  await expect(staff).toHaveURL(ORIGIN + '/callbacks?window=overdue');
  await expect(staff.getByText('해당하는 고객이 없습니다')).toBeVisible();
  await staff.goto(ORIGIN + `/team/${user.id}/work`);
  await expect(staff.getByRole('heading', { name: '접근할 수 없는 페이지입니다' })).toBeVisible();
  await staff.goto(ORIGIN + '/account');
  await staff.getByLabel('현재 비밀번호 *').fill('wrong-password');
  await staff.getByRole('button', { name: '계정 정보 저장' }).click();
  await expect(staff.getByRole('alert')).toContainText('현재 비밀번호를 확인');
  await staff.getByLabel('현재 비밀번호 *').fill('synthetic-password-123');
  await staff.getByLabel('새 비밀번호', { exact: true }).fill('changed-password-123');
  await staff.getByLabel('새 비밀번호 확인', { exact: true }).fill('changed-password-123');
  await staff.getByRole('button', { name: '계정 정보 저장' }).click();
  await expect(staff).toHaveURL(/\/login\?next=%2Faccount/);
  await staff.getByLabel('로그인 ID', { exact: true }).fill(user.login_id);
  await staff.getByLabel('비밀번호', { exact: true }).fill('changed-password-123');
  await staff.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(staff).toHaveURL(ORIGIN + '/account');
  await context.close();
});

test('추가 페이지의 조회 오류·없는 기록·계정 충돌은 복구 경로를 제공한다', async ({ page }) => {
  const { lead } = await fixture(page);
  await page.route('**/api/leads?*callback_window*', (route) =>
    route.fulfill({ status: 503, json: { detail: '합성 일정 조회 오류' } }),
  );
  await page.goto(ORIGIN + '/callbacks');
  await expect(page.getByText('합성 일정 조회 오류')).toBeVisible();
  await page.unroute('**/api/leads?*callback_window*');
  await page.getByRole('button', { name: '다시 시도' }).click();
  await expect(page.getByRole('link', { name: lead.name, exact: true }).first()).toBeVisible();
  await page.goto(ORIGIN + `/leads/${lead.id}/records/00000000-0000-0000-0000-000000000000`);
  await expect(page.getByText('업무 기록을 찾을 수 없습니다')).toBeVisible();
  await page.goto(ORIGIN + '/account');
  await page.getByLabel('연락처', { exact: true }).fill('010-0000-5555');
  await page.getByLabel('현재 비밀번호 *').fill('e2e-only-admin-password');
  const user = await (await page.request.get(ORIGIN + '/api/auth/me')).json();
  expect(
    (
      await page.request.patch(ORIGIN + '/api/auth/me', {
        data: {
          version: user.version,
          current_password: 'e2e-only-admin-password',
          phone: '010-0000-9876',
        },
      })
    ).ok(),
  ).toBeTruthy();
  await page.getByRole('button', { name: '계정 정보 저장' }).click();
  await expect(page.getByRole('alert')).toContainText('계정 정보가 변경');
  await expect(page.getByLabel('연락처', { exact: true })).toHaveValue('010-0000-5555');
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '최신 계정 정보 불러오기' }).click();
  await expect(page.getByLabel('연락처', { exact: true })).toHaveValue('010-0000-9876');
});
