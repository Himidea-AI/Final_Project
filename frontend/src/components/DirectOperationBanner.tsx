/**
 * DirectOperationBanner — 직영 브랜드 특화 분석 모드 안내
 * is_direct === true 일 때 시뮬레이터 결과 상단에 표시
 */

import { Building2, Info } from "lucide-react";

interface Props {
  brandName?: string;
}

export default function DirectOperationBanner({ brandName }: Props) {
  return (
    <div className="flex items-center gap-4 px-5 py-4 rounded-xl bg-[#818cf8]/[0.06] border border-[#818cf8]/30">
      <div className="shrink-0 w-10 h-10 rounded-lg bg-[#818cf8]/15 flex items-center justify-center">
        <Building2 className="w-5 h-5 text-[#818cf8]" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-0.5">
          <h3 className="text-sm font-bold text-[#e2e8f0]">
            본사 직접 관리 브랜드 특화 분석
          </h3>
          <span className="px-2 py-0.5 text-[9px] font-bold bg-[#818cf8]/15 text-[#818cf8] border border-[#818cf8]/30 rounded-full">
            DIRECT OPERATION
          </span>
        </div>
        <p className="text-xs text-[#9ca3af] leading-relaxed">
          {brandName ? `${brandName}은(는)` : "해당 브랜드는"} 직영 방식으로 운영되어 가맹 정보가 제한됩니다.
          상권 분석 및 매출 예측은 본사 직영 기준으로 산출됩니다.
        </p>
      </div>
      <Info className="w-4 h-4 text-[#818cf8] shrink-0 opacity-50" />
    </div>
  );
}
