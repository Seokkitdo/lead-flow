import { expect, test } from '@playwright/test';

test('직원 안내 → 고객 연속 등록과 즉시 배정 → 결과 기록 후 다음 고객', async ({
  page,
  browser,
}, testInfo) => {
  await page.goto('/login');
  await page.getByLabel('로그인 아이디').fill('e2e-admin');
  await page.getByLabel('비밀번호', { exact: true }).fill('e2e-only-admin-password');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await page.getByRole('navigation', { name: '주 메뉴' }).waitFor();
  await page.goto('/team/new');
  await page.getByLabel('이름 *', { exact: true }).fill('합성과정직원');
  await page.getByLabel('로그인 아이디 *').fill('process-staff');
  await page.getByRole('button', { name: '비밀번호 자동 생성' }).click();
  const password = await page.getByLabel('초기 비밀번호 *', { exact: false }).inputValue();
  expect(password.length).toBeGreaterThanOrEqual(12);
  await page.getByRole('button', { name: '직원 등록', exact: true }).click();
  const guide = page.getByRole('region', { name: '직원 등록 완료' });
  await expect(guide).toContainText('process-staff');
  await expect(guide.getByRole('link', { name: '고객 배정하기' })).toBeVisible();
  await expect(guide).not.toContainText(password);
  await page.goto('/leads/new');
  const form = page.getByRole('region', { name: '고객 등록', exact: true });
  await form.getByLabel('담당자', { exact: true }).selectOption({ label: '합성과정직원' });
  await form.getByLabel('이름 *', { exact: true }).fill('합성과정고객첫째');
  await form.getByLabel('연락처 *', { exact: true }).fill('01000006101');
  await form.getByLabel('문의일').fill('2026-10-01T10:00');
  await form.getByRole('button', { name: '등록 후 계속 추가' }).click();
  await expect(form.getByRole('status')).toContainText('합성과정고객첫째');
  await expect(form.getByLabel('이름 *', { exact: true })).toBeEmpty();
  await expect(form.getByLabel('이름 *', { exact: true })).toBeFocused();
  await expect(form.getByLabel('연락처 *', { exact: true })).toBeEmpty();
  await form.getByLabel('이름 *', { exact: true }).fill('합성과정고객둘째');
  await form.getByLabel('연락처 *', { exact: true }).fill('01000006102');
  await form.getByLabel('문의일').fill('2026-10-02T10:00');
  await form.getByRole('button', { name: '고객 등록', exact: true }).click();
  await expect(form).not.toBeVisible();
  await expect(page.getByRole('region', { name: '고객 상세', exact: true })).toContainText(
    '합성과정직원',
  );

  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const staff = await context.newPage();
  try {
    await staff.goto('http://127.0.0.1:4173/login');
    await staff.getByLabel('로그인 아이디').fill('process-staff');
    await staff.getByLabel('비밀번호', { exact: true }).fill(password);
    await staff.getByRole('button', { name: '로그인', exact: true }).click();
    await staff.getByRole('link', { name: '배정 후 기록 없는 고객', exact: true }).click();
    await staff.getByRole('link', { name: '합성과정고객둘째 업무 처리', exact: true }).click();
    await staff.getByRole('button', { name: '전화 안 받음', exact: true }).click();
    await expect(staff.getByLabel('상담 상태')).toHaveValue('CONTACTING');
    await staff.getByLabel('업무 메모').fill('합성 기록: 부재 후 다시 연락');
    await staff.route(
      '**/api/leads/*/activities',
      (route) =>
        route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: '합성 저장 실패' }),
        }),
      { times: 1 },
    );
    await staff.getByRole('button', { name: '저장하고 다음 고객' }).click();
    await expect(staff.getByRole('alert')).toContainText('합성 저장 실패');
    await expect(
      staff.getByRole('heading', { name: '합성과정고객둘째', exact: true }),
    ).toBeVisible();
    await expect(staff.getByLabel('업무 메모')).toHaveValue('합성 기록: 부재 후 다시 연락');
    await staff.getByRole('button', { name: '저장하고 다음 고객' }).click();
    await expect(
      staff.getByRole('heading', { name: '합성과정고객첫째', exact: true }),
    ).toBeVisible();
    await expect(staff.getByLabel('상담 상태')).toHaveValue('NEW');
    await expect(staff.getByRole('button', { name: '메모 작성', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await staff.getByRole('button', { name: '재통화 예약', exact: true }).click();
    await staff.getByRole('button', { name: '내일 오전 10시' }).click();
    await expect(staff.getByLabel('재통화 일시 * (한국 시간)')).not.toBeEmpty();
    await staff.getByRole('button', { name: '저장하고 다음 고객' }).click();
    await expect(staff.getByRole('status')).toContainText('이 목록의 마지막 고객입니다');
    await staff.screenshot({ path: testInfo.outputPath('staff-next-mobile.png'), fullPage: true });
    expect(await staff.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  } finally {
    await context.close();
  }
});

test('여러 페이지 선택을 유지하고 직원별 배정 건수를 미리 보여준다', async ({ page }, testInfo) => {
  await page.goto('/login');
  await page.getByLabel('로그인 아이디').fill('e2e-admin');
  await page.getByLabel('비밀번호', { exact: true }).fill('e2e-only-admin-password');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await page.getByRole('navigation', { name: '주 메뉴' }).waitFor();
  const employee = await page.request.post('/api/users', {
    data: {
      name: '합성배정직원',
      login_id: 'process-assign-staff',
      password: 'synthetic-process-password',
    },
  });
  expect(employee.status()).toBe(201);
  const secondEmployee = await page.request.post('/api/users', {
    data: {
      name: '합성배정직원둘',
      login_id: 'process-assign-second',
      password: 'synthetic-process-password',
    },
  });
  expect(secondEmployee.status()).toBe(201);
  for (let i = 0; i < 16; i++) {
    const result = await page.request.post('/api/leads', {
      data: {
        name: `합성페이지배정${i}`,
        phone: `010000062${String(i).padStart(2, '0')}`,
      },
    });
    expect(result.status()).toBe(201);
  }
  await page.goto('/assignments?search=합성페이지배정');
  await page.getByLabel('현재 페이지 고객 전체 선택').check();
  await expect(page.getByText('15명 선택', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '다음', exact: true }).click();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.getByLabel('현재 페이지 고객 전체 선택').check();
  await expect(page.getByText('16명 선택', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '담당자 배정', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '담당자 배정' });
  await dialog.getByRole('checkbox', { name: /합성배정직원 담당/ }).check();
  await expect(dialog).toContainText('배정 후 기록 없음 0명');
  await expect(dialog.getByLabel('배정 예정')).toContainText('합성배정직원: 16명');
  await dialog.getByRole('checkbox', { name: /합성배정직원둘/ }).check();
  await expect(dialog.getByLabel('배정 예정')).toContainText('합성배정직원: 8명');
  await expect(dialog.getByLabel('배정 예정')).toContainText('합성배정직원둘: 8명');
  await page.screenshot({ path: testInfo.outputPath('assignment-preview.png'), fullPage: true });
  await dialog.getByRole('button', { name: '16명 배정하기' }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole('status')).toContainText('16명의 고객을 배정했습니다');
});
