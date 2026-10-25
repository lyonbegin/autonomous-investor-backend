import {test,expect} from '@playwright/test';

test('F01 실제 HTTP 기반 전략 조회 → 검토 승인 → F03 PAPER 배정 → F05 치명적 감사 중지',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'실제 운영 상태 · F01 / F03 / F05'})).toBeVisible();
  await expect(page.locator('.ops-stats')).toContainText('0');

  // This Chromium test runs against the explicit CI-only mock HTTP upstream.
  await page.locator('.ops-task').nth(0).getByRole('button',{name:'F01 실행'}).click();
  await expect(page.locator('.ops-table-wrap tbody b').getByText('CI Public Pine Strategy')).toBeVisible({timeout:15000});
  await expect(page.getByText('CI protected Pine')).toBeVisible();
  await expect(page.locator('.ops-status.PENDING_REVIEW').first()).toBeVisible();
  await expect(page.locator('.ops-status.INELIGIBLE').first()).toBeVisible();

  await page.getByLabel('승인할 전략 버전').selectOption({index:1});
  await page.getByLabel('검토자').fill('ci-browser-reviewer');
  await page.getByLabel('검증 증거 참조').fill('CI_TEST_ATTESTATION_NOT_VALIDATED');
  await page.getByLabel('사용 라이선스 검토 완료').check();
  await page.getByLabel('Pine 변환·동등성 검증 완료').check();
  await page.getByLabel('독립 백테스트 검증 완료').check();
  await page.getByRole('button',{name:'증거와 함께 승인 기록'}).click();
  await expect(page.locator('.ops-status.APPROVED').first()).toBeVisible({timeout:12000});

  await page.getByLabel('신규 PAPER 에이전트 ID').fill('ci-chromium-agent');
  await page.getByRole('button',{name:'유휴 에이전트 등록'}).click();
  await expect(page.locator('.ops-table-wrap tbody b').getByText('ci-chromium-agent')).toBeVisible();

  await page.locator('.ops-task').nth(1).getByRole('button',{name:'F03 실행'}).click();
  await expect(page.locator('.ops-table-wrap').nth(1)).toContainText('ACTIVE',{timeout:12000});

  const assignments=await page.request.get('/studio-api/api/v1/ops/agents');
  expect(assignments.ok()).toBeTruthy();
  const data=await assignments.json();
  const item=data.active_assignments[0];
  expect(item.agent_id).toBe('ci-chromium-agent');
  expect(item.epoch).toBe(1);

  // No broker connection is present: this is an audit *observation*, not an order.
  const audit=await page.request.post('/studio-api/api/v1/ops/audit/observations',{data:{
    event_id:'CI-BROWSER-UNAPPROVED-ORDER-0001',event_type:'OrderSubmitted',
    assignment_id:item.assignment_id,strategy_version_id:item.version_id,
    epoch:item.epoch,payload:{risk_approved:false,client_order_id:'CI-NONEXECUTABLE'},
  }});
  expect(audit.ok()).toBeTruthy();
  const finding=await audit.json();
  expect(finding.assignment_state).toBe('HALTED');
  await expect(page.locator('.ops-table-wrap tbody b').getByText('unapproved_order')).toBeVisible({timeout:12000});
  await expect(page.locator('.ops-table-wrap').nth(1)).toContainText('HALTED');

  await page.screenshot({path:'test-results/f01-f03-f05-real-db-dashboard.png',fullPage:true});
});

test('F01 오류는 가짜 데이터로 교체하지 않는다',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'실제 운영 상태 · F01 / F03 / F05'})).toBeVisible();
  await expect(page.getByText(/브로커 연결 없음/)).toBeVisible();
  await expect(page.getByText(/승인은 검토자의 확인 기록/)).toBeVisible();
});
