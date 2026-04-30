/**
 * TrendDriversRisks — 트렌드 드라이버 / 리스크 칩 리스트
 *
 * 데이터: trend_forecast.forecast.key_drivers / risks (string[])
 * 디자인: 좌(emerald 드라이버) / 우(rose 리스크) 양분 레이아웃
 * Best practice: chip 스타일 + 아이콘 + 색상 시멘틱
 */

import { Sparkles, AlertTriangle } from 'lucide-react';

interface Props {
  drivers?: string[];
  risks?: string[];
}

export function TrendDriversRisks({ drivers, risks }: Props) {
  const hasDrivers = drivers && drivers.length > 0;
  const hasRisks = risks && risks.length > 0;

  if (!hasDrivers && !hasRisks) {
    return null;
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {/* 드라이버 */}
      <div className="rounded-2xl border border-success/20 bg-success/5 p-4">
        <div className="flex items-center gap-1.5 mb-2.5">
          <Sparkles size={12} className="text-success" />
          <span className="text-[0.625rem] font-black uppercase tracking-widest text-success">
            성장 드라이버
          </span>
        </div>
        {hasDrivers ? (
          <ul className="space-y-1.5">
            {drivers!.map((d, i) => (
              <li
                key={i}
                className="text-[0.6875rem] text-foreground leading-relaxed flex items-start gap-1.5"
              >
                <span className="text-success mt-0.5">•</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-[0.625rem] text-muted-foreground">식별된 드라이버 없음</span>
        )}
      </div>

      {/* 리스크 */}
      <div className="rounded-2xl border border-danger/20 bg-danger/5 p-4">
        <div className="flex items-center gap-1.5 mb-2.5">
          <AlertTriangle size={12} className="text-danger" />
          <span className="text-[0.625rem] font-black uppercase tracking-widest text-danger">
            리스크 요인
          </span>
        </div>
        {hasRisks ? (
          <ul className="space-y-1.5">
            {risks!.map((r, i) => (
              <li
                key={i}
                className="text-[0.6875rem] text-foreground leading-relaxed flex items-start gap-1.5"
              >
                <span className="text-danger mt-0.5">•</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-[0.625rem] text-muted-foreground">식별된 리스크 없음</span>
        )}
      </div>
    </div>
  );
}
