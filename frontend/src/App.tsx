import { useState, useEffect, useRef, useCallback } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import JoinUsPage from "./pages/JoinUs/JoinUsPage";
import {
  ChevronRight,
  Sliders,
  Activity,
  MapPin,
  BarChart3,
  AlertCircle,
  Play,
  ExternalLink,
  Mail,
  Phone,
  GitFork,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════
   DATA
   ═══════════════════════════════════════════════════════ */

const DISTRICTS = [
  { name: "강남구", eng: "GANGNAM", img: "/images/Gangnam-gu.svg" },
  { name: "강동구", eng: "GANGDONG", img: "/images/Gangdong-gu.svg" },
  { name: "강북구", eng: "GANGBUK", img: "/images/Gangbuk-gu.svg" },
  { name: "강서구", eng: "GANGSEO", img: "/images/Gangseo-gu.svg" },
  { name: "관악구", eng: "GWANAK", img: "/images/Gwanak-gu.svg" },
  { name: "광진구", eng: "GWANGJIN", img: "/images/Gwangjin-gu.svg" },
  { name: "구로구", eng: "GURO", img: "/images/Guro-gu.svg" },
  { name: "금천구", eng: "GEUMCHEON", img: "/images/Geumcheon-gu.svg" },
  { name: "노원구", eng: "NOWON", img: "/images/Nowon-gu.svg" },
  { name: "도봉구", eng: "DOBONG", img: "/images/Dobong-gu.svg" },
  { name: "동대문구", eng: "DDM", img: "/images/Dongdaemun-gu.svg" },
  { name: "동작구", eng: "DONGJAK", img: "/images/Dongjak-gu.svg" },
  { name: "마포구", eng: "MAPO", img: "/images/Mapo-gu.svg" },
  { name: "서대문구", eng: "SDM", img: "/images/Seodaemun-gu.svg" },
  { name: "서초구", eng: "SEOCHO", img: "/images/Seocho-gu.svg" },
  { name: "성동구", eng: "SEONGDONG", img: "/images/Seongdong-gu.svg" },
  { name: "성북구", eng: "SEONGBUK", img: "/images/Seongbuk-gu.svg" },
  { name: "송파구", eng: "SONGPA", img: "/images/Songpa-gu.svg" },
  { name: "양천구", eng: "YANGCHEON", img: "/images/Yangcheon-gu.svg" },
  { name: "영등포구", eng: "YDP", img: "/images/Yeongdeungpo-gu.svg" },
  { name: "용산구", eng: "YONGSAN", img: "/images/Yongsan-gu.svg" },
  { name: "은평구", eng: "EP", img: "/images/Eunpyeong-gu.svg" },
  { name: "종로구", eng: "JONGNO", img: "/images/Jongno-gu.svg" },
  { name: "중구", eng: "JUNG", img: "/images/Jung-gu.svg" },
  { name: "중랑구", eng: "JUNGNANG", img: "/images/Jungnang-gu.svg" },
];

const MAPO_IDX = 12;

const MENU_ITEMS = ["ABOUT SPOTTER", "JOIN US", "SIMULATOR", "CONTACT"];

const DONG_DATA: Record<string, string[]> = {
  "강남구": ["신사동","논현1동","논현2동","압구정동","청담동","삼성1동","삼성2동","대치1동","대치2동","대치4동","역삼1동","역삼2동","도곡1동","도곡2동","개포1동","개포2동","개포3동","개포4동","일원본동","일원1동","수서동","세곡동"],
  "강동구": ["강일동","상일1동","상일2동","명일1동","명일2동","고덕1동","고덕2동","암사1동","암사2동","암사3동","천호1동","천호2동","천호3동","성내1동","성내2동","성내3동","둔촌1동","둔촌2동"],
  "강북구": ["삼양동","미아동","송중동","송천동","삼각산동","번1동","번2동","번3동","수유1동","수유2동","수유3동","우이동","인수동"],
  "강서구": ["염창동","등촌1동","등촌2동","등촌3동","화곡1동","화곡2동","화곡3동","화곡4동","화곡6동","화곡8동","가양1동","가양2동","가양3동","발산1동","공항동","방화1동","방화2동","방화3동"],
  "관악구": ["보라매동","청림동","행운동","낙성대동","중앙동","인헌동","남현동","서원동","신원동","서림동","신사동","신림동","난향동","조원동","대학동","은천동","성현동","청룡동","난곡동","삼성동","미성동"],
  "광진구": ["중곡1동","중곡2동","중곡3동","중곡4동","능동","구의1동","구의2동","구의3동","광장동","자양1동","자양2동","자양3동","자양4동","화양동","군자동"],
  "구로구": ["신도림동","구로1동","구로2동","구로3동","구로4동","구로5동","가리봉동","고척1동","고척2동","개봉1동","개봉2동","개봉3동","오류1동","오류2동","항동"],
  "금천구": ["가산동","독산1동","독산2동","독산3동","독산4동","시흥1동","시흥2동","시흥3동","시흥4동","시흥5동"],
  "노원구": ["월계1동","월계2동","월계3동","공릉1동","공릉2동","하계1동","하계2동","중계본동","중계1동","중계2동","중계3동","상계1동","상계2동","상계3·4동","상계5동","상계6·7동","상계8동","상계9동","상계10동"],
  "도봉구": ["쌍문1동","쌍문2동","쌍문3동","쌍문4동","방학1동","방학2동","방학3동","창1동","창2동","창3동","창4동","창5동","도봉1동","도봉2동"],
  "동대문구": ["용신동","제기동","전농1동","전농2동","답십리1동","답십리2동","장안1동","장안2동","청량리동","회기동","휘경1동","휘경2동","이문1동","이문2동"],
  "동작구": ["노량진1동","노량진2동","상도1동","상도2동","상도3동","상도4동","흑석동","사당1동","사당2동","사당3동","사당4동","사당5동","대방동","신대방1동","신대방2동"],
  "마포구": ["공덕동","아현동","도화동","용강동","대흥동","염리동","신수동","서강동","서교동","합정동","망원1동","망원2동","연남동","성산1동","성산2동","상암동"],
  "서대문구": ["충현동","천연동","북아현동","신촌동","연희동","홍제1동","홍제2동","홍제3동","홍은1동","홍은2동","남가좌1동","남가좌2동","북가좌1동","북가좌2동"],
  "서초구": ["서초1동","서초2동","서초3동","서초4동","잠원동","반포본동","반포1동","반포2동","반포3동","반포4동","방배본동","방배1동","방배2동","방배3동","방배4동","양재1동","양재2동","내곡동"],
  "성동구": ["왕십리2동","왕십리도선동","마장동","사근동","행당1동","행당2동","응봉동","금호1가동","금호2·3가동","금호4가동","옥수동","성수1가1동","성수1가2동","성수2가1동","성수2가3동","송정동","용답동"],
  "성북구": ["성북동","삼선동","동선동","돈암1동","돈암2동","안암동","보문동","정릉1동","정릉2동","정릉3동","정릉4동","길음1동","길음2동","종암동","월곡1동","월곡2동","장위1동","장위2동","장위3동","석관동"],
  "송파구": ["풍납1동","풍납2동","거여1동","거여2동","마천1동","마천2동","방이1동","방이2동","오륜동","오금동","송파1동","송파2동","석촌동","삼전동","가락본동","가락1동","가락2동","문정1동","문정2동","장지동","위례동","잠실본동","잠실2동","잠실3동","잠실4동","잠실6동","잠실7동"],
  "양천구": ["목1동","목2동","목3동","목4동","목5동","신월1동","신월2동","신월3동","신월4동","신월5동","신월6동","신월7동","신정1동","신정2동","신정3동","신정4동","신정6동","신정7동"],
  "영등포구": ["영등포본동","영등포동","여의동","당산1동","당산2동","도림동","문래동","양평1동","양평2동","신길1동","신길3동","신길4동","신길5동","신길6동","신길7동","대림1동","대림2동","대림3동"],
  "용산구": ["후암동","용산2가동","남영동","청파동","원효로1동","원효로2동","효창동","용문동","한강로동","이촌1동","이촌2동","이태원1동","이태원2동","한남동","서빙고동","보광동"],
  "은평구": ["녹번동","불광1동","불광2동","갈현1동","갈현2동","구산동","대조동","응암1동","응암2동","응암3동","역촌동","신사1동","신사2동","증산동","수색동","진관동"],
  "종로구": ["청운효자동","사직동","삼청동","부암동","평창동","무악동","교남동","가회동","종로1·2·3·4가동","종로5·6가동","이화동","혜화동","창신1동","창신2동","창신3동","숭인1동","숭인2동"],
  "중구": ["소공동","회현동","명동","필동","장충동","광희동","을지로동","신당동","다산동","약수동","청구동","신당5동","동화동","황학동","중림동"],
  "중랑구": ["면목본동","면목2동","면목3·8동","면목4동","면목5동","면목7동","상봉1동","상봉2동","중화1동","중화2동","묵1동","묵2동","망우본동","망우3동","신내1동","신내2동"],
};

const GU_NAMES = Object.keys(DONG_DATA);

const CHART_DATA = [
  { label: "유동인구", value: 82 },
  { label: "임대료", value: 45 },
  { label: "경쟁강도", value: 68 },
  { label: "매출추정", value: 74 },
  { label: "생존율", value: 91 },
  { label: "성장성", value: 56 },
  { label: "접근성", value: 78 },
];

/* ═══════════════════════════════════════════════════════
   NetworkBackground
   ═══════════════════════════════════════════════════════ */

function NetworkBackground({
  isTransitioning,
  scene,
  theme,
}: {
  isTransitioning: boolean;
  scene: string;
  theme: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<
    { x: number; y: number; vx: number; vy: number }[]
  >([]);
  const animRef = useRef<number>(0);
  const mouseRef = useRef<{ x: number; y: number }>({ x: -9999, y: -9999 });
  const pingRef = useRef<{ x: number; y: number; t: number }[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const onMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };
    const onClick = (e: MouseEvent) => {
      pingRef.current.push({ x: e.clientX, y: e.clientY, t: 0 });
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("click", onClick);

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
      else if (scene === "simulator") speedMult = 0.2;

      const isLight = scene === "simulator" && theme === "light";
      const r = isLight ? 217 : 245;
      const g = isLight ? 119 : 158;
      const b = isLight ? 6 : 11;

      const isIntro = scene === "intro";
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
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("click", onClick);
    };
  }, [isTransitioning, scene, theme]);

  const simClass =
    scene === "simulator"
      ? "scale-110 opacity-40"
      : "scale-100 opacity-100";

  return (
    <canvas
      ref={canvasRef}
      className={`fixed inset-0 z-0 transition-all duration-1000 ${simClass}`}
    />
  );
}

/* ═══════════════════════════════════════════════════════
   Scene 1: Intro
   ═══════════════════════════════════════════════════════ */

function IntroScene({
  activeMenuIndex,
  setActiveMenuIndex,
  onAboutClick,
  onJoinUsClick,
  onSimulatorClick,
  onContactClick,
}: {
  activeMenuIndex: number;
  setActiveMenuIndex: (i: number) => void;
  onAboutClick: () => void;
  onJoinUsClick: () => void;
  onSimulatorClick: () => void;
  onContactClick: () => void;
}) {
  return (
    <div className="relative z-10 flex h-full w-full items-center">
      {/* Left section — Typography menu */}
      <div className="flex-1 flex flex-col justify-center pl-12 md:pl-20 lg:pl-32">
        {/* Sub-copy */}
        <div className="flex items-center gap-4 mb-10 text-xs tracking-[0.3em] text-gray-500 uppercase">
          <div className="w-px h-4 bg-gray-600" />
          <span>
            0{activeMenuIndex + 1} / 04 — GET TO KNOW
          </span>
        </div>

        {/* Menu */}
        <nav className="flex flex-col gap-3">
          {MENU_ITEMS.map((item, i) => {
            const isActive = activeMenuIndex === i;
            return (
              <button
                key={item}
                className="relative text-left group"
                onMouseEnter={() => setActiveMenuIndex(i)}
                onClick={() => {
                  if (i === 0) onAboutClick();
                  if (i === 1) onJoinUsClick();
                  if (i === 2) onSimulatorClick();
                  if (i === 3) onContactClick();
                }}
              >
                {/* Indicator bar */}
                <div
                  className={`absolute -left-10 top-1/2 -translate-y-1/2 w-1.5 h-[80%] bg-[#f59e0b] rounded-full transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] origin-top ${
                    isActive ? "scale-x-100" : "scale-x-0"
                  }`}
                />
                <span
                  className={`block text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-black uppercase tracking-tight transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                    isActive
                      ? "text-[#e5e5e5] translate-x-0"
                      : "text-[#404040] -translate-x-2 group-hover:text-[#a3a3a3]"
                  }`}
                >
                  {item}
                </span>
              </button>
            );
          })}
        </nav>

        {/* CTA hint */}
        <div className="mt-12 flex items-center gap-3 text-sm text-gray-500">
          <span className="text-amber-500">
            <ChevronRight size={16} />
          </span>
          <span className="tracking-wide">
            Click <span className="text-[#e5e5e5] font-semibold">SIMULATOR</span> to
            explore
          </span>
        </div>
      </div>

      {/* Right section — Floating Logo with Glow */}
      <div className="absolute right-[10%] top-1/2 -translate-y-1/2 p-10 cursor-pointer group hidden md:flex flex-col items-center pointer-events-auto">
        <div className="relative animate-float-logo">
          {/* Amber neon glow on hover */}
          <div className="absolute inset-0 bg-amber-500 blur-[40px] opacity-0 group-hover:opacity-40 transition-opacity duration-500" />

          <img
            src="/logo.png"
            alt="SPOTTER"
            className="w-48 h-auto relative z-10 opacity-90 transition-all duration-500 group-hover:scale-105 group-hover:drop-shadow-[0_0_30px_rgba(245,158,11,0.6)]"
          />
        </div>

        {/* Text logo */}
        <div className="mt-8 text-center transition-all duration-500 group-hover:scale-105">
          <h1 className="text-4xl md:text-5xl font-black tracking-[0.2em] text-[#e5e5e5]">
            SPOTTER
          </h1>
          <p className="text-amber-500 font-mono text-xs tracking-widest mt-3 uppercase opacity-60 group-hover:opacity-100">
            AI Franchise Simulator
          </p>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Scene 2: Accordion Gallery
   ═══════════════════════════════════════════════════════ */

function AccordionGallery({
  hoveredIdx,
  setHoveredIdx,
  onMapoClick,
  onLogoClick,
}: {
  hoveredIdx: number | null;
  setHoveredIdx: (i: number | null) => void;
  onMapoClick: () => void;
  onLogoClick: () => void;
}) {
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
    track.addEventListener("wheel", handler, { passive: false });
    return () => track.removeEventListener("wheel", handler);
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
    [isDragging]
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
      className="relative z-10 flex flex-col h-full w-full"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeaveTrack}
    >
      {/* Top bar — 3-column: Logo+Back | Indicator | Guide */}
      <div className="w-full h-24 border-b border-[#404040]/50 flex items-center px-8 md:px-16 justify-between bg-[#171717]/80 backdrop-blur-md z-50 shrink-0">
        {/* Left — Logo + Back */}
        <div className="flex items-center gap-3 min-w-[180px]">
          <button
            onClick={onLogoClick}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.png" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-[#e5e5e5]">
              SPOTTER
            </span>
          </button>
          <span className="text-[#404040]">/</span>
          <button
            onClick={onLogoClick}
            className="flex items-center gap-1.5 text-xs text-[#a3a3a3] hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>

        {/* Center — Indicator */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-[3px]">
            {DISTRICTS.map((d, i) => (
              <div
                key={d.eng}
                className={`w-1 h-3 rounded-full transition-all duration-300 ${
                  hoveredIdx === i
                    ? "bg-amber-400 scale-y-150 shadow-[0_0_10px_rgba(245,158,11,0.5)]"
                    : "bg-white/20"
                }`}
              />
            ))}
          </div>
          <span className="ml-3 text-xs text-gray-400 font-mono tabular-nums min-w-[80px]">
            {hoveredIdx !== null
              ? `${DISTRICTS[hoveredIdx].name} ${hoveredIdx + 1}`
              : "25 Districts"}{" "}
            / 25
          </span>
        </div>

        {/* Right — Guide text */}
        <div className="min-w-[180px] text-right">
          <span className="text-xs text-gray-600 tracking-widest">
            SCROLL TO EXPLORE
          </span>
        </div>
      </div>

      {/* Gallery track */}
      <div
        ref={trackRef}
        className={`flex-1 flex items-center gap-2 md:gap-3 overflow-x-auto scrollbar-hide px-4 ${
          isDragging ? "cursor-grabbing" : "cursor-grab"
        }`}
        onMouseDown={handleMouseDown}
      >
          {DISTRICTS.map((d, i) => {
            const isHovered = hoveredIdx === i;
            const isMapo = i === MAPO_IDX;

            return (
              <div
                key={d.eng}
                className={`relative h-[65vh] shrink-0 rounded-2xl overflow-hidden cursor-pointer border transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                  isHovered
                    ? "w-[320px] md:w-[480px] border-amber-500/40 shadow-[0_0_20px_rgba(245,158,11,0.15)] bg-[#262626]"
                    : "w-[70px] md:w-[80px] border-[#404040] bg-[#171717]"
                }`}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
                onClick={() => {
                  if (isMapo && !isDragging) onMapoClick();
                }}
              >
                {/* Parallax background image */}
                <div
                  className={`absolute inset-0 w-full h-full bg-contain bg-center bg-no-repeat transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                    isHovered
                      ? "scale-100 opacity-80 grayscale-0"
                      : "scale-[0.9] opacity-30 grayscale-0"
                  }`}
                  style={{ backgroundImage: `url(${d.img})` }}
                />

                {/* Gradient mask */}
                <div className="absolute inset-0 bg-gradient-to-t from-[#171717] via-[#171717]/60 to-transparent opacity-90 transition-opacity duration-1000" />

                {/* District number */}
                <div
                  className={`absolute top-6 left-0 right-0 text-center font-mono text-xs transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                    isHovered ? "text-gray-400 opacity-100" : "text-gray-600 opacity-0"
                  }`}
                >
                  {String(i + 1).padStart(2, "0")}
                </div>

                {/* English name (shown on hover) */}
                <div
                  className={`absolute top-12 left-6 right-6 transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                    isHovered
                      ? "opacity-100 translate-y-0"
                      : "opacity-0 translate-y-4"
                  }`}
                >
                  <span className="text-xs tracking-[0.3em] text-gray-400 font-light uppercase">
                    {d.eng}-GU
                  </span>
                </div>

                {/* Mapo badge (shown on hover) */}
                {isMapo && (
                  <div
                    className={`absolute top-24 left-6 transition-all duration-[1200ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                      isHovered
                        ? "opacity-100 translate-y-0"
                        : "opacity-0 translate-y-4"
                    }`}
                  >
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs">
                      <Activity size={12} />
                      분석 가능
                    </span>
                  </div>
                )}

                {/* ★ Staggered Letter Animation ★ */}
                <div className="absolute inset-0 pointer-events-none p-4 md:p-8">
                  <div className="relative w-full h-full">
                    {/* Hover: horizontal staggered text */}
                    <h2 className="absolute left-6 md:left-8 bottom-24 md:bottom-20 flex gap-[2px]">
                      {d.name.split("").map((char, ci) => (
                        <span
                          key={ci}
                          className={`font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-white to-[#a3a3a3] transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] ${
                            isHovered
                              ? "text-4xl md:text-5xl opacity-100 translate-y-0 blur-0"
                              : "text-4xl md:text-5xl opacity-0 translate-y-10 blur-[4px]"
                          }`}
                          style={{
                            transitionDelay: isHovered
                              ? `${ci * 40 + 100}ms`
                              : "0ms",
                          }}
                        >
                          {char}
                        </span>
                      ))}
                    </h2>

                    {/* Default: vertical stacked staggered text */}
                    <h2 className="absolute left-1/2 -translate-x-1/2 bottom-10 md:bottom-12 flex flex-col items-center gap-1">
                      {d.name.split("").map((char, ci) => (
                        <span
                          key={ci}
                          className={`font-black text-transparent bg-clip-text bg-gradient-to-b from-white to-[#a3a3a3] leading-none transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] ${
                            isHovered
                              ? "text-2xl md:text-3xl opacity-0 -translate-y-10 blur-[4px]"
                              : "text-2xl md:text-3xl opacity-60 translate-y-0 blur-0"
                          }`}
                          style={{
                            transitionDelay: isHovered
                              ? "0ms"
                              : `${ci * 40 + 100}ms`,
                          }}
                        >
                          {char}
                        </span>
                      ))}
                    </h2>

                    {/* Bottom info (shown on hover) */}
                    <div
                      className={`absolute left-0 bottom-0 flex flex-col items-start transition-all duration-[1000ms] ease-[cubic-bezier(0.19,1,0.22,1)] ${
                        isHovered
                          ? "opacity-100 translate-y-0 delay-[300ms]"
                          : "opacity-0 translate-y-4 pointer-events-none"
                      }`}
                    >
                      {isMapo ? (
                        <div className="flex items-center gap-2 text-amber-400 text-sm">
                          <Play size={14} />
                          <span>클릭하여 시뮬레이션 시작</span>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-500">
                          서비스 준비 중
                        </span>
                      )}
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

/* ═══════════════════════════════════════════════════════
   Scene: About Page
   ═══════════════════════════════════════════════════════ */

const FEATURES = [
  {
    num: "01",
    title: "카니발리제이션(자기잠식) 분석",
    desc: "같은 브랜드 기존 매장과의 영향권 중첩을 계산하여 매출 잠식률을 산출합니다. \"3호점을 내면 1호점 매출이 얼마나 깎이는가?\"에 대한 정량적 답을 제시합니다.",
  },
  {
    num: "02",
    title: "간접 경쟁(대체재) 분석",
    desc: "치킨집의 경쟁상대는 옆 치킨집만이 아닙니다. 피자·족발·배달 야식 등 소비 카테고리 전체의 경쟁 강도를 가중치 기반으로 반영합니다.",
  },
  {
    num: "03",
    title: "What-if 시나리오 시뮬레이션",
    desc: "경쟁 매장 진입, 최저임금 변화, 임대료 상승 등 조건을 변경하면 즉시 재시뮬레이션합니다. 미래의 불확실성을 데이터로 대비하세요.",
  },
  {
    num: "04",
    title: "12개월 시간 축 예측",
    desc: "단순 스냅샷이 아닌, 12개월간의 매출 추이·경쟁 반응·생존 확률을 시계열로 예측합니다.",
  },
  {
    num: "05",
    title: "법률 리스크 AI 검토 (RAG)",
    desc: "가맹사업법 영업지역 보호, 상가임대차보호법 위반 여부를 AI가 자동으로 검토하여 법적 리스크를 사전에 차단합니다.",
  },
];

const COMPARISONS = [
  { old: "현재 상권 스냅샷만 제공", arrow: "→", now: "12개월 미래 예측 시뮬레이션" },
  { old: "같은 업종 경쟁만 분석", arrow: "→", now: "간접 경쟁(대체재)까지 반영" },
  { old: "자기잠식 분석 불가", arrow: "→", now: "카니발리제이션 정량 산출" },
  { old: "컨설팅 비용 수천만 원", arrow: "→", now: "AI 기반 즉시 분석" },
  { old: "정적 리포트 1회 제공", arrow: "→", now: "What-if 무제한 재시뮬레이션" },
  { old: "법률 리스크 수동 검토", arrow: "→", now: "RAG 기반 자동 법률 검토" },
];

const DATA_SOURCES = [
  "소상공인시장진흥공단",
  "서울 생활인구 (KT)",
  "통계청 SGIS",
  "국토부 실거래가",
  "공정위 정보공개서",
  "서울 상권분석 (golmok)",
  "Naver DataLab",
];

const ROADMAP = [
  { phase: "NOW", label: "서울시 마포구 16개 행정동 분석 지원" },
  { phase: "NEXT", label: "서울 전체 25개 구 확장 + 프랜차이즈 브랜드 DB 고도화" },
  { phase: "FUTURE", label: "전국 단위 확장 + 실시간 매출 데이터 연동 + B2B SaaS 출시" },
];

function AboutPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="absolute inset-0 z-20 overflow-y-auto bg-[#171717]/95 backdrop-blur-sm text-[#e5e5e5] pb-32 custom-scrollbar">
      {/* Header */}
      <div className="fixed top-0 left-0 w-full h-24 border-b border-[#404040]/50 flex items-center px-8 md:px-16 bg-[#171717]/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.png" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-[#e5e5e5]">
              SPOTTER
            </span>
          </button>
          <span className="text-[#404040]">/</span>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-[#a3a3a3] hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-8 md:px-16 pt-24">
        {/* ── Section 1: Hero ── */}
        <section className="min-h-[80vh] flex flex-col justify-center animate-[fadeSlideIn_1s_ease-out]">
          <p className="text-lg md:text-xl text-[#a3a3a3] mb-6 tracking-wide">
            기존 상권분석 도구는{" "}
            <span className="text-[#f59e0b] font-bold text-2xl md:text-3xl">
              '지금'
            </span>
            만 보여줍니다.
          </p>

          <div className="flex flex-col gap-4 my-10">
            {[
              "이 자리에 매장을 내면, 1년 뒤 매출은 얼마일까?",
              "같은 브랜드 3호점이 1호점 매출을 얼마나 잡아먹을까?",
              "옆에 경쟁 매장이 들어오면, 내 생존 확률은?",
            ].map((q, i) => (
              <div
                key={i}
                className="border-l-2 border-amber-500 pl-6 py-2"
                style={{ animationDelay: `${i * 150 + 300}ms` }}
              >
                <p className="text-xl md:text-2xl font-medium text-[#e5e5e5]/80 italic">
                  "{q}"
                </p>
              </div>
            ))}
          </div>

          <h2 className="text-3xl md:text-5xl font-black mt-10 tracking-tight leading-tight">
            <span className="text-[#f59e0b]">SPOTTER</span>는
            <br />
            여기서 시작합니다.
          </h2>
        </section>

        {/* ── Section 2: What We Do Differently ── */}
        <section className="py-24">
          <div className="flex items-center gap-4 mb-16">
            <div className="w-12 h-px bg-[#f59e0b]" />
            <h3 className="text-xs font-mono tracking-[0.3em] text-[#a3a3a3] uppercase">
              What We Do Differently
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
            {FEATURES.map((f) => (
              <div key={f.num} className="relative pl-2 pt-6">
                <span className="font-mono text-5xl md:text-7xl font-black text-[#404040] absolute -top-6 -left-4 opacity-50 z-0 select-none">
                  {f.num}
                </span>
                <h4 className="text-xl font-bold text-[#e5e5e5] mb-3 relative z-10">
                  {f.title}
                </h4>
                <p className="text-[#a3a3a3] leading-relaxed relative z-10">
                  {f.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Section 3: Comparison ── */}
        <section className="py-24">
          <div className="flex items-center gap-4 mb-16">
            <div className="w-12 h-px bg-[#f59e0b]" />
            <h3 className="text-xs font-mono tracking-[0.3em] text-[#a3a3a3] uppercase">
              Compared to Existing Solutions
            </h3>
          </div>

          <div className="flex flex-col">
            {COMPARISONS.map((c, i) => (
              <div
                key={i}
                className="flex justify-between items-center py-4 border-b border-[#404040]/50"
              >
                <span className="text-[#6b7280] line-through decoration-[#404040] flex-1 text-sm">
                  {c.old}
                </span>
                <span className="text-[#404040] font-mono mx-6 shrink-0">
                  {c.arrow}
                </span>
                <span className="text-amber-500 font-bold text-lg flex-1 text-right">
                  {c.now}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Section 4: Data & Roadmap ── */}
        <section className="py-24">
          {/* Data sources */}
          <div className="mb-20">
            <div className="flex items-center gap-4 mb-10">
              <div className="w-12 h-px bg-[#f59e0b]" />
              <h3 className="text-xs font-mono tracking-[0.3em] text-[#a3a3a3] uppercase">
                Data &amp; Trust
              </h3>
            </div>
            <p className="text-[#a3a3a3] mb-6 text-sm">
              7개 공공데이터 API 기반 — 신뢰할 수 있는 데이터만 사용합니다.
            </p>
            <div className="flex flex-wrap gap-3">
              {DATA_SOURCES.map((src) => (
                <span
                  key={src}
                  className="px-4 py-2 rounded-full border border-[#404040] bg-[#262626] text-sm text-[#a3a3a3] hover:border-amber-500/50 hover:text-[#e5e5e5] transition-colors cursor-default"
                >
                  {src}
                </span>
              ))}
            </div>
          </div>

          {/* Roadmap */}
          <div>
            <div className="flex items-center gap-4 mb-10">
              <div className="w-12 h-px bg-[#f59e0b]" />
              <h3 className="text-xs font-mono tracking-[0.3em] text-[#a3a3a3] uppercase">
                Roadmap
              </h3>
            </div>
            <div className="flex flex-col gap-8">
              {ROADMAP.map((r, i) => (
                <div key={i} className="flex items-start gap-6">
                  <span className="font-mono text-amber-500 w-24 shrink-0 text-sm font-bold pt-0.5">
                    {r.phase}
                  </span>
                  <div className="flex items-start gap-4">
                    <div className="mt-2 w-2 h-2 rounded-full bg-[#f59e0b] shrink-0" />
                    <p className="text-[#e5e5e5] leading-relaxed">
                      {r.label}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Scene: Contact Page
   ═══════════════════════════════════════════════════════ */

function ContactPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col bg-[#171717]/95 backdrop-blur-sm text-[#e5e5e5] pb-10">
      {/* Header */}
      <div className="fixed top-0 left-0 w-full h-24 border-b border-[#404040]/50 flex items-center px-8 md:px-16 bg-[#171717]/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.png" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-[#e5e5e5]">
              SPOTTER
            </span>
          </button>
          <span className="text-[#404040]">/</span>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-[#a3a3a3] hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex flex-col justify-center pt-24 px-8 md:px-16 overflow-hidden">
        <div className="max-w-6xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left — Mega Typography */}
          <div
            className="lg:col-span-5 flex flex-col justify-center"
            style={{ animation: "fadeSlideIn 1s ease-out" }}
          >
            <span className="font-mono text-amber-500 tracking-widest mb-4 text-xs">
              PROJECT SPOTTER
            </span>
            <h1 className="text-5xl lg:text-7xl xl:text-8xl font-black uppercase leading-none mb-8">
              GET IN
              <br />
              TOUCH.
            </h1>
            <p className="text-[#6b7280] leading-relaxed text-sm max-w-sm">
              AI 기반 프랜차이즈 상권분석 시뮬레이터 프로젝트에 대한 상세한
              코드와 기획 문서는 아래 워크스페이스에서 확인하실 수 있습니다.
            </p>
          </div>

          {/* Right — Bento Box */}
          <div className="lg:col-span-7 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Card 1: Workspace — full width */}
            <div
              className="md:col-span-2 bg-[#262626] border border-[#404040] rounded-2xl p-5 md:p-6 hover:border-amber-500/50 transition-colors flex flex-col justify-center"
              style={{ animation: "fadeSlideIn 1s ease-out 100ms both" }}
            >
              <span className="font-mono text-xs text-[#a3a3a3] uppercase tracking-widest mb-4 block">
                Workspace
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <a
                  href="https://github.com/Himidea-AI/Final_Project"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-[#171717] hover:bg-[#333333] border border-[#404040] rounded-xl p-4 flex justify-between items-center group transition-all"
                >
                  <div className="flex items-center gap-3">
                    <GitFork size={18} className="text-[#a3a3a3] group-hover:text-[#e5e5e5] transition-colors" />
                    <span className="font-bold text-[#e5e5e5] text-sm">GitHub</span>
                  </div>
                  <ExternalLink size={14} className="text-[#404040] group-hover:text-amber-500 transition-colors" />
                </a>
                <a
                  href="https://www.notion.so/333ac2a0181b802b807cf7de2447b890"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-[#171717] hover:bg-[#333333] border border-[#404040] rounded-xl p-4 flex justify-between items-center group transition-all"
                >
                  <div className="flex items-center gap-3">
                    <ExternalLink size={18} className="text-[#a3a3a3] group-hover:text-[#e5e5e5] transition-colors" />
                    <span className="font-bold text-[#e5e5e5] text-sm">Notion</span>
                  </div>
                  <ExternalLink size={14} className="text-[#404040] group-hover:text-amber-500 transition-colors" />
                </a>
                <a
                  href="https://www.figma.com/board/lkjvfmKP4FU5XWBAyWR52a/%EC%A0%9C%EB%AA%A9-%EC%97%86%EC%9D%8C?node-id=0-1&p=f&t=ZITF88ooGHZ2rrHV-0"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-[#171717] hover:bg-[#333333] border border-[#404040] rounded-xl p-4 flex justify-between items-center group transition-all"
                >
                  <div className="flex items-center gap-3">
                    <ExternalLink size={18} className="text-[#a3a3a3] group-hover:text-[#e5e5e5] transition-colors" />
                    <span className="font-bold text-[#e5e5e5] text-sm">Figma</span>
                  </div>
                  <ExternalLink size={14} className="text-[#404040] group-hover:text-amber-500 transition-colors" />
                </a>
                <a
                  href="https://bat981120.atlassian.net/jira/software/projects/IM3/boards/2"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-[#171717] hover:bg-[#333333] border border-[#404040] rounded-xl p-4 flex justify-between items-center group transition-all"
                >
                  <div className="flex items-center gap-3">
                    <ExternalLink size={18} className="text-[#a3a3a3] group-hover:text-[#e5e5e5] transition-colors" />
                    <span className="font-bold text-[#e5e5e5] text-sm">Jira</span>
                  </div>
                  <ExternalLink size={14} className="text-[#404040] group-hover:text-amber-500 transition-colors" />
                </a>
              </div>
            </div>

            {/* Card 2: Team Info */}
            <div
              className="bg-[#262626] border border-[#404040] rounded-2xl p-5 md:p-6 hover:border-amber-500/50 transition-colors flex flex-col justify-center"
              style={{ animation: "fadeSlideIn 1s ease-out 200ms both" }}
            >
              <span className="font-mono text-xs text-[#a3a3a3] uppercase tracking-widest mb-2 block">
                Team
              </span>
              <p className="text-lg font-bold text-white mb-4">
                AI 심화과정 6인 팀 프로젝트 (3조)
              </p>
              <span className="font-mono text-xs text-[#a3a3a3] uppercase tracking-widest mb-2 block">
                Mentor
              </span>
              <p className="text-lg font-bold text-white">황태림</p>
            </div>

            {/* Card 3: Location */}
            <div
              className="bg-[#262626] border border-[#404040] rounded-2xl p-5 md:p-6 hover:border-amber-500/50 transition-colors flex flex-col justify-center"
              style={{ animation: "fadeSlideIn 1s ease-out 300ms both" }}
            >
              <span className="font-mono text-xs text-[#a3a3a3] uppercase tracking-widest mb-4 block">
                Location
              </span>
              <div className="flex items-center gap-3">
                <MapPin className="text-amber-500 w-6 h-6 shrink-0" />
                <span className="text-lg font-bold text-white leading-tight">
                  강남 하이미디어
                  <br />
                  아카데미
                </span>
              </div>
            </div>

            {/* Card 4: Direct Inquiry — full width */}
            <div
              className="md:col-span-2 bg-[#262626] border border-[#404040] rounded-2xl p-5 md:p-6 hover:border-amber-500/50 transition-colors flex flex-col justify-center"
              style={{ animation: "fadeSlideIn 1s ease-out 400ms both" }}
            >
              <span className="font-mono text-xs text-[#a3a3a3] uppercase tracking-widest mb-4 block">
                Direct Inquiry
              </span>
              <div className="flex flex-wrap gap-8">
                <a
                  href="mailto:bat981120@gmail.com"
                  className="text-xl md:text-2xl font-black hover:text-amber-500 transition-colors flex items-center gap-3"
                >
                  <Mail className="w-5 h-5 text-[#a3a3a3] shrink-0" />
                  bat981120@gmail.com
                </a>
                <a
                  href="tel:01067790080"
                  className="text-xl md:text-2xl font-black hover:text-amber-500 transition-colors flex items-center gap-3"
                >
                  <Phone className="w-5 h-5 text-[#a3a3a3] shrink-0" />
                  010.6779.0080
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Scene 3: Simulator Dashboard
   ═══════════════════════════════════════════════════════ */

function SimulatorDashboard({
  reportState,
  setReportState,
}: {
  reportState: string;
  setReportState: (s: "idle" | "loading" | "result") => void;
}) {
  const [radius, setRadius] = useState(500);
  const [budget, setBudget] = useState(200);
  const [weighted, setWeighted] = useState(true);
  const [hoveredBar, setHoveredBar] = useState<number | null>(null);
  const [loadingText, setLoadingText] = useState("INITIALIZING AI ENGINE...");
  const [selectedGu, setSelectedGu] = useState("마포구");
  const [selectedDongs, setSelectedDongs] = useState<string[]>(
    () => [...DONG_DATA["마포구"]]
  );
  const [guDropdownOpen, setGuDropdownOpen] = useState(false);
  const [dongDropdownOpen, setDongDropdownOpen] = useState(false);

  const handleGuChange = useCallback((gu: string) => {
    setSelectedGu(gu);
    setSelectedDongs([...DONG_DATA[gu]]);
    setGuDropdownOpen(false);
    setDongDropdownOpen(false);
  }, []);

  const toggleDong = useCallback((dong: string) => {
    setSelectedDongs((prev) => {
      if (prev.includes(dong)) {
        if (prev.length <= 1) return prev; // 최소 1개
        return prev.filter((d) => d !== dong);
      }
      return [...prev, dong];
    });
  }, []);

  const toggleAllDongs = useCallback(() => {
    const all = DONG_DATA[selectedGu];
    if (selectedDongs.length === all.length) {
      setSelectedDongs([all[0]]); // 전체 해제 시 첫 번째만 유지
    } else {
      setSelectedDongs([...all]);
    }
  }, [selectedGu, selectedDongs]);

  const runSim = useCallback(() => {
    setReportState("loading");
    setTimeout(() => setReportState("result"), 3000);
  }, [setReportState]);

  // Loading streaming text
  useEffect(() => {
    if (reportState !== "loading") return;
    const texts = [
      "FETCHING KT TELECOM DATA...",
      "ANALYZING CANNIBALIZATION RATE...",
      "CALCULATING RENT-TO-REVENUE RATIO...",
      "RUNNING WHAT-IF SCENARIOS...",
      "CROSS-CHECKING LEGAL RISKS...",
      "GENERATING 12-MONTH FORECAST...",
    ];
    let i = 0;
    const interval = setInterval(() => {
      setLoadingText(texts[i % texts.length]);
      i++;
    }, 400);
    return () => clearInterval(interval);
  }, [reportState]);

  // Dark theme only
  const textPrimary = "text-[#e5e5e5]";
  const textSecondary = "text-[#a3a3a3]";
  const accent = "text-[#f59e0b]";
  const accentBg = "bg-[#f59e0b]";
  const panel = "bg-[#262626] border-[#404040] shadow-2xl";
  const inputTrack = "accent-[#f59e0b]";

  return (
    <div className="relative z-10 h-full w-full bg-[#171717] overflow-y-auto custom-scrollbar">
      {/* Top bar */}
      <div className="sticky top-0 z-30 flex items-center px-8 py-4 mt-14 border-b border-[#404040] bg-[#171717]/80 backdrop-blur-xl">
        <span className={`text-xs font-medium tracking-wider ${textSecondary}`}>
          마포구 시뮬레이터
        </span>
      </div>

      {/* Dashboard body */}
      <div className="flex flex-col lg:flex-row gap-6 p-8 max-w-7xl mx-auto">
        {/* Left panel — Controls */}
        <div className={`lg:w-[380px] shrink-0 rounded-2xl border p-6 transition-all duration-700 ${panel}`}>
          <h3
            className={`flex items-center gap-2 text-sm font-bold tracking-wider mb-8 ${textPrimary}`}
          >
            <Sliders size={16} className={accent} />
            SIMULATION CONTROLS
          </h3>

          {/* Radius slider */}
          <div className="mb-8">
            <div className="flex justify-between mb-2">
              <label className={`text-xs font-medium ${textSecondary}`}>
                상권 반경
              </label>
              <span className={`text-xs font-mono ${accent}`}>{radius}m</span>
            </div>
            <input
              type="range"
              min={100}
              max={1500}
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className={`w-full h-1.5 rounded-full appearance-none cursor-pointer ${inputTrack} ${
                "bg-[#404040]"
              }`}
            />
            <div className={`flex justify-between text-[10px] mt-1 ${textSecondary}`}>
              <span>100m</span>
              <span>1500m</span>
            </div>
          </div>

          {/* Budget slider */}
          <div className="mb-8">
            <div className="flex justify-between mb-2">
              <label className={`text-xs font-medium ${textSecondary}`}>
                임대료 예산
              </label>
              <span className={`text-xs font-mono ${accent}`}>{budget}만원</span>
            </div>
            <input
              type="range"
              min={50}
              max={1000}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className={`w-full h-1.5 rounded-full appearance-none cursor-pointer ${inputTrack} ${
                "bg-[#404040]"
              }`}
            />
            <div className={`flex justify-between text-[10px] mt-1 ${textSecondary}`}>
              <span>50만</span>
              <span>1000만</span>
            </div>
          </div>

          {/* Toggle switch */}
          <div className="mb-10">
            <div className="flex items-center justify-between">
              <label className={`text-xs font-medium ${textSecondary}`}>
                유동인구 가중치
              </label>
              <button
                onClick={() => setWeighted(!weighted)}
                className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${
                  weighted ? accentBg : "bg-[#404040]"
                }`}
              >
                <div
                  className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${
                    weighted ? "translate-x-[22px]" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Run button */}
          <button
            onClick={runSim}
            disabled={reportState === "loading"}
            className={`w-full py-3.5 rounded-xl font-bold text-sm tracking-wider flex items-center justify-center gap-2 transition-all duration-300 ${
              reportState === "loading"
                ? "opacity-50 cursor-not-allowed"
                : "hover:scale-[1.02] active:scale-[0.98]"
            } ${
              "bg-gradient-to-r from-[#d97706] to-[#f59e0b] text-white shadow-[0_0_20px_rgba(245,158,11,0.3)] hover:from-[#b45309] hover:to-[#d97706]"
            }`}
          >
            <Play size={16} />
            RUN SIMULATION
          </button>

          {/* Location selector */}
          <div className="mt-6 p-4 rounded-xl border bg-[#171717] border-[#404040]">
            <div className="flex items-center gap-2 mb-3">
              <MapPin size={14} className={accent} />
              <span className={`text-xs font-medium ${textPrimary}`}>
                분석 대상
              </span>
            </div>

            {/* 구 선택 드롭다운 */}
            <div className="relative mb-3">
              <button
                onClick={() => {
                  setGuDropdownOpen(!guDropdownOpen);
                  setDongDropdownOpen(false);
                }}
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-[#404040] bg-[#262626] text-sm text-[#e5e5e5] hover:border-[#f59e0b]/50 transition-colors"
              >
                <span>{selectedGu}</span>
                <ChevronRight
                  size={14}
                  className={`text-[#a3a3a3] transition-transform duration-200 ${
                    guDropdownOpen ? "rotate-90" : ""
                  }`}
                />
              </button>
              {guDropdownOpen && (
                <div className="absolute z-50 mt-1 w-full max-h-52 overflow-y-auto rounded-lg border border-[#404040] bg-[#262626] shadow-2xl custom-scrollbar">
                  {GU_NAMES.map((gu) => (
                    <button
                      key={gu}
                      onClick={() => handleGuChange(gu)}
                      className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                        gu === selectedGu
                          ? "text-[#f59e0b] bg-[#f59e0b]/10"
                          : "text-[#a3a3a3] hover:text-[#e5e5e5] hover:bg-[#333333]"
                      }`}
                    >
                      {gu}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 행정동 선택 드롭다운 */}
            <div className="relative">
              <button
                onClick={() => {
                  setDongDropdownOpen(!dongDropdownOpen);
                  setGuDropdownOpen(false);
                }}
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-[#404040] bg-[#262626] text-sm text-[#e5e5e5] hover:border-[#f59e0b]/50 transition-colors"
              >
                <span className="truncate">
                  {selectedDongs.length === DONG_DATA[selectedGu].length
                    ? `전체 ${selectedDongs.length}개 동`
                    : `${selectedDongs.length}개 동 선택됨`}
                </span>
                <ChevronRight
                  size={14}
                  className={`text-[#a3a3a3] transition-transform duration-200 shrink-0 ${
                    dongDropdownOpen ? "rotate-90" : ""
                  }`}
                />
              </button>
              {dongDropdownOpen && (
                <div className="absolute z-50 mt-1 w-full max-h-52 overflow-y-auto rounded-lg border border-[#404040] bg-[#262626] shadow-2xl custom-scrollbar">
                  {/* 전체 선택 */}
                  <button
                    onClick={toggleAllDongs}
                    className="w-full text-left px-3 py-2 text-xs font-medium border-b border-[#404040] transition-colors text-[#f59e0b] hover:bg-[#f59e0b]/10"
                  >
                    {selectedDongs.length === DONG_DATA[selectedGu].length
                      ? "전체 해제"
                      : "전체 선택"}
                  </button>
                  {DONG_DATA[selectedGu].map((dong) => {
                    const checked = selectedDongs.includes(dong);
                    return (
                      <button
                        key={dong}
                        onClick={() => toggleDong(dong)}
                        className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                          checked
                            ? "text-[#e5e5e5] hover:bg-[#333333]"
                            : "text-[#666666] hover:bg-[#333333] hover:text-[#a3a3a3]"
                        }`}
                      >
                        <div
                          className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                            checked
                              ? "bg-[#f59e0b] border-[#f59e0b]"
                              : "border-[#404040] bg-transparent"
                          }`}
                        >
                          {checked && (
                            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                              <path d="M1.5 4L3 5.5L6.5 2" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          )}
                        </div>
                        {dong}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right panel — Visualization */}
        <div className={`flex-1 rounded-2xl border p-6 min-h-[500px] transition-all duration-700 ${panel}`}>
          {reportState === "idle" && (
            <div className="h-full flex flex-col items-center justify-center gap-4">
              <div
                className={`w-16 h-16 rounded-2xl flex items-center justify-center ${
                  "bg-[#171717]"
                }`}
              >
                <BarChart3 size={28} className={textSecondary} />
              </div>
              <p className={`text-sm ${textSecondary}`}>
                조건을 설정하고 시뮬레이션을 실행하세요
              </p>
            </div>
          )}

          {reportState === "loading" && (
            <div className="h-full flex flex-col items-center justify-center">
              <div className="relative w-24 h-24 mb-8">
                {/* Double spinner */}
                <div className="absolute inset-0 border-4 border-[#404040] border-t-[#f59e0b] rounded-full animate-[spin_2s_linear_infinite]" />
                <div className="absolute inset-2 border-4 border-[#404040] border-b-[#f59e0b] rounded-full animate-[spin_3s_linear_infinite_reverse]" />
              </div>

              <div className="flex flex-col items-center gap-2">
                <p className={`font-mono text-xl font-black tracking-[0.2em] uppercase ${accent}`}>
                  PROCESSING DATA
                </p>
                <div className="px-4 py-2 mt-2 bg-black/10 rounded-md border border-[#404040]/30 backdrop-blur-sm flex items-center gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                  <p className={`font-mono text-xs tracking-widest ${textSecondary}`}>
                    [ {loadingText} ]
                  </p>
                </div>
              </div>
            </div>
          )}

          {reportState === "result" && (
            <div className="flex flex-col gap-6">
              {/* Header */}
              <div className="flex items-center justify-between">
                <h3
                  className={`text-sm font-bold tracking-wider ${textPrimary}`}
                >
                  ANALYSIS RESULT
                </h3>
                <span className={`text-xs ${textSecondary}`}>
                  반경 {radius}m · 예산 {budget}만원
                </span>
              </div>

              {/* Stat cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {/* Score */}
                <div
                  className={`rounded-xl border p-5 transition-all duration-700 ${
                    "bg-[#171717] border-[#404040]"
                  }`}
                >
                  <div className={`text-xs mb-1 ${textSecondary}`}>
                    상권 매력도
                  </div>
                  <div className="flex items-end gap-1">
                    <span className={`text-3xl font-black ${accent}`}>87</span>
                    <span className={`text-sm mb-1 ${textSecondary}`}>
                      / 100
                    </span>
                  </div>
                </div>
                {/* Revenue */}
                <div
                  className={`rounded-xl border p-5 transition-all duration-700 ${
                    "bg-[#171717] border-[#404040]"
                  }`}
                >
                  <div className={`text-xs mb-1 ${textSecondary}`}>
                    예상 월 매출
                  </div>
                  <div className="flex items-end gap-1">
                    <span className={`text-3xl font-black ${textPrimary}`}>
                      3,240
                    </span>
                    <span className={`text-sm mb-1 ${textSecondary}`}>만원</span>
                  </div>
                </div>
                {/* Risk */}
                <div
                  className={`rounded-xl border p-5 transition-all duration-700 ${
                    "bg-[#171717] border-[#404040]"
                  }`}
                >
                  <div className={`text-xs mb-1 ${textSecondary}`}>
                    카니발리제이션 위험
                  </div>
                  <div className="flex items-center gap-2">
                    <AlertCircle size={20} className="text-red-500" />
                    <span className="text-3xl font-black text-red-500">
                      High
                    </span>
                  </div>
                </div>
              </div>

              {/* Bar chart */}
              <div
                className="rounded-xl border p-6 bg-[#171717] border-[#404040]"
              >
                <h4
                  className={`text-xs font-bold tracking-wider mb-6 ${textSecondary}`}
                >
                  항목별 분석
                </h4>
                <div className="flex items-end justify-between gap-3 h-48">
                  {CHART_DATA.map((bar, i) => {
                    const isBarHovered = hoveredBar === i;
                    return (
                      <div
                        key={bar.label}
                        className="flex-1 flex flex-col items-center gap-2 h-full justify-end"
                        onMouseEnter={() => setHoveredBar(i)}
                        onMouseLeave={() => setHoveredBar(null)}
                      >
                        {/* Value label */}
                        <span
                          className={`text-xs font-mono transition-opacity duration-300 ${
                            isBarHovered ? "opacity-100" : "opacity-0"
                          } ${accent}`}
                        >
                          {bar.value}
                        </span>
                        {/* Bar */}
                        <div
                          className="w-full rounded-t-lg transition-all duration-700 ease-[cubic-bezier(0.19,1,0.22,1)] bg-gradient-to-t from-[#b45309] to-[#fbbf24]"
                          style={{
                            height: `${bar.value}%`,
                            opacity: isBarHovered ? 1 : 0.6,
                            filter: isBarHovered
                              ? "brightness(1.3)"
                              : "brightness(1)",
                          }}
                        />
                        {/* Label */}
                        <span
                          className={`text-[10px] ${textSecondary} whitespace-nowrap`}
                        >
                          {bar.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   App — Root
   ═══════════════════════════════════════════════════════ */

/** 현재 경로 → scene 이름 매핑 */
function pathToScene(pathname: string): "intro" | "about" | "joinus" | "accordion" | "simulator" | "contact" {
  if (pathname === "/about") return "about";
  if (pathname === "/joinus") return "joinus";
  if (pathname === "/explore") return "accordion";
  if (pathname === "/simulator") return "simulator";
  if (pathname === "/contact") return "contact";
  return "intro";
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const scene = pathToScene(location.pathname);

  const [isTransitioning, setIsTransitioning] = useState(false);
  const [reportState, setReportState] = useState<"idle" | "loading" | "result">(
    "idle"
  );
  const [activeMenuIndex, setActiveMenuIndex] = useState(2);
  const [hoveredDistrictIdx, setHoveredDistrictIdx] = useState<number | null>(
    null
  );

  // Preloader
  const [loadProgress, setLoadProgress] = useState(0);
  const [isAppLoaded, setIsAppLoaded] = useState(false);
  const [loadLogs, setLoadLogs] = useState<string[]>([]);

  useEffect(() => {
    setLoadLogs(["[SYSTEM] KERNEL BOOT SEQUENCE INITIATED..."]);
    const duration = 3000;
    const interval = 30;
    const steps = duration / interval;
    let currentStep = 0;

    const timer = setInterval(() => {
      currentStep++;
      const p = Math.min(100, Math.floor((currentStep / steps) * 100));
      setLoadProgress(p);

      if (p === 15) setLoadLogs((prev) => [...prev, "[API] ESTABLISHING 3D SPATIAL CONNECTION..."]);
      if (p === 35) setLoadLogs((prev) => [...prev, "[ENGINE] AGGREGATING FRANCHISE DATA..."]);
      if (p === 60) setLoadLogs((prev) => [...prev, "[DATA] CALCULATING RISK ALGORITHMS..."]);
      if (p === 85) setLoadLogs((prev) => [...prev, "[UI] RENDERING HOLOGRAM DASHBOARD..."]);
      if (p === 100) setLoadLogs((prev) => [...prev, "[SYSTEM] SPOTTER ENGINE ONLINE."]);

      if (currentStep >= steps) {
        clearInterval(timer);
        setTimeout(() => setIsAppLoaded(true), 1700);
      }
    }, interval);

    return () => clearInterval(timer);
  }, []);

  /** 암전 트랜지션 + 라우팅 */
  const transitionTo = useCallback(
    (next: "intro" | "about" | "joinus" | "accordion" | "simulator" | "contact") => {
      setIsTransitioning(true);
      setTimeout(() => {
        const pathMap: Record<string, string> = {
          intro: "/",
          about: "/about",
          joinus: "/joinus",
          accordion: "/explore",
          simulator: "/simulator",
          contact: "/contact",
        };
        const path = pathMap[next] || "/";
        navigate(path);
        setReportState("idle");
        setTimeout(() => setIsTransitioning(false), 100);
      }, 800);
    },
    [navigate]
  );

  return (
    <div
      className="w-screen h-screen overflow-hidden select-none"
      style={{
        backgroundColor: "#171717",
        animation: isAppLoaded
          ? "none"
          : "main-scene-in 1.5s cubic-bezier(0.19, 1, 0.22, 1) 0.5s forwards",
      }}
    >
      {/* Film Grain Noise Overlay */}
      <div
        className="pointer-events-none fixed inset-0 z-[9998] opacity-[0.04] mix-blend-screen"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Particle background */}
      <NetworkBackground
        isTransitioning={isTransitioning}
        scene={scene}
        theme="dark"
      />

      {/* Route-based scenes */}
      <Routes>
        <Route
          path="/"
          element={
            <IntroScene
              activeMenuIndex={activeMenuIndex}
              setActiveMenuIndex={setActiveMenuIndex}
              onAboutClick={() => transitionTo("about")}
              onJoinUsClick={() => transitionTo("joinus")}
              onSimulatorClick={() => transitionTo("accordion")}
              onContactClick={() => transitionTo("contact")}
            />
          }
        />
        <Route
          path="/about"
          element={
            <AboutPage onBack={() => transitionTo("intro")} />
          }
        />
        <Route
          path="/joinus"
          element={
            <JoinUsPage onBack={() => transitionTo("intro")} />
          }
        />
        <Route
          path="/explore"
          element={
            <AccordionGallery
              hoveredIdx={hoveredDistrictIdx}
              setHoveredIdx={setHoveredDistrictIdx}
              onMapoClick={() => transitionTo("simulator")}
              onLogoClick={() => transitionTo("intro")}
            />
          }
        />
        <Route
          path="/contact"
          element={
            <ContactPage onBack={() => transitionTo("intro")} />
          }
        />
        <Route
          path="/simulator"
          element={
            <SimulatorDashboard
              reportState={reportState}
              setReportState={setReportState}
            />
          }
        />
      </Routes>

      {/* Global header — simulator only (accordion has its own integrated header) */}
      {scene === "simulator" && !isTransitioning && (
        <header className="fixed top-0 left-0 right-0 z-40 flex items-center gap-4 px-6 py-4 bg-[#171717]/80 backdrop-blur-md border-b border-[#404040]/50">
          <button
            onClick={() => transitionTo("intro")}
            className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.png" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-[#e5e5e5]">
              SPOTTER
            </span>
          </button>
          <span className="text-[#404040]">/</span>
          <button
            onClick={() => transitionTo("accordion")}
            className="flex items-center gap-1.5 text-xs text-[#a3a3a3] hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </header>
      )}

      {/* Transition overlay */}
      <div
        className={`fixed inset-0 z-50 bg-black pointer-events-none transition-opacity duration-[800ms] ${
          isTransitioning ? "opacity-100" : "opacity-0"
        }`}
      />

      {/* 3D Hologram Preloader */}
      {!isAppLoaded && (
        <div
          className="absolute inset-0 z-[99999] bg-[#050505] flex flex-col items-center justify-center"
          style={{
            animation:
              loadProgress === 100
                ? "warp-out 1.2s cubic-bezier(0.19, 1, 0.22, 1) 0.5s forwards"
                : "none",
          }}
        >
          {/* Noise */}
          <div
            className="absolute inset-0 opacity-[0.05] mix-blend-screen pointer-events-none"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
            }}
          />

          {/* 3D Multi-Axis Core */}
          <div className="scene-3d relative w-[300px] h-[300px] md:w-[500px] md:h-[500px] flex items-center justify-center mt-[-10vh]">
            <div className="hologram-wrapper absolute w-full h-full flex items-center justify-center">
              {/* Base core glow */}
              <div className="absolute w-[40%] h-[40%] rounded-full bg-amber-500/20 blur-[40px]" />

              {/* Ring 1 */}
              <svg viewBox="0 0 200 200" className="absolute w-[100%] h-[100%] opacity-40" style={{ transform: "rotateX(70deg) rotateY(10deg) rotateZ(0deg)", animation: "gyro-1 12s linear infinite" }}>
                <circle cx="100" cy="100" r="95" fill="none" stroke="#f59e0b" strokeWidth="0.5" strokeDasharray="2 6" />
                <circle cx="100" cy="100" r="90" fill="none" stroke="#f59e0b" strokeWidth="2" strokeDasharray="10 40 30 20" />
              </svg>

              {/* Ring 2 */}
              <svg viewBox="0 0 200 200" className="absolute w-[85%] h-[85%] opacity-60" style={{ transform: "rotateX(50deg) rotateY(60deg) rotateZ(0deg)", animation: "gyro-2 9s linear infinite" }}>
                <circle cx="100" cy="100" r="85" fill="none" stroke="#d97706" strokeWidth="3" strokeDasharray="60 30 10 30" strokeLinecap="round" />
                <circle cx="100" cy="15" r="5" fill="#f59e0b" />
              </svg>

              {/* Ring 3 */}
              <svg viewBox="0 0 200 200" className="absolute w-[70%] h-[70%] opacity-70" style={{ transform: "rotateX(50deg) rotateY(-60deg) rotateZ(0deg)", animation: "gyro-3 15s linear infinite" }}>
                <circle cx="100" cy="100" r="75" fill="none" stroke="#fbbf24" strokeWidth="1" strokeDasharray="4 8" />
                <circle cx="100" cy="100" r="70" fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="40 80" />
              </svg>

              {/* Ring 4 */}
              <svg viewBox="0 0 200 200" className="absolute w-[95%] h-[95%] opacity-80" style={{ transform: "rotateX(20deg) rotateY(80deg) rotateZ(0deg)", animation: "gyro-4 6s linear infinite" }}>
                <circle cx="100" cy="100" r="88" fill="none" stroke="#fbbf24" strokeWidth="1" style={{ filter: "drop-shadow(0 0 8px #fbbf24)" }} />
                <circle cx="100" cy="12" r="3" fill="#ffffff" />
                <circle cx="100" cy="188" r="3" fill="#ffffff" />
              </svg>

              {/* Ring 5 */}
              <svg viewBox="0 0 200 200" className="absolute w-[115%] h-[115%] opacity-30" style={{ transform: "rotateX(80deg) rotateY(-30deg) rotateZ(0deg)", animation: "gyro-5 20s linear infinite" }}>
                <circle cx="100" cy="100" r="98" fill="none" stroke="#f59e0b" strokeWidth="1" strokeDasharray="4 16" />
                <circle cx="100" cy="100" r="94" fill="none" stroke="#d97706" strokeWidth="0.5" />
              </svg>

              {/* Center percentage */}
              <div
                className="absolute flex flex-col items-center justify-center pointer-events-none"
                style={{ animation: "energy-pulse 2s ease-in-out infinite" }}
              >
                <span className="font-black text-6xl md:text-8xl text-amber-500 tracking-tighter leading-none">
                  {loadProgress}
                  <span className="text-3xl md:text-4xl text-amber-500/60 ml-1">
                    %
                  </span>
                </span>
                <span className="font-mono text-[10px] md:text-xs text-amber-500/80 tracking-[0.3em] mt-2">
                  SYNCING...
                </span>
              </div>
            </div>
          </div>

          {/* Terminal logs */}
          <div className="absolute bottom-10 left-10 md:bottom-16 md:left-16 font-mono text-[10px] md:text-xs text-[#a3a3a3] max-w-md">
            <div className="flex flex-col gap-1.5">
              {loadLogs.map((log, idx) => (
                <div
                  key={idx}
                  className={
                    idx === loadLogs.length - 1
                      ? "text-amber-500 font-bold"
                      : ""
                  }
                >
                  {log}
                </div>
              ))}
            </div>
            <div className="w-2 h-3 bg-amber-500 mt-2 animate-pulse" />
          </div>
        </div>
      )}
    </div>
  );
}
