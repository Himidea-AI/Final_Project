/**
 * 입지 적합도 점수 카드 — 동별 종합 점수 표시
 */

interface ScoreCardProps {
  district: string;
  score: number;
  revenue: number;
  bepMonths: number;
  survivalRate: number;
}

function ScoreCard({ district, score, revenue, bepMonths, survivalRate }: ScoreCardProps) {
  // TODO: 점수 기반 색상 (높음: 녹색, 중간: 노랑, 낮음: 빨강)
  // TODO: 핵심 지표 표시 (매출, BEP, 생존율)

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-800">{district}</h3>
      <div className="mt-4 text-3xl font-bold text-blue-600">{score}점</div>
      <div className="mt-4 space-y-2 text-sm text-gray-600">
        <p>예상 월매출: {(revenue / 10000).toLocaleString()}만원</p>
        <p>BEP 도달: {bepMonths}개월</p>
        <p>12개월 생존율: {(survivalRate * 100).toFixed(0)}%</p>
      </div>
    </div>
  );
}

export default ScoreCard;
