const $=id=>document.getElementById(id);

const INVESTMENT_ADMIN_ORIGIN='https://investment-n8n-native-editor-production.up.railway.app';
window.addEventListener('message',e=>{
 if(e.origin!==INVESTMENT_ADMIN_ORIGIN||e.source!==window.opener||e.data?.type!=='AUTONOMOUS_PINE_IMPORT')return;
 const code=e.data?.pine_code;
 if(typeof code!=='string'||!code.trim()||new TextEncoder().encode(code).length>512*1024)return;
 $('pine').value=code;
 $('sourceUrl').value=typeof e.data.source_url==='string'&&/^https:\/\/(?:www\.|kr\.)?tradingview\.com\/script\/[A-Za-z0-9]{8}\/?$/.test(e.data.source_url)?e.data.source_url:'';
 $('csv').value='';$('screenshot').value='';
 csvText='';screenshotData='';
 $('csvInfo').textContent='실제 TradingView OHLC·플롯 CSV를 업로드하세요';
 $('screenshotInfo').textContent='원본 TradingView 차트 캡처를 업로드하세요';
 $('leftChart').innerHTML='<div class="noChart">원본 Pine 코드를 불러왔습니다. 실제 TradingView 전략 적용 이미지가 아직 없습니다.</div>';
 $('leftBadge').textContent='원본 이미지 미제공';
 $('symbol').value='';
 $('timeframe').value='';
 updateOverlay();
 setStatus('저장된 Pine 원본 전달 완료 · 실제 TradingView 차트·CSV·종목·시간봉을 입력하고 수치 검증하세요');
});
if(window.opener){
 try{window.opener.postMessage({type:'PARITY_READY'},INVESTMENT_ADMIN_ORIGIN);}
 catch(e){console.warn('Admin-to-parity handshake unavailable',e);}
}

let csvText='',screenshotData='';
function setStatus(s,state='pending'){$('status').textContent=s;$('status').dataset.state=state;}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function updateOverlay(){
  const source=$('leftChart').querySelector('img');
  const python=$('rightChart').querySelector('img');
  const both=Boolean(source&&python);
  $('overlayTradingView').hidden=!both;$('overlayPython').hidden=!both;
  $('overlayPlaceholder').hidden=both;
  if(!both)return;
  $('overlayTradingView').src=source.src;
  $('overlayPython').src=python.src;
  const alpha=Number($('opacity').value)/100;
  $('opacityValue').textContent=Math.round(alpha*100)+'%';
  $('overlayPython').style.opacity=String(alpha);
  $('overlayPython').style.transform='translate('+Number($('shiftX').value)+'px,'+Number($('shiftY').value)+'px)';
}
for(const id of ['opacity','shiftX','shiftY'])$(id).addEventListener('input',updateOverlay);
$('csv').addEventListener('change',async e=>{
 const f=e.target.files[0];csvText=f?await f.text():'';
 $('csvInfo').textContent=f?f.name+' · '+csvText.length+'자':'CSV 미선택';
});
$('screenshot').addEventListener('change',async e=>{
 const f=e.target.files[0];screenshotData='';
 if(!f){$('screenshotInfo').textContent='이미지 미선택';return;}
 if(f.size>2400000||!['image/png','image/jpeg'].includes(f.type)){
   alert('PNG/JPEG만 최대 2.4MB까지 지원합니다.');e.target.value='';return;
 }
 screenshotData=await new Promise((resolve,reject)=>{
   const reader=new FileReader();reader.onload=()=>resolve(reader.result);
   reader.onerror=()=>reject(new Error('이미지 읽기 오류'));reader.readAsDataURL(f);
 });
 $('screenshotInfo').textContent=f.name+' · '+Math.round(f.size/1024)+'KB';
 const img=document.createElement('img');img.src=screenshotData;img.alt='TradingView 원본 차트 캡처';
 $('leftChart').replaceChildren(img);$('leftBadge').textContent='사용자 제공 TV 원본';updateOverlay();
});
$('demo').addEventListener('click',()=>{
 $('sourceUrl').value='';$('symbol').value='SYNTHETIC:DEMO';$('timeframe').value='1D';
 $('pine').value=[
  '//@version=6','strategy("MA crossover demonstration", overlay=true)',
  'fastLength = input.int(5, "Fast length")','slowLength = input.int(12, "Slow length")',
  'fastMA = ta.sma(close, fastLength)','slowMA = ta.ema(close, slowLength)',
  'longCondition = ta.crossover(fastMA, slowMA)',
  'shortCondition = ta.crossunder(fastMA, slowMA)',
  'if (longCondition)','    strategy.entry("Long", strategy.long)',
  'if (shortCondition)','    strategy.entry("Short", strategy.short)',
  'plot(fastMA, title="Fast")','plot(slowMA, title="Slow")'].join('\n');
 const rows=['time,open,high,low,close,volume'];
 for(let i=0;i<110;i++){
  const base=100+Math.sin(i*.22)*7+Math.sin(i*.075)*13+i*.09;
  const open=base-.6,close=base+Math.sin(i*.65),high=Math.max(open,close)+1.5,low=Math.min(open,close)-1.5;
  rows.push(['2026-BAR-'+String(i+1).padStart(3,'0'),open.toFixed(4),high.toFixed(4),low.toFixed(4),close.toFixed(4),1000].join(','));
 }
 csvText=rows.join('\n');screenshotData='';
 $('csv').value='';$('screenshot').value='';
 $('csvInfo').textContent='합성 110개 캔들 · TradingView 데이터 아님';
 $('screenshotInfo').textContent='캡처 미제공';
 $('leftChart').innerHTML='<div class="noChart">합성 예제입니다. 진짜 TradingView 원본 차트는 제공되지 않았습니다.</div>';
 $('leftBadge').textContent='원본 미제공';$('columns').value='{}';updateOverlay();
 setStatus('예제 로드 · 실제 1차 검증 불가');
});
$('run').addEventListener('click',async()=>{
 $('run').disabled=true;setStatus('Python 계산·렌더링 중');
 try{
  const payload={source_url:$('sourceUrl').value.trim(),symbol:$('symbol').value.trim(),
   timeframe:$('timeframe').value.trim(),pine_code:$('pine').value,
   csv_text:csvText,screenshot_data_url:screenshotData,
   columns:JSON.parse($('columns').value||'{}')};
  const response=await fetch('/api/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const result=await response.json();
  if(!response.ok)throw Error(result.error||'HTTP '+response.status);
  const img=document.createElement('img');img.src=result.python_chart_url;
  img.alt='동일 CSV로 Python이 생성한 SVG 전략 차트';
  $('rightChart').replaceChildren(img);$('rightBadge').textContent='Python 차트 · '+result.bars+'봉';updateOverlay();
  $('numeric').textContent=result.numeric_match?'수치 일치':'TV 기준값 부족 또는 불일치';
  $('visual').textContent=result.reference_screenshot_url?'원본 이미지 수동 검토 대기':'TV 원본 캡처 미제공';
  const label={
   REFERENCE_COLUMNS_REQUIRED:'미완료 · TV 플롯 출력 CSV 필요',
   NUMERIC_MISMATCH:'불합격 · 수치 불일치',
   NUMERIC_MATCH_VISUAL_REVIEW_REQUIRED:'수치 일치 · 이미지 비교 대기',
   TRADINGVIEW_SCREENSHOT_REQUIRED:'차트 이미지 미제공'
  }[result.status]||result.status;
  setStatus(label,result.status==='NUMERIC_MISMATCH'?'bad':'pending');
  $('comparison').innerHTML=result.comparison.map(x=>'<tr><td>'+esc(x.variable)+'</td><td>'+esc(x.column||'미지정')+
    '</td><td>'+esc(x.status)+'</td><td>'+esc(x.compared_bars||0)+'</td><td>'+esc(x.mismatch_count||0)+'</td></tr>').join('');
  $('runLinks').innerHTML='실행 ID: <code>'+esc(result.run_id)+'</code> · <a href="'+result.details_url+
    '" target="_blank" rel="noopener">결과 JSON</a> · <a href="'+result.trace_url+
    '" target="_blank" rel="noopener">노드 입출력 로그</a> · <a href="'+result.python_chart_url+
    '" target="_blank" rel="noopener">Python SVG</a> · <a href="'+result.python_code_url+'" target="_blank" rel="noopener">변환된 Python 코드</a>';
  const trace=await(await fetch(result.trace_url)).json();
  $('trace').textContent=JSON.stringify(trace,null,2);
  $('steps').innerHTML=trace.events.map(x=>'<div class="step '+(x.status==='DONE'?'ok':'pending')+
    '"><b>'+esc(x.node)+'</b><div>'+esc(x.status)+'</div></div>').join('');
  const query=new URLSearchParams(location.search);query.set('run',result.run_id);
  history.replaceState(null,'','/?'+query.toString());
 }catch(err){setStatus('실행 실패 · '+err.message,'bad');$('numeric').textContent='검증 불가';$('trace').textContent=String(err);}
 finally{$('run').disabled=false;}
});
(async()=>{
 const runId=new URLSearchParams(location.search).get('run');
 if(!runId||!(/^[a-f0-9]{24}$/.test(runId)))return;
 try{
  const response=await fetch('/api/runs/'+runId);if(!response.ok)return;
  const data=await response.json();
  $('sourceUrl').value=data.source_url;$('symbol').value=data.symbol;$('timeframe').value=data.timeframe;
  if(data.reference_screenshot_url){
    const i=document.createElement('img');i.src=data.reference_screenshot_url;i.alt='저장된 TV 원본';
    $('leftChart').replaceChildren(i);$('leftBadge').textContent='저장된 TV 원본';
  }
  const i=document.createElement('img');i.src=data.python_chart_url;i.alt='기존 Python SVG';
  $('rightChart').replaceChildren(i);$('rightBadge').textContent='기존 Python 차트';updateOverlay();
  $('numeric').textContent=data.numeric_match?'수치 일치':'기준자료 부족/불일치';
  $('visual').textContent='이미지 육안 검토 필요';setStatus(data.status);
  $('comparison').innerHTML=(data.comparison||[]).map(x=>'<tr><td>'+esc(x.variable)+'</td><td>'+
     esc(x.column||'미지정')+'</td><td>'+esc(x.status)+'</td><td>'+
     esc(x.compared_bars||0)+'</td><td>'+esc(x.mismatch_count||0)+'</td></tr>').join('');
  $('runLinks').innerHTML='기존 실행 ID: '+esc(runId)+' · <a href="'+data.trace_url+
    '" target="_blank" rel="noopener">전체 노드 로그</a>';
  const t=await(await fetch(data.trace_url)).json();
  $('trace').textContent=JSON.stringify(t,null,2);
  $('steps').innerHTML=t.events.map(x=>'<div class="step '+(x.status==='DONE'?'ok':'pending')+
    '"><b>'+esc(x.node)+'</b><div>'+esc(x.status)+'</div></div>').join('');
 }catch(e){console.error('Saved run load failed',e);}
})();