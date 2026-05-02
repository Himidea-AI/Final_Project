/**
 * WaveBackground — IntroScene 전용 인터랙티브 캔버스 웨이브.
 *
 * sonic-waveform 시각 효과만 차용 (라이트모드 + Deep Blue 팔레트로 적응).
 * 색상 SoT: docs/light-mode-migration/palette-catalog.md (Deep Blue #002CD1)
 *
 * - 페이지 배경(white) 위에 Deep Blue 라인을 낮은 alpha 로 겹쳐 그림
 * - 마우스 근처에서 진폭 증가 — "데이터 흐름" 메타포
 * - prefers-reduced-motion 시 정적 단일 프레임만 렌더링
 * - pointer-events-none — glass-btn/메뉴 인터랙션 방해 X
 */

import { useEffect, useRef } from 'react';

// Deep Blue #002CD1 — palette-catalog.md SoT
const DEEP_BLUE_RGB = '0, 44, 209';
// 트레일 잔상용 — IntroScene `bg-white` 와 정합 (cream 으로 바꿀 경우 248,247,232)
const TRAIL_RGB = '255, 255, 255';

export default function WaveBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    let time = 0;
    let animationFrameId = 0;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const drawFrame = () => {
      // 트레일 잔상 — 화이트 배경 위에 자연스러운 페이드
      ctx.fillStyle = `rgba(${TRAIL_RGB}, 0.08)`;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const lineCount = 36;
      const segmentCount = 80;
      const baseY = canvas.height / 2;

      for (let i = 0; i < lineCount; i++) {
        ctx.beginPath();
        const progress = i / lineCount;
        const colorIntensity = Math.sin(progress * Math.PI);
        // alpha 0.16 max — 라이트 배경에서 헤드라인 가독성 확보
        ctx.strokeStyle = `rgba(${DEEP_BLUE_RGB}, ${colorIntensity * 0.16})`;
        ctx.lineWidth = 1;

        for (let j = 0; j < segmentCount + 1; j++) {
          const x = (j / segmentCount) * canvas.width;

          const distToMouse = Math.hypot(x - mouse.x, baseY - mouse.y);
          const mouseEffect = Math.max(0, 1 - distToMouse / 400);

          const noise = Math.sin(j * 0.1 + time + i * 0.2) * 18;
          const spike = Math.cos(j * 0.2 + time + i * 0.1) * Math.sin(j * 0.05 + time) * 45;
          const y = baseY + noise + spike * (1 + mouseEffect * 1.6);

          if (j === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }

      time += 0.018;
      if (!reduceMotion) animationFrameId = requestAnimationFrame(drawFrame);
    };

    const handleMouseMove = (event: MouseEvent) => {
      mouse.x = event.clientX;
      mouse.y = event.clientY;
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    window.addEventListener('mousemove', handleMouseMove);

    if (reduceMotion) {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      drawFrame();
    } else {
      drawFrame();
    }

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', resizeCanvas);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-0 h-full w-full"
    />
  );
}
