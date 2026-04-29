import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Eye, EyeOff, CheckCircle, XCircle, Loader2, ChevronRight, CreditCard } from 'lucide-react';
import type { SignupFormData } from '../types';
import { PLANS } from '../constants/plans';
import { useAuth } from '../../../auth/AuthContext';

const INITIAL: SignupFormData = {
  companyName: '',
  bizNumber: '',
  contactName: '',
  position: '',
  email: '',
  phone: '',
  storeCount: '',
  password: '',
  passwordConfirm: '',
  agreeTerms: false,
};

function formatBizNumber(v: string) {
  const n = v.replace(/\D/g, '').slice(0, 10);
  if (n.length <= 3) return n;
  if (n.length <= 5) return `${n.slice(0, 3)}-${n.slice(3)}`;
  return `${n.slice(0, 3)}-${n.slice(3, 5)}-${n.slice(5)}`;
}

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
  'w-full px-4 py-3 rounded-xl bg-[#1e1b18] border text-[#e2e8f0] text-sm placeholder-[#9ca3af] outline-none transition-colors duration-200';
const labelClass = 'block text-xs text-[#9ca3af] font-medium mb-1.5';
const errorClass = 'text-[0.625rem] text-red-400 mt-1';

interface Props {
  planName: string;
  onSuccess: () => void;
}

export default function SignupForm({ planName, onSuccess }: Props) {
  const auth = useAuth();
  const [form, setForm] = useState(INITIAL);
  const [showPw, setShowPw] = useState(false);
  const [showPwC, setShowPwC] = useState(false);
  const [bizLoading, setBizLoading] = useState(false);
  const [touched, setTouched] = useState<Set<string>>(new Set());

  const set = useCallback(
    (key: keyof SignupFormData, val: string | boolean) => setForm((p) => ({ ...p, [key]: val })),
    [],
  );
  const touch = (key: string) => setTouched((p) => new Set(p).add(key));

  // 사업자 검증 상태
  const [bizVerified, setBizVerified] = useState<boolean | null>(null); // null=미검증, true=유효, false=무효
  const [bizError, setBizError] = useState('');

  // Biz number formatting
  const handleBizChange = (v: string) => {
    const formatted = formatBizNumber(v);
    set('bizNumber', formatted);
    setBizVerified(null); // 번호 변경 시 검증 상태 초기화
    setBizError('');
  };

  // 사업자번호 10자리 입력 후 blur → DB에서 기업명+브랜드 자동 조회
  // 기업명까지 입력된 경우 기업명도 함께 전송하여 FTC 매칭 정확도 향상
  const tryBizLookup = async () => {
    const digits = form.bizNumber.replace(/\D/g, '');
    if (digits.length !== 10 || bizLoading) return;

    setBizLoading(true);
    setBizError('');
    try {
      const res = await fetch('/api/biz/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          biz_number: digits,
          company_name: form.companyName.trim(),
        }),
      });
      const data = await res.json();

      // 사업자번호 유효성 체크
      const verification = data.data?.verification;
      if (verification && !verification.valid) {
        setBizVerified(false);
        setBizError(verification.tax_type || '유효하지 않은 사업자등록번호입니다.');
        return;
      }

      if (data.status === 'success' && data.data?.brands?.length > 0) {
        const brand = data.data.brands[0];
        // 브랜드 매칭 성공 → 기업명 자동 입력 + 가맹점 수 자동 입력
        if (brand.corp_name) set('companyName', brand.corp_name);
        if (brand.franchise_count) set('storeCount', String(brand.franchise_count));
        setBizVerified(true);
        setBizError('');
      } else {
        // DB에 매칭되는 브랜드 없음 — 기업명 직접 입력 유도
        setBizVerified(false);
        setBizError('등록된 브랜드를 찾을 수 없습니다. 기업명을 직접 입력해주세요.');
      }
    } catch {
      // API 실패 시 검증 생략 (사용자 직접 입력 유도)
    } finally {
      setBizLoading(false);
    }
  };

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email);
  const pwStrength = getPasswordStrength(form.password);
  const pwMatch = form.password === form.passwordConfirm && form.passwordConfirm.length > 0;
  const storeNum = parseInt(form.storeCount) || 0;
  const allValid =
    form.companyName &&
    form.bizNumber.replace(/\D/g, '').length === 10 &&
    bizVerified === true &&
    form.contactName &&
    form.position &&
    emailValid &&
    form.phone.replace(/\D/g, '').length >= 10 &&
    form.storeCount &&
    form.password.length >= 8 &&
    pwMatch &&
    form.agreeTerms;

  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!allValid || isSubmitting) return;
    setSubmitError('');
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          companyName: form.companyName,
          bizNumber: form.bizNumber.replace(/\D/g, ''),
          contactName: form.contactName,
          position: form.position,
          email: form.email,
          phone: form.phone.replace(/\D/g, ''),
          storeCount: form.storeCount,
          password: form.password,
          plan: planName,
        }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        if (data.access_token && data.user) {
          // role 강제 spread — backend 가 role 누락해도 frontend 안전망 (ManagerSignupForm 패턴 일관)
          auth.login({ ...data.user, role: 'master' }, data.brand ?? null, data.access_token);
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

  const fields = [
    // Each field rendered with stagger delay
    {
      key: 'bizNumber',
      label: '사업자등록번호',
      type: 'text',
      value: form.bizNumber,
      onChange: handleBizChange,
      placeholder: '000-00-00000',
      onBlur: tryBizLookup,
      error: bizError,
      suffix: bizLoading ? (
        <Loader2 size={14} className="animate-spin text-[#818cf8]" />
      ) : bizVerified === true ? (
        <CheckCircle size={14} className="text-emerald-400" />
      ) : bizVerified === false ? (
        <XCircle size={14} className="text-rose-400" />
      ) : null,
    },
    {
      key: 'companyName',
      label: '기업명 (프랜차이즈 본부명)',
      type: 'text',
      value: form.companyName,
      onChange: (v: string) => {
        set('companyName', v);
        setBizVerified(null);
        setBizError('');
      },
      placeholder: '사업자번호와 기업명 입력 후 자동 검증',
      onBlur: tryBizLookup,
      suffix: bizLoading ? (
        <Loader2 size={14} className="animate-spin text-[#818cf8]" />
      ) : bizVerified === true ? (
        <CheckCircle size={14} className="text-emerald-400" />
      ) : null,
    },
    {
      key: 'contactName',
      label: '담당자명',
      type: 'text',
      value: form.contactName,
      onChange: (v: string) => set('contactName', v),
      placeholder: '홍길동',
    },
    {
      key: 'position',
      label: '직책',
      type: 'text',
      value: form.position,
      onChange: (v: string) => set('position', v),
      placeholder: '영업기획팀장',
    },
    {
      key: 'email',
      label: '업무용 이메일',
      type: 'email',
      value: form.email,
      onChange: (v: string) => set('email', v),
      placeholder: 'name@company.com',
      error:
        touched.has('email') && form.email && !emailValid ? '올바른 이메일 형식을 입력하세요' : '',
    },
    {
      key: 'phone',
      label: '연락처',
      type: 'tel',
      value: form.phone,
      onChange: (v: string) => set('phone', formatPhone(v)),
      placeholder: '010-0000-0000',
    },
    {
      key: 'storeCount',
      label: '현재 가맹점 수',
      type: 'number',
      value: form.storeCount,
      onChange: (v: string) => set('storeCount', v),
      placeholder: '0',
    },
  ];

  return (
    <div className="flex flex-col gap-4 w-full">
      {fields.map((f, i) => (
        <motion.div
          key={f.key}
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05, duration: 0.4 }}
        >
          <label className={labelClass}>{f.label}</label>
          <div className="relative">
            <input
              type={f.type}
              value={f.value}
              onChange={(e) => f.onChange(e.target.value)}
              onBlur={() => {
                touch(f.key);
                if ((f as any).onBlur) (f as any).onBlur();
              }}
              placeholder={f.placeholder}
              className={`${fieldClass} ${
                f.error ? 'border-red-500' : 'border-[#3a3633] focus:border-[#818cf8]'
              }`}
            />
            {f.suffix && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">{f.suffix}</div>
            )}
          </div>
          {f.error && <p className={errorClass}>{f.error}</p>}
          {f.key === 'storeCount' && storeNum >= 30 && (
            <p className="text-[0.625rem] text-[#a5b4fc] mt-1">
              30호점 이상 — Enterprise 요금제를 추천합니다
            </p>
          )}
        </motion.div>
      ))}

      {/* Password */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
      >
        <label className={labelClass}>비밀번호</label>
        <div className="relative">
          <input
            type={showPw ? 'text' : 'password'}
            value={form.password}
            onChange={(e) => set('password', e.target.value)}
            placeholder="영문+숫자+특수문자 8자 이상"
            className={`${fieldClass} border-[#3a3633] focus:border-[#818cf8] pr-10`}
          />
          <button
            type="button"
            onClick={() => setShowPw(!showPw)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9ca3af] hover:text-[#9ca3af]"
          >
            {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        {form.password && (
          <div className="flex items-center gap-2 mt-2">
            <div className="flex-1 h-1 rounded-full bg-[#2c2825] overflow-hidden flex gap-0.5">
              {[1, 2, 3, 4].map((n) => (
                <div
                  key={n}
                  className={`flex-1 rounded-full transition-colors ${n <= pwStrength.level ? pwStrength.color : 'bg-[#2c2825]'}`}
                />
              ))}
            </div>
            <span className="text-[0.625rem] text-[#9ca3af]">{pwStrength.label}</span>
          </div>
        )}
      </motion.div>

      {/* Password confirm */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.4 }}
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
                : 'border-[#3a3633] focus:border-[#818cf8]'
            }`}
          />
          <button
            type="button"
            onClick={() => setShowPwC(!showPwC)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9ca3af] hover:text-[#9ca3af]"
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

      {/* Terms */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.45, duration: 0.4 }}
      >
        <label className="flex items-center gap-3 cursor-pointer group">
          <div
            className={`w-5 h-5 rounded border flex items-center justify-center transition-colors shrink-0 ${
              form.agreeTerms
                ? 'bg-[#818cf8] border-[#818cf8]'
                : 'border-[#3a3633] group-hover:border-[#9ca3af]'
            }`}
            onClick={() => set('agreeTerms', !form.agreeTerms)}
          >
            {form.agreeTerms && (
              <svg width="10" height="10" viewBox="0 0 8 8" fill="none">
                <path
                  d="M1.5 4L3 5.5L6.5 2"
                  stroke="white"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
          <span className="text-xs text-[#9ca3af]">이용약관 및 개인정보처리방침에 동의합니다</span>
        </label>
      </motion.div>

      {/* Error message */}
      {submitError && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="px-4 py-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-400 text-center"
        >
          {submitError}
        </motion.div>
      )}

      {/* Submit — 플랜 tier에 따라 CTA + 색상 분기 (Patch v12.2) */}
      {(() => {
        const planObj = PLANS.find((p) => p.name === planName);
        const isFree = planObj ? planObj.price === '₩0' : true;
        const buttonLabel = isSubmitting
          ? '가입 처리 중...'
          : isFree
            ? '가입하기 · 무료로 시작'
            : '구독 및 가입';
        const activeClass = isFree
          ? 'bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:scale-[1.02] active:scale-[0.98]'
          : 'bg-gradient-to-r from-amber-500 to-amber-400 text-[#1e1b18] shadow-[0_0_20px_rgba(245,158,11,0.3)] hover:scale-[1.02] active:scale-[0.98]';
        return (
          <>
            <motion.button
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.4 }}
              onClick={handleSubmit}
              disabled={!allValid || isSubmitting}
              className={`w-full py-3.5 rounded-xl font-bold text-sm tracking-wider mt-2 transition-all duration-300 flex items-center justify-center gap-2 ${
                allValid && !isSubmitting
                  ? activeClass
                  : 'bg-[#2c2825] text-[#9ca3af] cursor-not-allowed'
              }`}
            >
              {!isSubmitting && !isFree && <CreditCard className="w-4 h-4" />}
              {buttonLabel}
              {!isSubmitting && <ChevronRight className="w-4 h-4" />}
            </motion.button>
            {!isFree && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.55, duration: 0.4 }}
                className="text-[0.625rem] text-[#9ca3af] text-center mt-2 leading-relaxed"
              >
                결제는 가입 후 HQ의{' '}
                <span className="text-amber-400 font-mono">결제 및 API 토큰</span> 메뉴에서
                진행됩니다 · 플랜:{' '}
                <span className="text-amber-400 font-bold">
                  {planObj?.name} {planObj?.price}
                  {planObj?.priceNote}
                </span>
              </motion.p>
            )}
          </>
        );
      })()}
    </div>
  );
}
