import http from 'node:http';
import path from 'node:path';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url)),dist=path.join(root,'dist');
const PORT=Number(process.env.PORT||4173);
const markets=new Set(('america argentina australia austria bahrain bangladesh belgium bulgaria brazil canada chile china colombia croatia cyprus czech denmark egypt estonia finland france germany greece hongkong hungary iceland india indonesia ireland israel italy japan kenya kuwait latvia lithuania luxembourg malaysia mexico morocco netherlands newzealand nigeria norway pakistan peru philippines poland portugal qatar romania russia ksa serbia singapore slovakia slovenia rsa korea spain srilanka sweden switzerland taiwan thailand tunisia turkey uae uk venezuela vietnam bond coin crypto').split(' '));
const contentType={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.woff2':'font/woff2'};
const json=(res,status,body)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(body))};
async function scan(req,res){
 let raw='';try{for await(const chunk of req){raw+=chunk.toString();if(raw.length>800000)return json(res,413,{error:'Too large'})}}catch(e){return json(res,400,{error:'Read failed'})}
 let body;try{body=JSON.parse(raw)}catch{return json(res,400,{error:'Invalid JSON'})}
 const market=String(body.market||'').toLowerCase(),kind=String(body.kind||'').toLowerCase(),product=String(body.product||kind).toLowerCase();
 if(!markets.has(market)||!['stock','etf','bond','coin','crypto'].includes(kind)||!['stock','etf','bond','coin','cex','dex'].includes(product))return json(res,400,{error:'Unknown product/market'});
 const label=product==='cex'?'crypto-cex':product==='dex'?'crypto-dex':kind;
 const endpoint='https://scanner.tradingview.com/'+market+'/scan?label-product=screener-'+label;
 try{
   const upstream=await fetch(endpoint,{method:'POST',
      headers:{'Accept':'application/json','Content-Type':'application/json','Origin':'https://kr.tradingview.com','Referer':'https://kr.tradingview.com/'},
      body:JSON.stringify(body.payload||{}),signal:AbortSignal.timeout(20000)});
   const result=await upstream.text();
   res.writeHead(upstream.status,{'Content-Type':upstream.headers.get('content-type')||'application/json','Cache-Control':'private, max-age=10'});res.end(result);
 }catch(e){json(res,502,{error:'Upstream unavailable',detail:String(e).slice(0,180)})}
}
const server=http.createServer(async(req,res)=>{
 try{
  const route=new URL(req.url,'http://localhost').pathname;
  if(route==='/health')return json(res,200,{status:'ok',build:'tradingview-seven-screener-parity'});
  if(route==='/api/scan')return req.method==='POST'?scan(req,res):json(res,405,{error:'POST only'});
  if(req.method!=='GET'&&req.method!=='HEAD')return json(res,405,{error:'GET only'});
  let relative=decodeURIComponent(route).replace(/^\/+/,'');
  if(!relative||route.endsWith('/')||!path.extname(relative))relative='index.html';
  const resolved=path.resolve(dist,relative);
  if(!resolved.startsWith(dist+path.sep)&&resolved!==path.join(dist,'index.html'))return json(res,400,{error:'Bad path'});
  let content;
  try{content=await fs.readFile(resolved)}catch{
   if(path.extname(relative))return json(res,404,{error:'Not found'});
   content=await fs.readFile(path.join(dist,'index.html'));
  }
  const ext=path.extname(resolved)||'.html';
  res.writeHead(200,{'Content-Type':contentType[ext]||'application/octet-stream','Cache-Control':ext==='.html'?'no-cache':'public, max-age=300'});
  res.end(req.method==='HEAD'?undefined:content);
 }catch(e){json(res,500,{error:'Server error',detail:String(e).slice(0,150)})}
});
server.listen(PORT,'0.0.0.0',()=>console.log('Screener UI listening',PORT));
