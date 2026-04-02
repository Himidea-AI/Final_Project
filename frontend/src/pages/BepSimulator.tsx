/**
 * 손익분기점 시뮬레이터 — 슬라이더 조정 → 실시간 BEP 계산
 */

function BepSimulator() {
  // TODO: 임대료 슬라이더 (range input)
  // TODO: 인건비 슬라이더
  // TODO: 예상 매출 슬라이더
  // TODO: 원가율 슬라이더
  // TODO: BEP 도달 개월 수 실시간 계산 표시
  // TODO: 누적 손익 차트 (Recharts BarChart + Line)

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">손익분기점 시뮬레이터</h2>
      <p className="mt-2 text-gray-600">
        슬라이더를 조정하여 손익분기점을 시뮬레이션합니다.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-8">
        <div className="space-y-6">
          {/* TODO: 슬라이더 UI */}
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-gray-400">슬라이더 컨트롤</p>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6 h-80 flex items-center justify-center">
          <p className="text-gray-400">누적 손익 차트</p>
        </div>
      </div>
    </div>
  );
}

export default BepSimulator;
