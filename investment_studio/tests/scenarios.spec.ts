import {test,expect} from '@playwright/test';

test('운영 시나리오 10개를 클릭하고 각 실행 단계를 확인한다',async({page})=>{
  await page.goto('/');
  await expect(page.getByText('운영 시나리오 검사 센터')).toBeVisible();
  const options=page.locator('.scenario-menu button');
  await expect(options).toHaveCount(10,{timeout:15000});
  await expect(page.getByLabel('실행 엔진 선택')).toHaveValue('direct');
  await page.getByLabel('실행 속도').selectOption('0');
  for(let index=0;index<10;index++){
    await options.nth(index).click();
    await page.locator('.scenario-toolbar button.run').click();
    await expect(page.locator('.scenario-progress')).toContainText(/100(?:\\.0)?%/,{timeout:18000});
    await expect(page.locator('.scenario-progress')).toContainText('COMPLETED');
    const events=page.locator('.scenario-steps .step.success');
    await expect(events.first()).toBeVisible();
    await page.locator('.scenario-steps .step').first().click();
    await expect(page.locator('.scenario-inspector')).toContainText('입력');
    await expect(page.locator('.scenario-inspector')).toContainText('출력');
    await expect(page.locator('.scenario-inspector')).toContainText('다음 전달');
  }
  await page.screenshot({path:'test-results/ten-scenarios-completed.png',fullPage:true});
});

test('실행 도중 각 독립 플로우가 활성화된다',async({page})=>{
  await page.goto('/');
  await expect(page.locator('.scenario-menu button')).toHaveCount(10);
  await page.getByLabel('실행 속도').selectOption('700');
  await page.locator('.scenario-menu button').nth(4).click();
  await page.locator('.scenario-toolbar button.run').click();
  await expect(page.locator('.scenario-steps .step.running')).toBeVisible({timeout:8000});
  await page.screenshot({path:'test-results/scenario-in-progress.png',fullPage:true});
  await expect(page.locator('.scenario-progress')).toContainText(/100(?:\\.0)?%/,{timeout:30000});
  await expect(page.locator('.scenario-flows .flow.success').first()).toBeVisible();
});
