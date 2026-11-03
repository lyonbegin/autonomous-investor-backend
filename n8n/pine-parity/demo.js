const el=id=>document.getElementById(id);
const fmt=x=>x===null||x===undefined?'—':Number(x).toFixed(5);
function chart(canvas, rows, keys) {
  const ctx=canvas.getContext('2d');
  const w=canvas.width,h=canvas.height,pad=34;
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle='#0b1828';ctx.fillRect(0,0,w,h);
  const all=rows.flatMap(r=>keys.map(k=>r[k])).filter(Number.isFinite);
  if(!all.length)throw Error('PYNECORE_PLOTS_MISSING');
  const low=Math.min(...all),high=Math.max(...all),spread=Math.max(high-low,0.00001);
  const y=v=>h-pad-(v-low)/spread*(h-pad*2);
  const x=i=>pad+(w-pad*2)*i/Math.max(1,rows.length-1);
  ctx.strokeStyle='#27415e';ctx.lineWidth=1;
  for(let i=0;i<5;i++){
    let yy=pad+(h-2*pad)*i/4;
    ctx.beginPath();ctx.moveTo(pad,yy);ctx.lineTo(w-pad,yy);ctx.stroke();
  }
  const colors={close:'#d2dfe9',Basis:'#4b9fff',Upper:'#fc9d72',Lower:'#54d4a9'};
  for(const key of keys){
    ctx.beginPath();ctx.strokeStyle=colors[key]||'#dbcdff';ctx.lineWidth=key==='close'?1.5:2;
    let segment=false;
    for(let i=0;i<rows.length;i++){
      const v=rows[i][key];
      if(!Number.isFinite(v)){segment=false;continue;}
      if(!segment)ctx.moveTo(x(i),y(v));else ctx.lineTo(x(i),y(v));
      segment=true;
    }
    ctx.stroke();
  }
  ctx.fillStyle='#91abc4';ctx.font='12px system-ui';
  ctx.fillText(high.toFixed(5),2,18);ctx.fillText(low.toFixed(5),2,h-6);
  ctx.fillText('과거',pad,h-6);ctx.fillText('최근',w-54,h-6);
  let lx=pad;
  for(const k of keys){ctx.fillStyle=colors[k]||'#dbcdff';ctx.fillText(k,lx,21);lx+=88;}
}
el('run').addEventListener('click',async()=>{
  el('run').disabled=true;
  el('status').textContent='실제 PyneCore 6.11.1에서 PyneSys 공개 시장 데이터를 실행 중…';
  try{
    const response=await fetch('/api/pynecore-demo',{cache:'no-store'});
    const r=await response.json();
    if(!response.ok)throw Error(r.error||'HTTP '+response.status);
    if(r.status!=='PYNECORE_REAL_MARKET_EXECUTED_TV_PARITY_PENDING'||
      r.market_data_is_synthetic!==false||r.tradingview_chart_validated!==false)
      throw Error('INVALID_DEMO_PROVENANCE_OR_STATUS');
    if(r.bar_count<900||r.strategy_closed_trades<1||r.chart.length<200)
      throw Error('REAL_STRATEGY_DATA_NOT_RETURNED');
    chart(el('market'),r.chart,['close']);
    chart(el('indicator'),r.chart,['close','Basis','Upper','Lower']);
    const tbody=el('trades');tbody.replaceChildren();
    for(const trade of r.strategy_trades.slice(-24).reverse()){
      const tr=document.createElement('tr');
      for(const val of [trade.close_bar_index,trade.direction,fmt(trade.entry_price),
        fmt(trade.exit_price),trade.profit?.toFixed(2)??'—']){
        const td=document.createElement('td');td.textContent=String(val);tr.append(td);
      }
      tbody.append(tr);
    }
    el('counts').textContent='시장 시간봉 '+r.bar_count.toLocaleString()+
      '개 · 종료 거래 '+r.strategy_closed_trades.toLocaleString()+
      '개 · 표시 차트봉 '+r.chart.length+'개';
    el('status').textContent='실제 PyneCore 실행 성공 · '+r.executed_at+
      ' · 신규 Pine 컴파일은 실시하지 않음';
    el('metadata').textContent='PyneCore '+r.pynecore_version+
      '\n원본: '+r.provenance_url+
      '\n라이선스: '+r.license+
      '\n종목: EURUSD 1h'+
      '\n데이터 SHA256: '+r.sha256['EURUSD_1h.csv']+
      '\nPython SHA256: '+r.sha256['sma_crossover.py']+
      '\nTV reference: missing · PAPER/LIVE disabled';
    window.__pynecoreDemoResult=r;
  }catch(e){
    el('status').textContent='실행 실패: '+e.message;
    el('metadata').textContent='';
  }finally{el('run').disabled=false;}
});
