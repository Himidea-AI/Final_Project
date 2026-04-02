/**
 * 동별 상세 리포트 — 12개월 매출 추이, 생존율, 레이더 차트
 */

function ReportView() {
  // TODO: 동 선택 드롭다운
  // TODO: 12개월 매출 추이 라인 차트 (Recharts)
  // TODO: 레이더 차트 (경쟁/유동인구/임대료/트렌드 등)
  // TODO: 생존 확률 게이지
  // TODO: AI 추천 의견 텍스트 블록

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">상세 분석 리포트</h2>
      <p className="mt-2 text-gray-600">
        시뮬레이션 실행 후 리포트가 표시됩니다.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6 h-64 flex items-center justify-center">
          <p className="text-gray-400">매출 추이 차트</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6 h-64 flex items-center justify-center">
          <p className="text-gray-400">레이더 차트</p>
        </div>
      </div>
    </div>
  );
}

export default ReportView;
