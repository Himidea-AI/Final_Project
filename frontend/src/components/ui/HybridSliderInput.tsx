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
// 1000 이상부터 천 단위 콤마. 미만은 raw 숫자 (콤마 없음).
const fmt = (n: number): string => (n >= 1000 ? n.toLocaleString('en-US') : String(n));

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
  // focus 중엔 raw 숫자(편집 편의), blur 후엔 콤마 적용 표시.
  const [focused, setFocused] = useState(false);

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
    // 콤마/공백 등 비숫자 모두 제거 → 사용자가 콤마 타이핑해도 raw 만 저장.
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

  // input 표시 값: focus 중엔 raw, blur 시 1000+ 콤마 적용.
  const inputDisplay = focused
    ? draft
    : draft === ''
      ? ''
      : (() => {
          const n = Number(draft);
          return Number.isNaN(n) ? draft : fmt(n);
        })();

  const renderMax = maxLabel ?? (max >= 10000 ? `${max / 10000}억` : `${fmt(max)}${unit}`);
  const renderMin = minLabel ?? `${fmt(min)}${unit}`;

  return (
    <div className={`flex flex-col gap-2 mb-3 ${className}`}>
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

        <div className="flex items-baseline gap-1 focus-within:[&>input]:text-primary transition-all">
          <input
            type="text"
            inputMode="numeric"
            value={inputDisplay}
            onChange={handleInputChange}
            onFocus={() => setFocused(true)}
            onBlur={() => {
              setFocused(false);
              commitDraft();
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
            }}
            className="w-24 bg-transparent text-right text-2xl font-black tabular-nums text-primary tracking-tight focus:outline-none placeholder-muted-foreground/60"
            placeholder={fmt(min)}
          />
          <span className="text-xs font-bold text-muted-foreground">{unit}</span>
        </div>
      </div>

      {/* 커스텀 슬라이더 — input 자체에 gradient background 로 progress fill (왼쪽 Deep Blue / 오른쪽 gray) */}
      <div className="relative flex items-center h-4 group">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={sliderValue}
          onChange={handleSliderChange}
          className="w-full h-1.5 appearance-none rounded-full outline-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-125 [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(0,44,209,0.6)] [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:cursor-pointer"
          style={{
            background: `linear-gradient(to right, var(--primary) 0%, var(--primary) ${progressPercent}%, var(--border) ${progressPercent}%, var(--border) 100%)`,
          }}
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
