import { expect, test, type Page } from '@playwright/test';

const ADMIN_URL = 'http://127.0.0.1:4174';
const STAFF_URL = 'http://127.0.0.1:4173';
const employeePassword = 'e2e-only-staff-password';

async function login(page: Page, url: string, loginId: string, password: string) {
  await page.goto(url);
  await page.getByLabel('로그인 ID').fill(loginId);
  await page.getByLabel('비밀번호', { exact: true }).fill(password);
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.getByRole('navigation', { name: '주 메뉴' })).toBeVisible();
}

// The server is bootstrapped into a temporary database for each test run.
// All customer and staff records below are synthetic and created through the app.
test('관리자 등록·중복 확인·배분 → 직원 재통화 기록 → 재배분 접근 차단', async ({
  page,
  browser,
}, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await login(page, ADMIN_URL, 'e2e-admin', 'e2e-only-admin-password');
  await page.getByRole('navigation').getByRole('link', { name: '직원 관리', exact: true }).click();
  for (const [loginId, name] of [
    ['e2e-staff-one', '가상직원하나'],
    ['e2e-staff-two', '가상직원둘'],
  ]) {
    await page.getByRole('link', { name: '직원 등록', exact: true }).click();
    const form = page.getByRole('region', { name: '직원 계정 관리' });
    await form.getByLabel('이름 *', { exact: true }).fill(name);
    await form.getByLabel('로그인 ID *', { exact: true }).fill(loginId);
    await form.getByLabel('초기 비밀번호', { exact: false }).fill(employeePassword);
    await form.getByRole('button', { name: '저장하기' }).click();
    await expect(form).not.toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: loginId })).toBeVisible();
  }
  await page.getByRole('navigation').getByRole('link', { name: '고객 DB', exact: true }).click();
  for (const name of ['합성고객하나', '합성중복고객']) {
    await page.getByRole('button', { name: '고객 등록', exact: true }).click();
    const form = page.getByRole('region', { name: '고객 등록', exact: true });
    await form.getByLabel('이름 *', { exact: true }).fill(name);
    await form.getByLabel('연락처 *', { exact: true }).fill('010-0000-9999');
    await form.getByLabel('최초 메모').fill('합성 데이터: 테스트 전용 문의');
    await form.getByRole('button', { name: '고객 등록', exact: true }).click();
    if (name === '합성중복고객') {
      await expect(form.getByText('같은 연락처의 고객이 있습니다')).toBeVisible();
      await expect(form.getByRole('button', { name: '기존 고객 보기' })).toBeVisible();
      await form.getByRole('button', { name: '확인했어요, 그래도 등록' }).click();
    }
    await expect(form).not.toBeVisible();
    await page.getByRole('link', { name: '목록으로', exact: true }).click();
  }
  await page.getByLabel('합성고객하나 선택', { exact: true }).check();
  await page.getByRole('button', { name: '담당자 배분', exact: true }).click();
  const assignment = page.getByRole('dialog', { name: '담당자 배분' });
  await assignment.getByRole('checkbox', { name: /가상직원하나/ }).check();
  await assignment.getByLabel('배분 사유').fill('E2E 최초 배분');
  await assignment.getByRole('button', { name: '1명 배분하기' }).click();
  await expect(assignment).not.toBeVisible();
  await expect(page.getByRole('row').filter({ hasText: '합성고객하나' })).toContainText(
    '가상직원하나',
  );

  await page.screenshot({
    path: testInfo.outputPath('admin-customer-list.png'),
    animations: 'disabled',
    fullPage: true,
  });
  await page.getByRole('navigation').getByRole('link', { name: '대시보드', exact: true }).click();
  await page.screenshot({
    path: testInfo.outputPath('admin-dashboard.png'),
    animations: 'disabled',
    fullPage: true,
  });

  const staffContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    timezoneId: 'Asia/Seoul',
  });
  const staff = await staffContext.newPage();
  staff.on('pageerror', (error) => errors.push(error.message));
  try {
    await login(staff, STAFF_URL, 'e2e-staff-one', employeePassword);
    await expect(staff.getByRole('link', { name: '합성고객하나 상세 보기' })).toBeVisible();
    await expect(staff.getByRole('link', { name: '합성중복고객 상세 보기' })).toHaveCount(0);
    const visibleLeads = await (await staff.request.get(`${STAFF_URL}/api/leads`)).json();
    expect(visibleLeads.total).toBe(1);
    const leadId = visibleLeads.items[0].id;
    expect((await staff.request.get(`${STAFF_URL}/api/users`)).status()).toBe(403);
    await staff.getByRole('link', { name: '합성고객하나 상세 보기' }).click();
    const detail = staff.getByRole('region', { name: '고객 상세', exact: true });
    await expect(detail.getByRole('heading', { name: '합성고객하나' })).toBeVisible();
    const bounds = await detail.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
      };
    });
    expect(bounds.x).toBe(0);
    expect(bounds.width).toBe(bounds.viewportWidth);
    expect(
      await staff.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await detail.getByRole('button', { name: '전화 연결', exact: true }).click();
    await detail.getByLabel('현재 상태').selectOption('CALLBACK');
    await detail.getByLabel('재통화 일시').fill('2030-10-01T14:30');
    await detail.getByLabel('업무 메모').fill('합성 통화 기록: 다음 상담에서 다시 연락');
    await detail.getByRole('button', { name: '업무 기록 저장' }).click();
    await expect(detail.getByRole('status')).toHaveText('업무 기록을 저장했습니다.');
    await detail.getByRole('link', { name: /전체 타임라인/ }).click();
    await expect(
      detail.getByText('합성 통화 기록: 다음 상담에서 다시 연락', { exact: true }),
    ).toBeVisible();
    await expect(detail.getByText('E2E 최초 배분', { exact: true })).toBeVisible();
    const saved = await (await staff.request.get(`${STAFF_URL}/api/leads/${leadId}`)).json();
    expect(saved.current_status).toBe('CALLBACK');
    expect(new Date(saved.callback_at).toISOString()).toBe('2030-10-01T05:30:00.000Z');
    expect(
      saved.timeline.filter((event: { kind: string }) => event.kind === 'ACTIVITY'),
    ).toHaveLength(1);
    await staff.screenshot({
      path: testInfo.outputPath('staff-mobile-timeline.png'),
      animations: 'disabled',
      fullPage: false,
    });

    await page.getByRole('link', { name: '합성고객하나 상세 보기' }).click();
    const adminDetail = page.getByRole('region', { name: '고객 상세', exact: true });
    await adminDetail.getByRole('link', { name: '담당자 변경', exact: true }).click();
    await adminDetail.getByLabel('새 담당자').selectOption({ label: '가상직원둘' });
    await adminDetail.getByLabel('변경 사유').fill('E2E 재배분 권한 확인');
    await adminDetail
      .locator('form')
      .getByRole('button', { name: '담당자 변경', exact: true })
      .click();
    await expect(adminDetail.getByRole('status')).toHaveText('담당자를 변경했습니다.');
    expect((await staff.request.get(`${STAFF_URL}/api/leads/${leadId}`)).status()).toBe(404);
    expect((await (await staff.request.get(`${STAFF_URL}/api/leads`)).json()).total).toBe(0);
    await page.getByRole('link', { name: '목록으로', exact: true }).click();
    await page
      .getByRole('navigation')
      .getByRole('link', { name: '직원 관리', exact: true })
      .click();
    await page
      .getByRole('row')
      .filter({ hasText: 'e2e-staff-one' })
      .getByRole('link', { name: '계정 관리' })
      .click();
    const account = page.getByRole('region', { name: '직원 계정 관리' });
    await account.getByLabel('재직 상태').selectOption('INACTIVE');
    await account.getByRole('button', { name: '저장하기' }).click();
    await expect(account).not.toBeVisible();
    expect((await staff.request.get(`${STAFF_URL}/api/auth/me`)).status()).toBe(401);
    await staff.reload();
    await expect(staff.getByRole('button', { name: '로그인', exact: true })).toBeVisible();
  } finally {
    await staffContext.close();
  }
  expect(errors).toEqual([]);
});

test('로그인 오류를 표시하고 모바일에서도 입력 폼이 화면 안에 유지된다', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(STAFF_URL);
  await page.getByLabel('로그인 ID').fill('does-not-exist');
  await page.getByLabel('비밀번호', { exact: true }).fill('wrong-e2e-password');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('아이디 또는 비밀번호');
  await expect(page.getByLabel('로그인 ID')).toHaveValue('does-not-exist');
  await expect(page.getByRole('button', { name: '로그인', exact: true })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});
