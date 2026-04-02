/**
 * React 앱 진입점 — DOM 마운트 + BrowserRouter 래핑
 *
 * index.html의 #root에 React 앱을 마운트.
 * BrowserRouter로 클라이언트 사이드 라우팅 활성화.
 * Tailwind CSS는 index.css를 통해 로드.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
