/* Real headless Chromium test on the existing deployed parity-review page.
   Both CSVs are CI-generated SYNTHETIC references, with actual PyneCore output.
   No user scripts executed by this public page; no LIVE orders. */
const {chromium} = require('playwright');
const path = require('path');
const fs = require('fs');
const base = process.env.PARITY_TEST_BASE ||
  'https://investment-pine-parity-review-production.up.railway.app';
const evidence = process.env.INVESTMENT_DEMO_OUTPUT ||
  '/tmp/investment-pynecore-ci-evidence';
const ref = f => path.join(evidence, f);
const wait = ms => new Promise(resolve => setTimeout(resolve,ms));
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1480, height: 940}});
    const errors=[];
    page.on('pageerror', e=>errors.push(e.message));
    let response=null;
    for (let n=0; n<7; n++) {
      try {response=await page.goto(base+'/',{waitUntil:'domcontentloaded',timeout:30000});}
      catch(e) {if(n===6) throw e;}
      if(response?.status()===200) break;
      if(n===6) throw Error('LIVE_PARITY_SITE_NOT_HTTP_200');
      await wait(2500);
    }
    await page.locator('#keypointRun').waitFor({timeout:20000});
    await page.locator('#keypointTvCsv').setInputFiles(ref('reference_synthetic_mismatch.csv'));
    await page.locator('#keypointPyCsv').setInputFiles(ref('pynecore_actual_worker_output.csv'));
    await page.locator('#keypointRun').click();
    await page.waitForFunction(()=>document.getElementById('keypointStatus').textContent.includes('불일치 1개'),
      {timeout:30000});
    const mismatch=await page.locator('#keypointStatus').innerText();
    const table=await page.locator('#keypointRows').innerText();
    if(!mismatch.includes('20개')||!table.toLowerCase().includes('tv price'))
      throw Error('LIVE_MISMATCH_NOT_VISIBLE '+mismatch+' '+table.slice(0,400));
    await page.locator('#pynecore-keypoint-panel').screenshot({path:ref('live-pynecore-mismatch.png')});
    console.log('LIVE_CHROME_MISMATCH_PASS',mismatch);
    await page.locator('#keypointTvCsv').setInputFiles(ref('reference_synthetic_match.csv'));
    await page.locator('#keypointRun').click();
    await page.waitForFunction(()=>document.getElementById('keypointStatus').textContent.includes('불일치 0개'),
      {timeout:30000});
    const match=await page.locator('#keypointStatus').innerText();
    if(!match.includes('20개')||!match.includes('불충분'))
      throw Error('LIVE_UNVERIFIED_MATCH_NOT_LABELED '+match);
    if(errors.length) throw Error('BROWSER_JS_ERRORS '+JSON.stringify(errors));
    await page.locator('#pynecore-keypoint-panel').screenshot({path:ref('live-pynecore-match.png')});
    fs.writeFileSync(ref('live_browser_result.json'), JSON.stringify({
      source: 'SYNTHETIC_REFERENCE_WITH_ACTUAL_PYNECORE_OUTPUT',
      site: base, mismatchStatus: mismatch, matchStatus: match,
      liveOrdersEnabled: false, authenticatedTradingView: false
    },null,2));
    console.log('LIVE_CHROME_MATCH_PASS',match);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
