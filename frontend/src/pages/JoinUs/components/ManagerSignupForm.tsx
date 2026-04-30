import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Eye, EyeOff, CheckCircle, XCircle, Loader2, CheckCircle2, Building2 } from 'lucide-react';
import { useToast } from '../../../components/Toast';
import { useAuth } from '../../../auth/AuthContext';

interface Props {
  onSuccess: () => void;
}

interface ManagerForm {
  contactName: string;
  position: string;
  email: string;
  phone: string;
  password: string;
  passwordConfirm: string;
}

interface VerifiedWorkspace {
  company_name: string;
  biz_number: string;
  store_count: number | null;
  owner_id: string;
}

const INITIAL: ManagerForm = {
  contactName: '',
  position: '',
  email: '',
  phone: '',
  password: '',
  passwordConfirm: '',
};

function formatPhone(v: string) {
  const n = v.replace(/\D/g, '').slice(0, 11);
  if (n.length <= 3) return n;
  if (n.length <= 7) return `${n.slice(0, 3)}-${n.slice(3)}`;
  return `${n.slice(0, 3)}-${n.slice(3, 7)}-${n.slice(7)}`;
}

function getPasswordStrength(pw: string): { level: number; label: string; color: string } {
  if (pw.length === 0) return { level: 0, label: '', color: '' };
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[a-zA-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;
  const map = [
    { level: 1, label: '약함', color: 'bg-red-500' },
    { level: 2, label: '보통', color: 'bg-indigo-500' },
    { level: 3, label: '강함', color: 'bg-emerald-400' },
    { level: 4, label: '매우 강함', color: 'bg-emerald-500' },
  ];
  return map[Math.min(score, 4) - 1] || map[0];
}

const fieldClass =
  'w-full px-4 py-3 rounded-xl bg-card border text-foreground text-sm placeholder-muted-foreground outline-none transition-colors duration-200';
const labelClass = 'block text-xs text-muted-foreground font-medium mb-1.5';
const errorClass = 'text-[0.625rem] text-red-400 mt-1';

export default function ManagerSignupForm({ onSuccess }: Props) {
  const { showToast } = useToast();
  const auth = useAuth();

  // 1단계: 초대코드 검증
  const [inviteCode, setInviteCode] = useState('');
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState('');
  const [workspace, setWorkspace] = useState<VerifiedWorkspace | null>(null);

  // 2단계: 매니저 정보 입력
  const [form, setForm] = useState(INITIAL);
  const [showPw, setShowPw] = useState(false);
  const [showPwC, setShowPwC] = useState(false);
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const set = useCallback(
    (key: keyof ManagerForm, val: string) => setForm((p) => ({ ...p, [key]: val })),
    [],
  );
  const touch = (key: string) => setTouched((p) => new Set(p).add(key));

  const handleVerifyInvite = async () => {
    const code = inviteCode.trim().toUpperCase();
    if (code.length < 4 || verifyLoading) return;
    setVerifyError('');
    setVerifyLoading(true);
    try {
      const res = await fetch('/api/auth/verify-invite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        setWorkspace({
          company_name: data.company_name,
          biz_number: data.biz_number,
          store_count: data.store_count,
          owner_id: data.owner_id,
        });
        showToast('success', `${data.company_name} 워크스페이스가 확인되었습니다.`);
      } else {
        setVerifyError(data.message || '초대코드 검증에 실패했습니다.');
      }
    } catch {
      setVerifyError('서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setVerifyLoading(false);
    }
  };

  const resetVerification = () => {
    setWorkspace(null);
    setInviteCode('');
    setVerifyError('');
  };

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email);
  const pwStrength = getPasswordStrength(form.password);
  const pwMatch = form.password === form.passwordConfirm && form.passwordConfirm.length > 0;
  const allValid =
    !!workspace &&
    form.contactName.trim().length > 0 &&
    emailValid &&
    form.phone.replace(/\D/g, '').length >= 10 &&
    form.password.length >= 8 &&
    pwMatch;

  const handleSubmit = async () => {
    if (!allValid || isSubmitting || !workspace) return;
    setSubmitError('');
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/auth/manager/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          inviteCode: inviteCode.trim().toUpperCase(),
          contactName: form.contactName,
          position: form.position,
          email: form.email,
          phone: form.phone.replace(/\D/g, ''),
          password: form.password,
        }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        if (data.access_token && data.user) {
          auth.login(
            { ...data.user, role: 'manager', plan: data.user.plan ?? '' },
            null,
            data.access_token,
          );
        }
        onSuccess();
      } else {
        setSubmitError(data.message || '가입 중 오류가 발생했습니다.');
      }
    } catch {
      setSubmitError('서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 w-full">
      {/* ============ 초대코드 검증 영역 ============ */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="p-5 bg-card border border-border rounded-2xl"
      >
        <label className="block text-xs font-bold text-foreground mb-2">
          워크스페이스 초대 코드
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={inviteCode}
            onChange={(e) => {
              setInviteCode(e.target.value.toUpperCase());
              setVerifyError('');
            }}
            disabled={!!workspace}
            placeholder="예: SPOTTER-2026"
            className={`flex-1 ${fieldClass} font-mono ${
              workspace
                ? 'border-emerald-500/40 text-emerald-400'
                : verifyError
                  ? 'border-red-500 text-warning'
                  : 'border-border text-warning focus:border-warning'
            } disabled:opacity-60`}
          />
          {!workspace ? (
            <button
              onClick={handleVerifyInvite}
              disabled={inviteCode.trim().length < 4 || verifyLoading}
              className={`px-5 rounded-xl text-xs font-bold transition-colors ${
                inviteCode.trim().length >= 4 && !verifyLoading
                  ? 'bg-muted text-foreground hover:bg-muted/80'
                  : 'bg-card text-muted-foreground cursor-not-allowed'
              }`}
            >
              {verifyLoading ? <Loader2 size={14} className="animate-spin" /> : '검증'}
            </button>
          ) : (
            <button
              onClick={resetVerification}
              className="px-5 rounded-xl text-xs font-bold bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/25 flex items-center gap-1.5 transition-colors"
            >
              <CheckCircle2 size={14} />
              확인됨
            </button>
          )}
        </div>

        {verifyError && <p className="text-[0.625rem] text-red-400 mt-2">{verifyError}</p>}

        {workspace && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
            className="mt-3 p-3 bg-emerald-500/10 border border-emerald-500/25 rounded-xl flex items-center gap-3"
          >
            <Building2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="text-xs font-bold text-emerald-400">
              {workspace.company_name} 팀원으로 합류합니다
            </span>
          </motion.div>
        )}
      </motion.div>

      {/* ============ 매니저 정보 입력 (검증 후 활성화) ============ */}
      <div
        className={`flex flex-col gap-4 transition-all duration-500 ${
          workspace
            ? 'opacity-100 max-h-[1200px]'
            : 'opacity-30 max-h-0 overflow-hidden pointer-events-none'
        }`}
      >
        {/* 매니저 이름 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
        >
          <label className={labelClass}>매니저 이름</label>
          <input
            type="text"
            value={form.contactName}
            onChange={(e) => set('contactName', e.target.value)}
            placeholder="홍길동"
            className={`${fieldClass} border-border focus:border-emerald-500`}
          />
        </motion.div>

        {/* 직책 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.4 }}
        >
          <label className={labelClass}>직책 (선택)</label>
          <input
            type="text"
            value={form.position}
            onChange={(e) => set('position', e.target.value)}
            placeholder="권역 매니저"
            className={`${fieldClass} border-border focus:border-emerald-500`}
          />
        </motion.div>

        {/* 이메일 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
        >
          <label className={labelClass}>업무용 이메일</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => set('email', e.target.value)}
            onBlur={() => touch('email')}
            placeholder="name@company.com"
            className={`${fieldClass} ${
              touched.has('email') && form.email && !emailValid
                ? 'border-red-500'
                : 'border-border focus:border-emerald-500'
            }`}
          />
          {touched.has('email') && form.email && !emailValid && (
            <p className={errorClass}>올바른 이메일 형식을 입력하세요</p>
          )}
        </motion.div>

        {/* 연락처 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.4 }}
        >
          <label className={labelClass}>연락처</label>
          <input
            type="tel"
            value={form.phone}
            onChange={(e) => set('phone', formatPhone(e.target.value))}
            placeholder="010-0000-0000"
            className={`${fieldClass} border-border focus:border-emerald-500`}
          />
        </motion.div>

        {/* 비밀번호 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.4 }}
        >
          <label className={labelClass}>비밀번호</label>
          <div className="relative">
            <input
              type={showPw ? 'text' : 'password'}
              value={form.password}
              onChange={(e) => set('password', e.target.value)}
              placeholder="영문+숫자+특수문자 8자 이상"
              className={`${fieldClass} border-border focus:border-emerald-500 pr-10`}
            />
            <button
              type="button"
              onClick={() => setShowPw(!showPw)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {form.password && (
            <div className="flex items-center gap-2 mt-2">
              <div className="flex-1 h-1 rounded-full bg-card overflow-hidden flex gap-0.5">
                {[1, 2, 3, 4].map((n) => (
                  <div
                    key={n}
                    className={`flex-1 rounded-full transition-colors ${
                      n <= pwStrength.level ? pwStrength.color : 'bg-card'
                    }`}
                  />
                ))}
              </div>
              <span className="text-[0.625rem] text-muted-foreground">{pwStrength.label}</span>
            </div>
          )}
        </motion.div>

        {/* 비밀번호 확인 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35, duration: 0.4 }}
        >
          <label className={labelClass}>비밀번호 확인</label>
          <div className="relative">
            <input
              type={showPwC ? 'text' : 'password'}
              value={form.passwordConfirm}
              onChange={(e) => set('passwordConfirm', e.target.value)}
              onBlur={() => touch('passwordConfirm')}
              placeholder="비밀번호 재입력"
              className={`${fieldClass} pr-10 ${
                touched.has('passwordConfirm') && form.passwordConfirm
                  ? pwMatch
                    ? 'border-emerald-500'
                    : 'border-red-500'
                  : 'border-border focus:border-emerald-500'
              }`}
            />
            <button
              type="button"
              onClick={() => setShowPwC(!showPwC)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              {showPwC ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
            {touched.has('passwordConfirm') && form.passwordConfirm && (
              <div className="absolute right-10 top-1/2 -translate-y-1/2">
                {pwMatch ? (
                  <CheckCircle size={14} className="text-emerald-400" />
                ) : (
                  <XCircle size={14} className="text-red-400" />
                )}
              </div>
            )}
          </div>
          {touched.has('passwordConfirm') && form.passwordConfirm && !pwMatch && (
            <p className={errorClass}>비밀번호가 일치하지 않습니다</p>
          )}
        </motion.div>

        {/* Submit error */}
        {submitError && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            className="px-4 py-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-400 text-center"
          >
            {submitError}
          </motion.div>
        )}

        {/* Submit button */}
        <motion.button
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.4 }}
          onClick={handleSubmit}
          disabled={!allValid || isSubmitting}
          className={`w-full py-3.5 rounded-xl font-bold text-sm tracking-wider mt-2 transition-all duration-300 ${
            allValid && !isSubmitting
              ? 'bg-gradient-to-r from-success to-success text-success-foreground shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:scale-[1.02] active:scale-[0.98]'
              : 'bg-card text-muted-foreground cursor-not-allowed'
          }`}
        >
          {isSubmitting ? '가입 처리 중...' : '팀원으로 합류하기'}
        </motion.button>
      </div>
    </div>
  );
}
