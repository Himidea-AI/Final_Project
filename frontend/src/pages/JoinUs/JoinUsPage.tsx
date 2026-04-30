import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import { ChevronRight, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { PLANS } from './constants/plans';
import type { Plan } from './types';
import PricingCard from './components/PricingCard';
import PlanBadge from './components/PlanBadge';
import SignupForm from './components/SignupForm';
import EnterpriseContactForm from './components/EnterpriseContactForm';
import RoleSelectView from './components/RoleSelectView';
import ManagerSignupForm from './components/ManagerSignupForm';

type Phase = 'role_select' | 'pricing' | 'form' | 'manager_form' | 'success';
type Role = 'master' | 'manager';

interface Props {
  onBack: () => void;
}

export default function JoinUsPage({ onBack }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [searchParams] = useSearchParams();
  const initialRole = searchParams.get('role') === 'manager' ? 'manager' : null;

  const [phase, setPhase] = useState<Phase>(
    initialRole === 'manager' ? 'manager_form' : 'role_select',
  );
  const [selectedRole, setSelectedRole] = useState<Role | null>(initialRole);
  const [selectedPlan, setSelectedPlan] = useState<Plan['id'] | null>(null);

  // 마운트 시 + phase 변경 시 스크롤 최상단으로
  useEffect(() => {
    scrollRef.current?.scrollTo(0, 0);
  }, [phase]);

  const handleSelectMaster = () => {
    setSelectedRole('master');
    setPhase('pricing');
  };

  const handleSelectManager = () => {
    setSelectedRole('manager');
    setPhase('manager_form');
  };

  const handleSelect = (id: Plan['id']) => {
    setSelectedPlan(id);
    setTimeout(() => setPhase('form'), 100);
  };

  const handleBackToPricing = () => {
    setPhase('pricing');
    setTimeout(() => setSelectedPlan(null), 500);
  };

  const handleBackToRoleSelect = () => {
    setPhase('role_select');
    setTimeout(() => {
      setSelectedRole(null);
      setSelectedPlan(null);
    }, 500);
  };

  const selectedPlanData = PLANS.find((p) => p.id === selectedPlan);

  return (
    <div
      ref={scrollRef}
      className="absolute inset-0 z-20 flex flex-col bg-card text-foreground overflow-y-auto custom-scrollbar"
    >
      {/* Header */}
      <div className="fixed top-0 left-0 w-full h-24 border-b border-border flex items-center px-8 md:px-16 bg-card/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity duration-300"
          >
            <img src="/logo.svg" alt="SPOTTER" className="h-5 w-auto" />
            <span className="text-sm font-bold tracking-wider text-foreground">SPOTTER</span>
          </button>
          <span className="text-border">/</span>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-white transition-colors duration-300"
          >
            <ChevronRight size={14} className="rotate-180" />
            BACK
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex flex-col items-center pt-36 pb-20 px-6">
        <AnimatePresence mode="wait">
          {/* Phase 0: Role Select */}
          {phase === 'role_select' && (
            <RoleSelectView
              key="role_select"
              onSelectMaster={handleSelectMaster}
              onSelectManager={handleSelectManager}
            />
          )}

          {/* Phase 1: Pricing Cards */}
          {phase === 'pricing' && (
            <motion.div
              key="pricing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="flex flex-col items-center w-full"
            >
              {/* Back to role select */}
              <div className="w-full max-w-3xl mb-8 flex justify-start">
                <button
                  onClick={handleBackToRoleSelect}
                  className="flex items-center gap-2 text-xs text-muted-foreground hover:text-white transition-colors"
                >
                  <ArrowLeft size={14} />
                  가입 유형 재선택
                </button>
              </div>

              {/* Heading */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className="text-center mb-16"
              >
                <span className="font-mono text-primary tracking-widest text-xs uppercase">
                  Pricing
                </span>
                <h1 className="text-4xl md:text-6xl font-black mt-4 tracking-tight">
                  요금제를 선택하세요
                </h1>
                <p className="text-muted-foreground mt-4 text-sm max-w-md mx-auto">
                  비즈니스 규모에 맞는 플랜으로 시작하세요.
                  <br />
                  언제든 업그레이드할 수 있습니다.
                </p>
              </motion.div>

              {/* Cards */}
              <div className="flex flex-col lg:flex-row gap-6 items-stretch justify-center">
                {PLANS.map((plan) => (
                  <PricingCard key={plan.id} plan={plan} onSelect={handleSelect} isVisible={true} />
                ))}
              </div>
            </motion.div>
          )}

          {/* Phase 2: Form */}
          {phase === 'form' && selectedPlanData && (
            <motion.div
              key="form"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.6, ease: [0.19, 1, 0.22, 1] }}
              className="w-full max-w-[520px]"
            >
              {/* Back + Badge */}
              <div className="flex items-center justify-between mb-8">
                <button
                  onClick={handleBackToPricing}
                  className="flex items-center gap-2 text-xs text-muted-foreground hover:text-white transition-colors"
                >
                  <ArrowLeft size={14} />
                  요금제 재선택
                </button>
                <PlanBadge planName={selectedPlanData.name} />
              </div>

              {/* Form heading */}
              <h2 className="text-2xl font-black mb-2">
                {selectedPlan === 'enterprise' ? 'Enterprise 도입 문의' : '회원가입'}
              </h2>
              <p className="text-muted-foreground text-sm mb-8">
                {selectedPlan === 'enterprise'
                  ? '담당 영업팀이 맞춤 견적을 안내해드립니다.'
                  : '사업자 정보를 입력하여 계정을 생성하세요.'}
              </p>

              {/* Conditional form */}
              {selectedPlan === 'enterprise' ? (
                <EnterpriseContactForm onSuccess={() => setPhase('success')} />
              ) : (
                <SignupForm
                  planName={selectedPlanData.name}
                  onSuccess={() => setPhase('success')}
                />
              )}
            </motion.div>
          )}

          {/* Phase 2-Manager: Manager Signup Form */}
          {phase === 'manager_form' && (
            <motion.div
              key="manager_form"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.6, ease: [0.19, 1, 0.22, 1] }}
              className="w-full max-w-[520px]"
            >
              {/* Back to role select */}
              <div className="flex items-center justify-between mb-8">
                <button
                  onClick={handleBackToRoleSelect}
                  className="flex items-center gap-2 text-xs text-muted-foreground hover:text-white transition-colors"
                >
                  <ArrowLeft size={14} />
                  가입 유형 재선택
                </button>
                <span className="text-[0.625rem] font-mono text-success tracking-wider uppercase px-2 py-1 rounded bg-success/10 border border-success/30">
                  팀원 가입
                </span>
              </div>

              <h2 className="text-2xl font-black mb-2">조직 합류하기</h2>
              <p className="text-muted-foreground text-sm mb-8">
                팀장에게 받은 초대 코드를 먼저 검증한 후, 매니저 정보를 입력해주세요.
              </p>

              <ManagerSignupForm onSuccess={() => setPhase('success')} />
            </motion.div>
          )}

          {/* Phase 3: Success */}
          {phase === 'success' && (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.6, ease: [0.19, 1, 0.22, 1] }}
              className="flex flex-col items-center justify-center text-center py-20"
            >
              <div
                className={`w-20 h-20 rounded-full flex items-center justify-center mb-6 ${
                  selectedRole === 'manager' ? 'bg-success/10' : 'bg-primary/10'
                }`}
              >
                <CheckCircle2
                  size={40}
                  className={selectedRole === 'manager' ? 'text-success' : 'text-primary'}
                />
              </div>
              <h2 className="text-3xl font-black mb-3">
                {selectedRole === 'manager'
                  ? '팀장 승인 대기 중'
                  : selectedPlan === 'enterprise'
                    ? '문의가 접수되었습니다'
                    : '가입이 완료되었습니다'}
              </h2>
              <p className="text-muted-foreground text-sm mb-8 max-w-sm">
                {selectedRole === 'manager'
                  ? '매니저 가입이 접수되었습니다. 팀장이 HQ에서 승인하면 즉시 로그인할 수 있습니다.'
                  : selectedPlan === 'enterprise'
                    ? '영업팀이 1영업일 내 연락드리겠습니다.'
                    : 'SPOTTER의 모든 기능을 사용할 준비가 되었습니다.'}
              </p>
              <button
                onClick={onBack}
                className={`px-8 py-3 rounded-xl text-white font-bold text-sm tracking-wider hover:scale-[1.02] active:scale-[0.98] transition-all ${
                  selectedRole === 'manager'
                    ? 'bg-gradient-to-r from-success to-success text-success-foreground'
                    : 'bg-gradient-to-r from-primary to-primary'
                }`}
              >
                {selectedRole === 'manager' ? '로그인 화면으로' : 'SPOTTER 시작하기'}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
