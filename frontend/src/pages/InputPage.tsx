/**
 * 조건 입력 화면 — 업종, 브랜드, 예산, 위치 선택 → 시뮬레이션 실행
 */

function InputPage() {
  // TODO: 업종 선택 (카페/음식점/편의점)
  // TODO: 브랜드명 입력
  // TODO: 대상 동 선택 (드롭다운 — 마포구 16개 동)
  // TODO: 기존 매장 정보 입력 (동적 추가/삭제)
  // TODO: 초기 투자금 입력
  // TODO: 월 임대료 입력 (0이면 자동 추정)
  // TODO: 시나리오 선택 (체크박스: base, competitor_entry, rent_increase 등)
  // TODO: 시뮬레이션 실행 버튼 → POST /api/simulate

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">시뮬레이션 조건 입력</h2>
      <p className="mt-2 text-gray-600">
        시뮬레이션 조건을 입력하고 실행 버튼을 누르세요.
      </p>

      <div className="mt-8 max-w-2xl space-y-6">
        {/* TODO: 폼 구현 */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-700 text-sm">
          조건 입력 폼이 여기에 구현됩니다.
        </div>
      </div>
    </div>
  );
}

export default InputPage;
