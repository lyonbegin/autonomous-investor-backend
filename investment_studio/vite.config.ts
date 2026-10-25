import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
/** Backend-for-frontend development proxy. Keep the token out of VITE_* vars. */
export default defineConfig({
  plugins:[react()],
  server:{
    port:5177,
    proxy:{
      '/studio-api':{
        target:process.env.INVESTMENT_STUDIO_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin:true,
        rewrite:path=>path.replace(/^\/studio-api/,''),
        configure:proxy=>{
          proxy.on('proxyReq',proxyReq=>{
            const token=process.env.INVESTMENT_STUDIO_API_TOKEN;
            if(token) proxyReq.setHeader('Authorization','Bearer '+token);
          });
        }
      }
    }
  }
});
