import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import '@fontsource-variable/inter';
import './index.css';
import App from './App';
import { ServerProvider } from './hooks/useServer';
import { ToastProvider } from './components/ui/Toast';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ServerProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </ServerProvider>
    </BrowserRouter>
  </StrictMode>,
);
