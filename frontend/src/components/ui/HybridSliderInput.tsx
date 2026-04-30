import { useState, useEffect } from 'react';
import { Info } from 'lucide-react';

export interface HybridSliderInputProps {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  unit: string;
  infoText?: string;
  /** 우측 max 표시 커스텀. 미지정 시 max >= 10000이면 "N억" 자동 변환 */
  maxLabel?: string;
  /** 좌측 min 표시 커스텀. 미지정 시 "{min}{unit}" */
  minLabel?: string;
  className?: string;
}

/**
 * HybridSliderInput — 마우스 드래그(range slider) + 키보드 수기 입력이 완벽 동기화되는
 * controlled 컴포넌트. 부모가 value/onChange로 상태를 관리한다.
 *
 * 내부 draft state가 "타이핑 중"을 수용 (e.g., 빈 문자열) 하고, blur/Enter 시점에
 * min/max로 clamp 후 부모에 커밋한다.
 */
export function HybridSliderInput({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  infoText,
  maxLabel,
  minLabel,
  className = '',
}: HybridSliderInputProps) {
  const [draft, setDraft] = useState<string>(String(value));

  // 외부에서 value가 바뀌면 draft 동기화 (프리셋 적용 등)
  useEffect(() => {
    setDraft(String(value));
  }, [value]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const num = Number(e.target.value);
    setDraft(String(num));
    onChange(num);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/[^0-9]/g, '');
    setDraft(raw);
  };

  const commitDraft = () => {
    let num = Number(draft);
    if (draft === '' || Number.isNaN(num) || num < min) num = min;
    if (num > max) num = max;
    setDraft(String(num));
    onChange(num);
  };

  // 진행률 계산 — draft가 비어있거나 초과값이어도 슬라이더 위치는 clamp
  const sliderValue = Math.min(max, Math.max(min, draft === '' ? min : Number(draft) || min));
  const progressPercent = ((sliderValue - min) / (max - min)) * 100;

  const renderMax = maxLabel ?? (max >= 10000 ? `${max / 10000}억` : `${max}${unit}`);
  const renderMin = minLabel ?? `${min}${unit}`;

  return (
    <div className={`flex flex-col gap-3 mb-6 ${className}`}>
      {/* 라벨 + 수기 입력 영역 */}
      <div className="flex justify-between items-center">
        <label className="text-xs font-bold text-foreground flex items-center gap-1.5 group cursor-help">
          {label}
          {infoText && (
            <div className="relative flex items-center">
              <Info className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary transition-colors" />
              <div className="absolute left-6 top-4 w-48 p-2 bg-card border border-border rounded-md shadow-xl text-[0.625rem] text-muted-foreground opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                {infoText}
              </div>
            </div>
          )}
        </label>

        <div className="flex items-center bg-muted border border-border rounded-md px-2 py-1.5 focus-within:border-primary focus-within:shadow-[0_0_10px_rgba(0,44,209,0.2)] transition-all">
          <input
            type="text"
            inputMode="numeric"
            value={draft}
            onChange={handleInputChange}
            onBlur={commitDraft}
            onKeyDown={(e) => {
              if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
            }}
            className="w-16 bg-transparent text-right text-xs font-mono tabular-nums font-black text-primary focus:outline-none placeholder-muted-foreground/60"
            placeholder={String(min)}
          />
          <span className="text-[0.625rem] text-muted-foreground ml-1 font-bold">{unit}</span>
        </div>
      </div>

      {/* 커스텀 슬라이더 */}
      <div className="relative flex items-center h-4 group">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={sliderValue}
          onChange={handleSliderChange}
          className="absolute w-full h-1.5 appearance-none bg-border rounded-full outline-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-125 [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(0,44,209,0.6)] z-10"
        />
        <div
          className="absolute left-0 h-1.5 bg-gradient-to-r from-primary to-primary rounded-full pointer-events-none z-0"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="flex justify-between text-[0.625rem] text-muted-foreground font-mono tabular-nums">
        <span>{renderMin}</span>
        <span>{renderMax}</span>
      </div>
    </div>
  );
}

export default HybridSliderInput;
