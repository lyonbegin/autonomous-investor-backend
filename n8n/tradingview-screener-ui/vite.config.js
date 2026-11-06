import{defineConfig}from'vite';
import fs from'node:fs';
export default defineConfig({
  plugins:[{
    name:'tradingview-public-screener-relay',
    configureServer(server){
      server.middlewares.use('/api/scan',async(req,res)=>{
        res.setHeader('Content-Type','application/json; charset=utf-8');
        if(req.method!=='POST'){res.statusCode=405;res.end(JSON.stringify({error:'POST required'}));return;}
        let body='';
        for await(const chunk of req){body+=chunk.toString();if(body.length>800000){res.statusCode=413;res.end(JSON.stringify({error:'body too large'}));return;}}
        let incoming;try{incoming=JSON.parse(body);}catch{res.statusCode=400;res.end('{"error":"bad JSON"}');return;}
        const code=String(incoming.market||'').toLowerCase();
        const kind=String(incoming.kind||'').toLowerCase();
        const allowed=new Set(('america argentina australia austria bahrain bangladesh belgium bulgaria brazil canada chile china colombia croatia cyprus czech denmark egypt estonia finland france germany greece hongkong hungary iceland india indonesia ireland israel italy japan kenya kuwait latvia lithuania luxembourg malaysia mexico morocco netherlands newzealand nigeria norway pakistan peru philippines poland portugal qatar romania russia ksa serbia singapore slovakia slovenia rsa korea spain srilanka sweden switzerland taiwan thailand tunisia turkey uae uk venezuela vietnam bond coin crypto').split(' '));
        if(!allowed.has(code)||!['stock','etf','bond','coin','crypto'].includes(kind)){res.statusCode=400;res.end(JSON.stringify({error:'Unsupported market/product'}));return;}
        const endpoint='https://scanner.tradingview.com/'+code+'/scan?label-product=screener-'+kind;
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