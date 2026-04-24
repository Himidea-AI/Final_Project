/**
 * Login Page — SPOTTER 로그인
 * POST /auth/login 연동 대기 (현재 백엔드 미구현)
 * _verify_password(bcrypt) 준비됨 → 찬영 API 추가 시 즉시 연결
 */

import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Eye, EyeOff, Loader2, ChevronRight, AlertCircle } from 'lucide-react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { useAuth, loginWithFallback } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { useTransition } from '../App';

// 외부 redirect 주입 방지 — 내부 경로(/로 시작, //로 시작은 프로토콜-상대 URL이라 거부)만 허용.
function safeRedirect(raw: string | null): string | null {
  if (!raw) return null;
  try {
    const decoded = decodeURIComponent(raw);
    if (!decoded.startsWith('/') || decoded.startsWith('//')) return null;
    if (decoded === '/login' || decoded.startsWith('/login?')) return null;
    return decoded;
  } catch {
    return null;
  }
}

export default function LoginPage({ onLogoClick }: { onLogoClick?: () => void }) {
  const nav = useTransition();
  const auth = useAuth();
  const { showToast } = useToast();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  const sessionExpired = searchParams.get('reason') === 'session_expired';
  const redirectTarget = safeRedirect(searchParams.get('redirect'));

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const canSubmit = emailValid && password.length >= 8;

  const handleLogin = async () => {
    if (!canSubmit || isLoading) return;
    setError('');
    setIsLoading(true);

    const result = await loginWithFallback(email, password);

    if (result.success) {
      const defaultLanding = result.role === 'manager' ? '/simulator' : '/hq';
      const destination = redirectTarget ?? defaultLanding;
      if (result.role === 'master') {
        auth.login(result.user, result.brand, result.token);
        showToast(
          'success',
          `환영합니다! ${result.user.company_name || 'SPOTTER'} 엔진에 연결되었습니다.`,
        );
      } else {
        auth.login(result.user, null, result.token);
        showToast('success', `${result.user.contact_name || '매니저'}님, 환영합니다.`);
      }
      nav(destination);
    } else {
      if (result.reason === 'pending_approval') {
        setError(result.message || '팀장의 승인을 기다리고 있습니다. 잠시 후 다시 시도해주세요.');
      } else if (result.reason === 'network_error') {
        setError('서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.');
      } else {
        // 보안: 이메일 존재 여부 노출 금지 (enumeration 공격 방지).
        // 서버가 "이메일이 틀렸다" 같은 구체 메시지를 줘도 통합 문구로 덮음.
        setError('아이디 또는 비밀번호가 잘못되었습니다.');
      }
      // [C-1] 첫 invalid 필드로 자동 포커스 이동 (접근성)
      setTimeout(() => emailRef.current?.focus(), 0);
    }

    setIsLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleLogin();
  };

  // 이미 로그인 상태면 redirect 파라미터 우선, 없으면 역할별 홈으로
  if (auth.isLoggedIn) {
    const fallback = auth.user?.role === 'manager' ? '/simulator' : '/hq';
    return <Navigate to={redirectTarget ?? fallback} replace />;
  }

  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#1e1b18]">
      {/* Background subtle gradient */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-[#818cf8]/[0.04] rounded-full blur-[120px]" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.19, 1, 0.22, 1] }}
        className="relative z-10 w-full max-w-[420px] mx-4"
      >
        {/* Logo */}
        <div className="text-center mb-10">
          <button
            onClick={onLogoClick ?? (() => nav('/'))}
            className="w-full flex items-center justify-center gap-3 mb-4 hover:opacity-80 transition-opacity cursor-pointer"
          >
            <svg width="48" height="18" viewBox="0 0 78 30" fill="none">
              <path
                d="M18.5147 0C15.4686 0 12.5473 1.21005 10.3934 3.36396L3.36396 10.3934C1.21005 12.5473 0 15.4686 0 18.5147C0 24.8579 5.14214 30 11.4853 30C14.5314 30 17.4527 28.7899 19.6066 26.636L24.4689 21.7737C24.469 21.7738 24.4689 21.7736 24.4689 21.7737L38.636 7.6066C39.6647 6.57791 41.0599 6 42.5147 6C44.9503 6 47.0152 7.58741 47.7311 9.78407L52.2022 5.31296C50.1625 2.11834 46.586 0 42.5147 0C39.4686 0 36.5473 1.21005 34.3934 3.36396L15.364 22.3934C14.3353 23.4221 12.9401 24 11.4853 24C8.45584 24 6 21.5442 6 18.5147C6 17.0599 6.57791 15.6647 7.6066 14.636L14.636 7.6066C15.6647 6.57791 17.0599 6 18.5147 6C20.9504 6 23.0152 7.58748 23.7311 9.78421L28.2023 5.31307C26.1626 2.1184 22.5861 0 18.5147 0Z"
                fill="#818cf8"
              />
              <path
                d="M39.364 22.3934C38.3353 23.4221 36.9401 24 35.4853 24C33.05 24 30.9853 22.413 30.2692 20.2167L25.7982 24.6877C27.838 27.8819 31.4143 30 35.4853 30C38.5314 30 41.4527 28.7899 43.6066 26.636L62.636 7.6066C63.6647 6.57791 65.0599 6 66.5147 6C69.5442 6 72 8.45584 72 11.4853C72 12.9401 71.4221 14.3353 70.3934 15.364L63.364 22.3934C62.3353 23.4221 60.9401 24 59.4853 24C57.0498 24 54.985 22.4127 54.269 20.2162L49.798 24.6873C51.8377 27.8818 55.4141 30 59.4853 30C62.5314 30 65.4527 28.7899 67.6066 26.636L74.636 19.6066C76.7899 17.4527 78 14.5314 78 11.4853C78 5.14214 72.8579 0 66.5147 0C63.4686 0 60.5473 1.21005 58.3934 3.36396L39.364 22.3934Z"
                fill="#818cf8"
              />
            </svg>
            <h1 className="text-2xl font-black tracking-[0.2em] text-[#e2e8f0]">SPOTTER</h1>
          </button>
          <p className="text-[#818cf8] font-mono text-[11px] tracking-widest uppercase">
            AI Franchise Intelligence Platform
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-[#2c2825] border border-[#3a3633] rounded-2xl p-8">
          <h2 className="text-lg font-black text-[#e2e8f0] mb-1">로그인</h2>
          <p className="text-xs text-[#9ca3af] mb-8">워크스페이스에 로그인하세요</p>

          {sessionExpired && (
            <div
              role="status"
              aria-live="polite"
              className="mb-5 flex items-start gap-2 px-4 py-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-300"
            >
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>세션이 만료되어 다시 로그인해주세요.</span>
            </div>
          )}

          {/* Email */}
          <div className="mb-5">
            <label className="block text-xs text-[#9ca3af] font-medium mb-1.5">업무용 이메일</label>
            <input
              ref={emailRef}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="name@company.com"
              className="w-full px-4 py-3 rounded-xl bg-[#1e1b18] border border-[#3a3633] text-sm text-[#e2e8f0] placeholder-[#9ca3af] outline-none transition-colors focus:border-[#818cf8]"
            />
          </div>

          {/* Password */}
          <div className="mb-6">
            <label className="block text-xs text-[#9ca3af] font-medium mb-1.5">비밀번호</label>
            <div className="relative">
              <input
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="8자 이상"
                className="w-full px-4 py-3 rounded-xl bg-[#1e1b18] border border-[#3a3633] text-sm text-[#e2e8f0] placeholder-[#9ca3af] outline-none transition-colors focus:border-[#818cf8] pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9ca3af] hover:text-[#e2e8f0] transition-colors"
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <motion.div
              role="alert"
              aria-live="assertive"
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-5 px-4 py-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-400 text-center"
            >
              {error}
            </motion.div>
          )}

          {/* Submit */}
          <button
            onClick={handleLogin}
            disabled={!canSubmit || isLoading}
            className={`w-full py-3.5 rounded-xl font-bold text-sm tracking-wider transition-all duration-300 flex items-center justify-center gap-2 ${
              canSubmit && !isLoading
                ? 'bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:scale-[1.02] active:scale-[0.98]'
                : 'bg-[#2c2825] text-[#9ca3af] cursor-not-allowed border border-[#3a3633]'
            }`}
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <>
                로그인
                <ChevronRight size={16} />
              </>
            )}
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-[#3a3633]" />
            <span className="text-[10px] text-[#9ca3af]">또는</span>
            <div className="flex-1 h-px bg-[#3a3633]" />
          </div>

          {/* Links */}
          <div className="flex flex-col gap-3">
            <button
              onClick={() => nav('/joinus')}
              className="w-full py-3 rounded-xl text-xs font-bold text-[#9ca3af] border border-[#3a3633] hover:border-[#818cf8]/50 hover:text-[#e2e8f0] transition-colors"
            >
              아직 계정이 없으신가요? 회원가입
            </button>
            <button
              onClick={() => nav('/joinus?role=manager')}
              className="w-full py-3 rounded-xl text-xs font-bold text-emerald-400/80 border border-emerald-500/20 hover:border-emerald-500/60 hover:text-emerald-400 hover:bg-emerald-500/5 transition-colors"
            >
              초대 코드로 팀원에 합류하기
            </button>
            <button
              onClick={() => showToast('info', '비밀번호 찾기 기능은 준비 중입니다.')}
              className="text-[10px] text-[#9ca3af] hover:text-[#818cf8] transition-colors"
            >
              비밀번호를 잊으셨나요?
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[9px] text-[#9ca3af]/50 mt-6 font-mono">
          &copy; PROJECT SPOTTER · AI FRANCHISE INTELLIGENCE
        </p>
      </motion.div>
    </div>
  );
}
