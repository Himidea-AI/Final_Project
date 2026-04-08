/**
 * 메인 앱 컴포넌트 — React Router 페이지 라우팅 설정
 */
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import InputPage from "./pages/InputPage";
import MapView from "./pages/MapView";
import ReportView from "./pages/ReportView";
import BepSimulator from "./pages/BepSimulator";
import Comparison from "./pages/Comparison";
import Cannibalization from "./pages/Cannibalization";
import { SimulationProvider } from "./contexts/SimulationContext";

function App() {
  return (
    <SimulationProvider>
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
    </SimulationProvider>
  );
}

export default App;
