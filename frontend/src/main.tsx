/**
 * 🚨 [AI 개발 규칙: ENTRY POINT PROTECTED]
 * ─────────────────────────────────────────────────────────────
 * 1. 이 파일은 반드시 <App /> 컴포넌트를 최상위로 렌더링해야 함.
 * 2. 특정 페이지를 직접 render()에 꽂지 마시오 — 라우팅은 App 내부에서만.
 * 3. BrowserRouter 설정 및 App 호출 구조 변경 금지.
 * ─────────────────────────────────────────────────────────────
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
