/**
 * 메인 앱 컴포넌트 — React Router 페이지 라우팅 설정
 *
 * 6개 페이지를 Layout(사이드바+헤더) 안에서 라우팅:
 *   /                  → InputPage      (조건 입력)
 *   /map               → MapView        (마포구 히트맵)
 *   /report            → ReportView     (상세 리포트)
 *   /bep               → BepSimulator   (손익분기점)
 *   /comparison        → Comparison     (동 vs 동 비교)
 *   /cannibalization   → Cannibalization (카니발리제이션)
 */
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import InputPage from "./pages/InputPage";
import MapView from "./pages/MapView";
import ReportView from "./pages/ReportView";
import BepSimulator from "./pages/BepSimulator";
import Comparison from "./pages/Comparison";
import Cannibalization from "./pages/Cannibalization";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<InputPage />} />
        <Route path="/map" element={<MapView />} />
        <Route path="/report" element={<ReportView />} />
        <Route path="/bep" element={<BepSimulator />} />
        <Route path="/comparison" element={<Comparison />} />
        <Route path="/cannibalization" element={<Cannibalization />} />
      </Routes>
    </Layout>
  );
}

export default App;
