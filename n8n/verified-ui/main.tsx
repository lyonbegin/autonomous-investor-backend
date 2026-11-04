import React from 'react';
import {createRoot} from 'react-dom/client';
import {VerifiedScriptsApp} from './VerifiedScriptsApp';
createRoot(document.getElementById('root')!).render(
 <React.StrictMode><VerifiedScriptsApp/></React.StrictMode>
);
