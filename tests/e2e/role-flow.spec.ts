import { expect, test } from '@playwright/test';

const COMMON = 'http://127.0.0.1:4173';
const ALTERNATE = 'http://127.0.0.1:4174';

test('공통 로그인에서 역할을 선택하고 배분 후 미처리 고객의 이력을 보며 기록한다', async ({
  page,
  browser,
}, testInfo) => {
  await page.goto(COMMON + '/login');
  await page.getByLabel('로그인 ID').fill('e2e-admin');
  await page.getByLabel('비밀번호', { exact: true }).fill('e2e-only-admin-password');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page).toHaveURL(COMMON + '/');
  await expect(page.getByRole('link', { name: '직원 관리', exact: true })).toBeVisible();
  const employee = await page.request.post(COMMON + '/api/users', {
    data: {
      login_id: 'role-flow-staff',
      name: '합성흐름직원',
      password: 'e2e-role-flow-password',
      role: 'USER',
    },
  });
  expect(employee.status()).toBe(201);
  const staffId = (await employee.json()).id;
  const created = await page.request.post(COMMON + '/api/leads', {
    data: {
      name: '합성업무흐름고객',
      phone: '010-0000-8181',
      source: 'NAVER',
      initial_memo: '합성 최초 문의',
    },
  });
  expect(created.status()).toBe(201);
  const lead = await created.json();
  expect(
    (
      await page.request.post(COMMON + `/api/leads/${lead.id}/activities`, {
        data: {
          activity_type: 'MEMO',
          memo: '합성 인계 내용',
          status: 'HOLD',
          version: lead.version,
        },
      })
    ).status(),
  ).toBe(201);
  expect(
    (
      await page.request.post(COMMON + '/api/leads/assign', {
        data: {
          lead_id: lead.id,
          user_id: staffId,
          reason: '합성 배분',
        },
      })
    ).status(),
  ).toBe(200);

  const context = await browser.newContext();
  try {
    const staff = await context.newPage();
    await staff.goto(ALTERNATE + '/login?next=/team');
    await staff.getByLabel('로그인 ID').fill('role-flow-staff');
    await staff.getByLabel('비밀번호', { exact: true }).fill('e2e-role-flow-password');
    await staff.getByRole('button', { name: '로그인', exact: true }).click();
    await expect(staff).toHaveURL(ALTERNATE + '/leads');
    await expect(staff.getByRole('link', { name: '직원 관리', exact: true })).toHaveCount(0);
    await expect(staff.getByRole('columnheader', { name: '최근 메모' })).toBeVisible();
    await expect(staff.getByRole('columnheader', { name: '배분일' })).toBeVisible();
    const row = staff.getByRole('row').filter({ hasText: '합성업무흐름고객' });
    await expect(row).toContainText('합성 인계 내용');
    await expect(row).toContainText('배분 후 미처리');
    await staff.getByLabel('배분 후 처리 필터').selectOption('true');
    await expect(staff).toHaveURL(/work_pending=true/);
    await row.getByRole('link', { name: '합성업무흐름고객 업무 처리' }).click();
    await expect(staff.getByLabel('현재 상태')).toHaveValue('HOLD');
    const history = staff.getByRole('region', { name: '이전 상담 및 배분 이력' });
    await expect(history).toContainText('합성 인계 내용');
    await expect(history).toContainText('합성 배분');
    await staff.getByRole('button', { name: '전화 부재', exact: true }).click();
    await staff.getByLabel('현재 상태').selectOption('CONTACTING');
    await staff.getByLabel('업무 메모').fill('합성 첫 콜 부재');
    await staff.screenshot({
      path: testInfo.outputPath('consultation-with-history.png'),
      fullPage: true,
    });
    await staff.getByRole('button', { name: '저장 후 목록으로', exact: true }).click();
    await expect(staff).toHaveURL(ALTERNATE + '/leads?work_pending=true');
    await expect(staff.getByRole('row').filter({ hasText: '합성업무흐름고객' })).toHaveCount(0);
    await staff.getByLabel('배분 후 처리 필터').selectOption('');
    await expect(row).toContainText('합성 첫 콜 부재');
    await expect(row).not.toContainText('배분 후 미처리');
    await expect(row).toContainText('연락 진행 중');
    await staff.goto(COMMON + '/team');
    await expect(staff.getByRole('heading', { name: '접근할 수 없는 페이지입니다' })).toBeVisible();
    expect((await staff.request.get(COMMON + '/api/users')).status()).toBe(403);
    await staff.goto(COMMON + '/leads');
    await expect(staff.getByRole('row').filter({ hasText: '합성업무흐름고객' })).toBeVisible();
  } finally {
    await context.close();
  }
});
