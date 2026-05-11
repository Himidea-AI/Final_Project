/**
 * AccordionGallery — 25개 구 선택 갤러리 (App.tsx에서 추출, Phase C Round 1).
 * 휠→가로 변환, Edge Panning, 드래그 스크롤, Staggered 글자 애니메이션.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Play } from 'lucide-react';

const DISTRICTS = [
  { name: '강남구', eng: 'GANGNAM', img: '/images/Gangnam-gu.svg' },
  { name: '강동구', eng: 'GANGDONG', img: '/images/Gangdong-gu.svg' },
  { name: '강북구', eng: 'GANGBUK', img: '/images/Gangbuk-gu.svg' },
  { name: '강서구', eng: 'GANGSEO', img: '/images/Gangseo-gu.svg' },
  { name: '관악구', eng: 'GWANAK', img: '/images/Gwanak-gu.svg' },
  { name: '광진구', eng: 'GWANGJIN', img: '/images/Gwangjin-gu.svg' },
  { name: '구로구', eng: 'GURO', img: '/images/Guro-gu.svg' },
  { name: '금천구', eng: 'GEUMCHEON', img: '/images/Geumcheon-gu.svg' },
  { name: '노원구', eng: 'NOWON', img: '/images/Nowon-gu.svg' },
  { name: '도봉구', eng: 'DOBONG', img: '/images/Dobong-gu.svg' },
  { name: '동대문구', eng: 'DONGDAEMUN', img: '/images/Dongdaemun-gu.svg' },
  { name: '동작구', eng: 'DONGJAK', img: '/images/Dongjak-gu.svg' },
  { name: '마포구', eng: 'MAPO', img: '/images/Mapo-gu.svg' },
  { name: '서대문구', eng: 'SEODAEMUN', img: '/images/Seodaemun-gu.svg' },
  { name: '서초구', eng: 'SEOCHO', img: '/images/Seocho-gu.svg' },
  { name: '성동구', eng: 'SEONGDONG', img: '/images/Seongdong-gu.svg' },
  { name: '성북구', eng: 'SEONGBUK', img: '/images/Seongbuk-gu.svg' },
  { name: '송파구', eng: 'SONGPA', img: '/images/Songpa-gu.svg' },
  { name: '양천구', eng: 'YANGCHEON', img: '/images/Yangcheon-gu.svg' },
  { name: '영등포구', eng: 'YEONGDEUNGPO', img: '/images/Yeongdeungpo-gu.svg' },
  { name: '용산구', eng: 'YONGSAN', img: '/images/Yongsan-gu.svg' },
  { name: '은평구', eng: 'EUNPYEONG', img: '/images/Eunpyeong-gu.svg' },
  { name: '종로구', eng: 'JONGNO', img: '/images/Jongno-gu.svg' },
  { name: '중구', eng: 'JUNG', img: '/images/Jung-gu.svg' },
  { name: '중랑구', eng: 'JUNGNANG', img: '/images/Jungnang-gu.svg' },
];

const MAPO_IDX = DISTRICTS.findIndex((d) => d.name === '마포구');

interface AccordionGalleryProps {
  hoveredIdx: number | null;
  setHoveredIdx: (i: number | null) => void;
  onMapoClick: () => void;
}

/* ═══════════════════════════════════════════════════════
   Scene 2: Accordion Gallery — 25개 구 선택 갤러리
   ═══════════════════════════════════════════════════════
   - 수평 스크롤 갤러리 (휠→가로 변환, Edge Panning, 드래그 스크롤)
   - 패널 호버 시 확장 + SVG 휘장 표시 + Staggered 글자 애니메이션
   - 상단 3열 헤더: 로고+BACK | 인디케이터 눈금 | SCROLL TO EXPLORE
   - 마포구 클릭 시 → /simulator로 이동
   - 자체 헤더를 갖고 있어 글로벌 헤더와 별도 (accordion 씬 자체 관리)
*/

export default function AccordionGallery({
  hoveredIdx,
  setHoveredIdx,
  onMapoClick,
}: AccordionGalleryProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const edgeScrollRef = useRef<number>(0);
  const edgeSpeedRef = useRef(0);

  // Drag scroll state
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragScrollLeft = useRef(0);

  // Wheel → horizontal scroll
  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      track.scrollLeft += e.deltaY * 1.5;
    };
    track.addEventListener('wheel', handler, { passive: false });
    return () => track.removeEventListener('wheel', handler);
  }, []);

  // Edge panning — rAF loop
  useEffect(() => {
    const tick = () => {
      const track = trackRef.current;
      if (track && edgeSpeedRef.current !== 0) {
        track.scrollLeft += edgeSpeedRef.current;
      }
      edgeScrollRef.current = requestAnimationFrame(tick);
    };
    edgeScrollRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(edgeScrollRef.current);
  }, []);

  // Mouse move → edge panning detection
  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const w = window.innerWidth;
      const x = e.clientX;
      const edgeZone = w * 0.15;

      if (x < edgeZone) {
        // Left edge — closer to edge = faster
        edgeSpeedRef.current = -((edgeZone - x) / edgeZone) * 12;
      } else if (x > w - edgeZone) {
        // Right edge
        edgeSpeedRef.current = ((x - (w - edgeZone)) / edgeZone) * 12;
      } else {
        edgeSpeedRef.current = 0;
      }

      // Drag scroll
      if (isDragging && trackRef.current) {
        const dx = e.clientX - dragStartX.current;
        trackRef.current.scrollLeft = dragScrollLeft.current - dx;
      }
    },
    [isDragging],
  );

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    dragStartX.current = e.clientX;
    dragScrollLeft.current = trackRef.current?.scrollLeft ?? 0;
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleMouseLeaveTrack = useCallback(() => {
    setIsDragging(false);
    edgeSpeedRef.current = 0;
  }, []);

  return (
    <div
      className="relative z-10 flex flex-col h-full w-full bg-white pt-20"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeaveTrack}
    >
      {/* Indicator strip — App 헤더(96px fixed) 와 갤러리 트랙 사이 중앙.
          (구) 자체 헤더(BACK + indicator + SCROLL TO EXPLORE)는 App 헤더 뒤에 가려져
          backdrop-blur 너머로 흐릿하게 비치는 이슈가 있어 통째 제거됨. indicator 만
          살려 별도 띠로 노출. BACK/scroll 가이드는 의도적 손실. */}
      <div className="w-full py-3 flex items-center justify-center shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-[3px]">
            {DISTRICTS.map((d, i) => (
              <div
                key={d.eng}
                className={`w-1.5 h-4 rounded-sm border transition-all duration-300 ${
                  hoveredIdx === i
                    ? 'bg-primary border-primary scale-y-125 shadow-[0_0_10px_rgba(0,44,209,0.5)]'
                    : 'bg-foreground/10 border-foreground/25'
                }`}
              />
            ))}
          </div>
          <span className="ml-3 text-xs text-muted-foreground tabular-nums min-w-[80px]">
            {hoveredIdx !== null
              ? `${DISTRICTS[hoveredIdx].name} ${hoveredIdx + 1}`
              : '25 Districts'}{' '}
            / 25
          </span>
        </div>
      </div>

      {/* Gallery track */}
      <div
        ref={trackRef}
        className={`flex-1 flex items-center gap-2 md:gap-3 overflow-x-auto scrollbar-hide px-4 ${
          isDragging ? 'cursor-grabbing' : 'cursor-grab'
        }`}
        onMouseDown={handleMouseDown}
      >
        {DISTRICTS.map((d, i) => {
          const isHovered = hoveredIdx === i;
          const isMapo = i === MAPO_IDX;

          return (
            <div
              key={d.eng}
              className={`group/panel relative h-[65vh] shrink-0 rounded-2xl overflow-hidden p-[2px] transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                isMapo ? 'cursor-pointer' : 'cursor-not-allowed'
              } ${
                isHovered
                  ? 'w-[65vh] z-10 shadow-[0_0_30px_rgba(0,44,209,0.3)]'
                  : 'w-[70px] md:w-[80px] z-0'
              }`}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
              onClick={() => {
                if (isMapo && !isDragging) onMapoClick();
              }}
            >
              {/* Rotating laser conic — 호버 only (HQ plan card 패턴: animate-spin-slow + inset-[-50%])
                  opacity transition 1000ms 으로 outer 1200ms 페이스에 맞춤 */}
              <div
                className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover/panel:opacity-100 transition-opacity duration-[1000ms]"
                style={{
                  background:
                    'conic-gradient(from 0deg, transparent 0%, transparent 40%, var(--primary) 50%, var(--primary) 60%, transparent 100%)',
                }}
              />

              {/* Inner glass surface + content (rounded-[14px] = outer 16px - 2px padding) */}
              <div className="box-glass relative z-10 h-full w-full rounded-[14px] overflow-hidden">
                {/* Parallax background image — 구별 SVG 휘장.
                    backgroundPosition 'center 30%' 통일 — 4글자 동명(동대문구·서대문구)이 글자와 겹치는 이슈 해소. */}
                <div
                  className={`absolute inset-0 w-full h-full bg-contain bg-no-repeat transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                    isHovered
                      ? 'scale-100 opacity-80 grayscale-0'
                      : 'scale-[0.9] opacity-30 grayscale-0'
                  }`}
                  style={{ backgroundImage: `url(${d.img})`, backgroundPosition: 'center 30%' }}
                />

                {/* ★ Staggered Letter Animation ★ */}
                <div className="absolute inset-0 pointer-events-none p-4 md:p-8">
                  <div className="relative w-full h-full">
                    {/* Hover: horizontal staggered text */}
                    <h2 className="absolute left-6 md:left-8 bottom-24 md:bottom-20 flex gap-[2px]">
                      {d.name.split('').map((char, ci) => (
                        <span
                          key={ci}
                          className={`font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-foreground to-muted-foreground transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] ${
                            isHovered
                              ? 'text-4xl md:text-5xl opacity-100 translate-y-0 blur-0'
                              : 'text-4xl md:text-5xl opacity-0 translate-y-10 blur-[4px]'
                          }`}
                          style={{
                            transitionDelay: isHovered ? `${ci * 40 + 100}ms` : '0ms',
                          }}
                        >
                          {char}
                        </span>
                      ))}
                    </h2>

                    {/* Default: vertical stacked staggered text */}
                    <h2 className="absolute left-1/2 -translate-x-1/2 bottom-10 md:bottom-12 flex flex-col items-center gap-1">
                      {d.name.split('').map((char, ci) => (
                        <span
                          key={ci}
                          className={`font-black text-transparent bg-clip-text bg-gradient-to-b from-foreground to-muted-foreground leading-none transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] ${
                            isHovered
                              ? 'text-2xl md:text-3xl opacity-0 -translate-y-10 blur-[4px]'
                              : 'text-2xl md:text-3xl opacity-60 translate-y-0 blur-0'
                          }`}
                          style={{
                            transitionDelay: isHovered ? '0ms' : `${ci * 40 + 100}ms`,
                          }}
                        >
                          {char}
                        </span>
                      ))}
                    </h2>

                    {/* Bottom info */}
                    <div
                      className={`absolute left-0 bottom-0 flex flex-col items-start transition-all duration-[1000ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                        isHovered
                          ? 'opacity-100 translate-y-0 delay-[300ms]'
                          : 'opacity-0 translate-y-4 pointer-events-none'
                      }`}
                    >
                      {isMapo ? (
                        <div className="flex items-center gap-2 text-primary text-sm">
                          <Play size={14} />
                          <span>클릭하여 시뮬레이션 시작</span>
                        </div>
                      ) : (
                        <span className="px-2.5 py-1 rounded-full bg-warning/15 border border-warning/30 text-warning text-[0.5625rem] font-bold tracking-wider">
                          서비스 준비 중
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
