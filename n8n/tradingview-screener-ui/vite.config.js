import{defineConfig}from'vite';
import fs from'node:fs';
const ENUM_ALLOWED={stock:['index','sector','analyst_rating'],etf:['asset_class','focus','niche','holdings_region','brand','actively_managed','strategy','dividend_treatment','dividends_frequency','leverage','leveraged_flag','ucits_compliant_flag'],bond:['bond_issuer_type','bond_issuer','coupon_type_current','coupon_frequency','fundamental_currency_code','coupon_currency','exchange'],coin:['crypto_common_categories'],cex:['exchange','type','currency_id'],dex:['blockchain-id','exchange']};
export default defineConfig({
  plugins:[{
    name:'tradingview-public-screener-relay',
    configureServer(server){
      server.middlewares.use('/api/enum',async(req,res)=>{
        const q=new URL(req.url,'http://localhost').searchParams;
        const product=q.get('product'),id=q.get('id');
        res.setHeader('Content-Type','application/json; charset=utf-8');
        if(!ENUM_ALLOWED[product]?.includes(id)){res.statusCode=400;res.end('{"error":"product and valid id required"}');return;}
        const label=product==='cex'?'crypto-cex':product==='dex'?'crypto-dex':product;
        const endpoint='https://scanner.tradingview.com/enum/ordered?lang=ko&label-product=screener-'+label+'&id='+encodeURIComponent(id);
        try{const response=await fetch(endpoint,{headers:{Accept:'application/vnd.tv.orderedEnumValues.v1+json'},signal:AbortSignal.timeout(25000)});
          res.statusCode=response.status;res.end(await response.text());
        }catch(e){res.statusCode=502;res.end(JSON.stringify({error:'enum unavailable'}));}
      });
      server.middlewares.use('/api/scan',async(req,res)=>{
        res.setHeader('Content-Type','application/json; charset=utf-8');
        if(req.method!=='POST'){res.statusCode=405;res.end(JSON.stringify({error:'POST required'}));return;}
        let body='';
        for await(const chunk of req){body+=chunk.toString();if(body.length>800000){res.statusCode=413;res.end(JSON.stringify({error:'body too large'}));return;}}
        let incoming;try{incoming=JSON.parse(body);}catch{res.statusCode=400;res.end('{"error":"bad JSON"}');return;}
        const code=String(incoming.market||'').toLowerCase();
        const kind=String(incoming.kind||'').toLowerCase();
        const product=String(incoming.product||kind).toLowerCase();
        const allowed=new Set(('america argentina australia austria bahrain bangladesh belgium bulgaria brazil canada chile china colombia croatia cyprus czech denmark egypt estonia finland france germany greece hongkong hungary iceland india indonesia ireland israel italy japan kenya kuwait latvia lithuania luxembourg malaysia mexico morocco netherlands newzealand nigeria norway pakistan peru philippines poland portugal qatar romania russia ksa serbia singapore slovakia slovenia rsa korea spain srilanka sweden switzerland taiwan thailand tunisia turkey uae uk venezuela vietnam bond coin crypto').split(' '));
        if(!allowed.has(code)||!['stock','etf','bond','coin','crypto'].includes(kind)){res.statusCode=400;res.end(JSON.stringify({error:'Unsupported market/product'}));return;}
        const label=product==='cex'?'crypto-cex':product==='dex'?'crypto-dex':kind;
        const endpoint='https://scanner.tradingview.com/'+code+'/scan?label-product=screener-'+label;
        try{
          const remote=await fetch(endpoint,{method:'POST',headers:{
            'Content-Type':'application/json','Accept':'application/json',
            'Origin':'https://kr.tradingview.com','Referer':'https://kr.tradingview.com/'
          },body:JSON.stringify(incoming.payload||{}),signal:AbortSignal.timeout(18000)});
          const text=await remote.text();res.statusCode=remote.status;
          res.end(text);
        }catch(err){
          res.statusCode=502;res.end(JSON.stringify({error:'Upstream connection failed',detail:String(err).slice(0,200)}));
        }
      });
    }
  }],
  server:{host:'0.0.0.0',port:4173,strictPort:true},
  build:{target:'es2020'}
});