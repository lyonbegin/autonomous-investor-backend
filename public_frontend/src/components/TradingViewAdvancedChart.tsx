import {useEffect,useRef} from 'react';

const SCRIPT='https://widgets.tradingview-widget.com/w/en/tv-advanced-chart.js';

export function TradingViewAdvancedChart({symbol,interval}:{symbol:string;interval:string}){
  const host=useRef<HTMLDivElement>(null);

  useEffect(()=>{
    let script=document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT}"]`);
    if(!script){
      script=document.createElement('script');
      script.type='module';
      script.src=SCRIPT;
      document.head.appendChild(script);
    }

    const mount=()=>{
      if(!host.current)return;
      host.current.innerHTML='';
      const chart=document.createElement('tv-advanced-chart');
      chart.setAttribute('symbol',symbol||'NASDAQ:AAPL');
      chart.setAttribute('interval',interval||'1D');
      chart.setAttribute('timezone','Asia/Seoul');
      chart.setAttribute('theme','light');
      chart.setAttribute('locale','kr');
      chart.setAttribute('autosize','');
      chart.setAttribute('allow-symbol-change','true');
      chart.setAttribute('show-drawing-toolbar','true');
      chart.setAttribute('show-date-ranges','true');
      chart.setAttribute('show-details','true');
      chart.setAttribute('show-hotlist','true');
      chart.style.display='block';
      chart.style.width='100%';
      chart.style.height='100%';
      host.current.appendChild(chart);
    };

    // Module registration is async. Creating the custom element before registration is valid,
    // and it upgrades automatically once the module is loaded.
    mount();
    return()=>{if(host.current)host.current.innerHTML=''};
  },[symbol,interval]);

  return <div ref={host} className="tv-advanced-chart-host"/>;
}
