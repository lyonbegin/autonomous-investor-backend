import React from 'react';
import {createRoot} from 'react-dom/client';
import InvestmentStudio from './InvestmentStudio';
import '@xyflow/react/dist/style.css';
import './style.css';
const root=document.getElementById('root');
if(!root)throw new Error('Root element missing');
createRoot(root).render(<React.StrictMode><InvestmentStudio/></React.StrictMode>);
