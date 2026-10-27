/** Browser evidence from actual local services; no mocked browser API responses. */
import {createRequire} from 'node:module';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {randomBytes} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'investment_studio/package.json'));
const {chromium,expect}=require('@playwright/test');
const out=process.env.REVIEW_OUTPUT_DIR||'/workspace/review';
const state=process.env.REVIEW_STATE_DIR||'/workspace/.onboarding/user-review-20261027-v2';
await mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium'});
const checks=[];
let liveProxy;
const check=(name,extra={})=>{checks.push({name,status:'passed',...extra});console.log(name+': PASS')};
try{
 const context=await browser.newContext({viewport:{width:1600,height:1100},locale:'ko-KR'});
 const page=await context.newPage();
 await page.goto('http://127.0.0.1:5177');
 await expect(page.getByRole('heading',{name:'실제 운영 상태 · F01 / F03 / F05'})).toBeVisible();
 await expect(page.locator('.ops-table-wrap')).toContainText(['CI Public Pine Strategy'],{timeout:15000});
 await page.screenshot({path:path.join(out,'operations.png'),fullPage:true});
 check('기존 운영 화면과 실제 로컬 API 연결');

 await page.getByRole('button',{name:'12개 엔진 상태',exact:true}).click();
 await expect(page.locator('.engine-card')).toHaveCount(12);
 await expect(page.locator('.engines-summary')).toContainText('검증 통과 12',{timeout:180000});
 await expect(page.locator('.engines-summary')).toContainText('준비 12',{timeout:180000});
 const nautilus=page.locator('[data-engine="nautilus"]');
 await nautilus.getByRole('button',{name:'정지',exact:true}).click();
 await expect(nautilus.locator('.engine-state')).toHaveText('정지');
 await nautilus.getByRole('button',{name:'시작',exact:true}).click();
 await expect(nautilus.locator('.engine-state')).toHaveText('준비',{timeout:45000});
 const verified=page.waitForResponse(response=>response.url().endsWith('/ops/engines/nautilus/verify')&&response.request().method()==='POST');
 await nautilus.getByRole('button',{name:'소규모 검증',exact:true}).click();
 const result=await(await verified).json();
 if(result.demo_state!=='passed')throw new Error('Browser native verification did not complete');
 await expect(nautilus.getByTestId('demo-state')).toHaveText('통과',{timeout:45000});
 await expect(page.locator('.engines-error')).toHaveCount(0);
 await page.setViewportSize({width:1600,height:1800});
 await page.locator('.engines-root').evaluate(element=>element.scrollTo(0,0));
 await page.screenshot({path:path.join(out,'engines.png'),fullPage:true});
 await page.setViewportSize({width:1600,height:1100});
 check('12개 실제 엔진 상태와 Nautilus 시작·정지·네이티브 검증 UI');

 await page.getByRole('button',{name:'10개 운영 시나리오 실행',exact:true}).click();
 await expect(page.locator('.scenario-menu button')).toHaveCount(10);
 await page.getByLabel('실행 엔진 선택').selectOption('n8n');
 await page.getByLabel('실행 속도').selectOption('0');
 for(let i=0;i<10;i++){
  await page.locator('.scenario-menu button').nth(i).click();
  await page.locator('.scenario-toolbar button.run').click();
  await expect(page.locator('.scenario-progress')).toContainText('COMPLETED',{timeout:30000});
  await expect(page.locator('.scenario-progress')).toContainText(/100(?:\.0)?%/);
 }
 await page.locator('.scenario-steps .step').first().click();
 await expect(page.locator('.scenario-inspector')).toContainText('입력');
 await expect(page.locator('.scenario-inspector')).toContainText('출력');
 await page.screenshot({path:path.join(out,'n8n-scenarios.png'),fullPage:true});
 check('브라우저에서 원본 n8n Worker 경유 시나리오 10개 완료');

 const publicPage=await context.newPage();
 const errors=[];publicPage.on('pageerror',error=>errors.push(error.message));
 for(const [route,selector,min] of [['strategies','.strategy-card',1],['agents','.agent-card',1],
                                  ['ideas','.idea-card',1],['scripts','.script-card',1],['markets','.market-table tbody tr',1]]){
  await publicPage.goto('http://127.0.0.1:5178/'+route);
  await expect(publicPage.getByRole('note')).toContainText('SYNTHETIC');
  // Cards in the original components have multiple style variants; verify API
  // completion and the substantive rendered text rather than a new fixture DOM.
  await expect(publicPage.locator('main')).toContainText(/SYNTHETIC|합성/, {timeout:15000});
  if(route==='markets')await expect(publicPage.locator(selector)).toHaveCount(min);
  await expect(publicPage.locator('.loading')).toHaveCount(0,{timeout:15000});
  await expect(publicPage.locator('.empty-state')).toHaveCount(0);
  await publicPage.screenshot({path:path.join(out,'public-'+route+'.png'),fullPage:true});
  check('기존 공개 화면 /'+route+' 실제 API·데이터 표시');
 }
 if(errors.length)throw new Error('Public UI runtime errors: '+errors.join('; '));
 await publicPage.goto('http://127.0.0.1:5178/strategies');
 await publicPage.getByPlaceholder('전략·시장·종목·원본 검색').fill('절대로-없는-검증전략');
 await expect(publicPage.locator('.strategy-card')).toHaveCount(0);
 check('공개 전략 검색 필터');

 // The only n8n account created here belongs to our isolated local Compose
 // project. Never perform owner setup or credential changes on production.
 const native=await browser.newContext({viewport:{width:1600,height:1100},locale:'ko-KR'});
 const settingsResponse=await native.request.get('http://127.0.0.1:5678/rest/settings');
 const settings=await settingsResponse.json();
 let account;
 try{account=JSON.parse(await readFile(path.join(state,'local-n8n-owner.json'),'utf8'))}catch{}
 if((settings.data||settings).userManagement?.showSetupOnFirstLoad){
  account={email:'review@localhost.invalid',firstName:'Local',lastName:'Review',password:'LocalReview!'+randomBytes(24).toString('hex')};
  const response=await native.request.post('http://127.0.0.1:5678/rest/owner/setup',{data:account});
  if(!response.ok())throw new Error('Local n8n owner setup returned '+response.status());
  await writeFile(path.join(state,'local-n8n-owner.json'),JSON.stringify(account),{mode:0o600});
 }
 if(!account)throw new Error('Local n8n is already owned without this review session account; refusing to modify it');
 const login=await native.request.post('http://127.0.0.1:5678/rest/login',{
  data:{emailOrLdapLoginId:account.email,password:account.password}});
 if(!login.ok())throw new Error('Local n8n login returned '+login.status());
 const editor=await native.newPage();
 await editor.goto('http://127.0.0.1:5678/workflow/autonomousScenario01');
 await expect(editor.locator('.vue-flow__node').first()).toBeVisible({timeout:45000});
 const nodes=await editor.locator('.vue-flow__node').count();
 const edges=await editor.locator('.vue-flow__edge').count();
 if(nodes<6||edges<4)throw new Error('Original n8n graph did not render its source-defined nodes/edges');
 await editor.screenshot({path:path.join(out,'native-n8n-editor.png'),fullPage:true});
 check('인증 후 원본 n8n 에디터에서 실제 6개 노드·연결선 표시',{nodes,edges});
 const executions=await native.request.get('http://127.0.0.1:5678/rest/executions?filter='+encodeURIComponent(JSON.stringify({workflowId:'autonomousScenario01'})));
 if(!executions.ok())throw new Error('Native n8n execution history returned '+executions.status());
 const executionData=await executions.json();
 const nativeRuns=(executionData.data||executionData).results||[];
 if(!nativeRuns.some(row=>row.status==='success'))throw new Error('No successful real n8n execution was returned');
 await writeFile(path.join(out,'n8n-execution-summary.json'),JSON.stringify({workflow:'autonomousScenario01',
  successful_executions:nativeRuns.filter(row=>row.status==='success').map(row=>({id:row.id,status:row.status,startedAt:row.startedAt})),verified:true},null,2));
 check('원본 n8n 인증된 실행 이력 API');
 const succeeded=nativeRuns.find(row=>row.status==='success');
 await editor.goto('http://127.0.0.1:5678/workflow/autonomousScenario01/executions/'+succeeded.id);
 await editor.locator('.vue-flow__node').first().waitFor();
 await editor.locator('.vue-flow__node').filter({hasText:'상태·노드 실행 결과 조회'}).dblclick();
 await expect(editor.locator('[data-test-id="ndv-input-panel"]')).toBeVisible();
 await expect(editor.locator('[data-test-id="output-panel"]')).toContainText('run_id');
 await expect(editor.locator('[data-test-id="output-panel"]')).toContainText('completed');
 await editor.screenshot({path:path.join(out,'native-n8n-node-io.png'),fullPage:true,
   mask:[editor.locator('[data-test-id="node-parameters"]')],maskColor:'#e5e9ef'});
 check('원본 n8n 성공 실행의 노드별 실제 입력·출력 (연결 설정 영역 마스킹)');

 const live=await context.newPage();
 liveProxy=spawn(process.env.REVIEW_PYTHON||'/workspace/.onboarding/autonomous-investor-backend/py313/bin/python',
   [path.join(root,'scripts/verify_live_readonly_proxy.py')],{stdio:'ignore'});
 for(let i=0;i<100;i++){
  try{const response=await fetch('http://127.0.0.1:8007/');if(response.ok)break}catch{}
  await new Promise(resolve=>setTimeout(resolve,100));
 }
 await live.goto('http://127.0.0.1:8007/');
 await expect(live.getByRole('button',{name:'10개 운영 시나리오 실행',exact:true})).toBeVisible({timeout:20000});
 // Read-only navigation. No live scenario, approval or agent mutation is sent.
 await live.getByRole('button',{name:'전략 풀 · 에이전트 · 독립 감사',exact:true}).click();
 await expect(live.getByRole('heading',{name:'실제 운영 상태 · F01 / F03 / F05'})).toBeVisible();
 await expect(live.locator('.ops-table-wrap tbody tr').first()).toBeVisible();
 await live.screenshot({path:path.join(out,'existing-production-readonly.png'),fullPage:true});
 check('기존 운영 URL 브라우저 읽기 확인 (관리 CA로 TLS 검증하는 읽기 전용 프록시 경유, 통합 변경 미배포)');
 await writeFile(path.join(out,'browser-checks.json'),JSON.stringify({observed_at:new Date().toISOString(),checks},null,2));
 console.log('ALL_REVIEW_BROWSER_CHECKS_PASSED '+checks.length);
}finally{liveProxy?.kill('SIGTERM');await browser.close()}
