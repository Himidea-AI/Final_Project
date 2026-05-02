/**
 * GooeyFilter — SVG feGaussianBlur + feColorMatrix 조합으로 "액체 융합" 효과를 만드는 filter 정의.
 *
 * 사용:
 *   <GooeyFilter id="dashboard-tab-goo" strength={6} />
 *   <div style={{ filter: 'url(#dashboard-tab-goo)' }}>...</div>
 *
 * filter 가 적용된 영역에서 가까이 있는 두 요소가 만나면 액체처럼 합쳐지고,
 * 멀어지면 분리되며 늘어나는 인상. tab indicator 가 다른 탭으로 이동할 때 자연스러운
 * 액체 transition 효과를 만든다.
 *
 * strength: blur 반경(px). 높을수록 액체감 강함. enterprise 톤은 4~8 권장.
 */
export function GooeyFilter({
  id = 'goo-filter',
  strength = 6,
}: {
  id?: string;
  strength?: number;
}) {
  return (
    <svg className="absolute hidden" aria-hidden="true">
      <defs>
        <filter id={id}>
          <feGaussianBlur in="SourceGraphic" stdDeviation={strength} result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 19 -9"
            result="goo"
          />
          <feComposite in="SourceGraphic" in2="goo" operator="atop" />
        </filter>
      </defs>
    </svg>
  );
}
