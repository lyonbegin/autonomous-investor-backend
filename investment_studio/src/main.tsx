import React from 'react';
import {createRoot} from 'react-dom/client';
import Workbench from './Workbench';
import '@xyflow/react/dist/style.css';
import './style.css';
import './scenario.css';
const root=document.getElementById('root');
if(!root)throw new Error('Root element missing');
createRoot(root).render(<React.StrictMode><Workbench/></React.StrictMode>);
