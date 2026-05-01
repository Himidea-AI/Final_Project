/**
 * NetworkBackground — 전역 입자 + 연결선 캔버스 배경.
 *
 * Scene 별 동작:
 * - intro: 마우스 자기장 인터랙션 + 클릭 시 레이더 ping
 * - simulator: 정적, 약간 줌인 + 투명도 낮춤 (light 테마면 indigo)
 * - 그 외: 표준 부드러운 흐름
 *
 * App.tsx 추출 (Phase C Round 1) — 외부 의존성 없음(props만), useRef/useEffect만 사용.
 */

import { useEffect, useRef } from 'react';

interface NetworkBackgroundProps {
  isTransitioning: boolean;
  scene: string;
  theme: string;
}

export default function NetworkBackground({
  isTransitioning,
  scene,
  theme,
}: NetworkBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<{ x: number; y: number; vx: number; vy: number }[]>([]);
  const animRef = useRef<number>(0);
  const mouseRef = useRef<{ x: number; y: number }>({ x: -9999, y: -9999 });
  const pingRef = useRef<{ x: number; y: number; t: number }[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const onMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };
    const onClick = (e: MouseEvent) => {
      pingRef.current.push({ x: e.clientX, y: e.clientY, t: 0 });
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('click', onClick);

    // Init particles — responsive count based on screen area
    if (particlesRef.current.length === 0) {
      const particleCount = Math.min(350, Math.floor((canvas.width * canvas.height) / 8000));
      for (let i = 0; i < particleCount; i++) {
        particlesRef.current.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.6,
          vy: (Math.random() - 0.5) * 0.6,
        });
      }
    }

    const animate = () => {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const particles = particlesRef.current;
      let speedMult = 1;
      if (isTransitioning) speedMult = 5;
      else if (scene === 'simulator') speedMult = 0.2;

      const isLight = scene === 'simulator' && theme === 'light';
      const r = isLight ? 99 : 129;
      const g = isLight ? 102 : 140;
      const b = isLight ? 241 : 248;

      const isIntro = scene === 'intro';
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;

      // Update & draw particles
      for (const p of particles) {
        // Intro only: magnetic pull toward mouse
        if (isIntro) {
          const dmx = mx - p.x;
          const dmy = my - p.y;
          const md = Math.sqrt(dmx * dmx + dmy * dmy);
          if (md < 200 && md > 1) {
            const force = ((200 - md) / 200) * 0.015;
            p.vx += (dmx / md) * force;
            p.vy += (dmy / md) * force;
          }
        }

        p.x += p.vx * speedMult;
        p.y += p.vy * speedMult;
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r},${g},${b},0.5)`;
        ctx.fill();
      }

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(${r},${g},${b},${0.15 * (1 - dist / 150)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      // Intro only: mouse connection lines (radius 250, high visibility)
      if (isIntro && mx > 0) {
        for (const p of particles) {
          const dmx = mx - p.x;
          const dmy = my - p.y;
          const md = Math.sqrt(dmx * dmx + dmy * dmy);
          if (md < 250) {
            ctx.beginPath();
            ctx.moveTo(mx, my);
            ctx.lineTo(p.x, p.y);
            ctx.strokeStyle = `rgba(${r},${g},${b},${(1 - md / 250) * 0.8})`;
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }
        }

        // Radar ping effect
        const pings = pingRef.current;
        for (let i = pings.length - 1; i >= 0; i--) {
          const ping = pings[i];
          ping.t += 2;
          if (ping.t > 150) {
            pings.splice(i, 1);
            continue;
          }
          const alpha = 1 - ping.t / 150;
          ctx.beginPath();
          ctx.arc(ping.x, ping.y, ping.t, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(${r},${g},${b},${alpha * 0.3})`;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('click', onClick);
    };
  }, [isTransitioning, scene, theme]);

  const simClass = scene === 'simulator' ? 'scale-110 opacity-40' : 'scale-100 opacity-100';

  return (
    <canvas
      ref={canvasRef}
      className={`fixed inset-0 z-0 transition-all duration-1000 ${simClass}`}
    />
  );
}
