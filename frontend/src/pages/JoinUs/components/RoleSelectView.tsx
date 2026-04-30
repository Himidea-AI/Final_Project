import { motion } from 'framer-motion';
import { Building2, Key, ChevronRight } from 'lucide-react';

interface Props {
  onSelectMaster: () => void;
  onSelectManager: () => void;
}

export default function RoleSelectView({ onSelectMaster, onSelectManager }: Props) {
  return (
    <motion.div
      key="role_select"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.5, ease: [0.19, 1, 0.22, 1] }}
      className="w-full max-w-[520px] flex flex-col items-center"
    >
      <div className="text-center mb-12">
        <span className="font-mono text-primary tracking-widest text-xs uppercase">
          Get Started
        </span>
        <h1 className="text-4xl md:text-5xl font-black mt-4 tracking-tight">가입 유형 선택</h1>
        <p className="text-muted-foreground mt-4 text-sm max-w-md mx-auto">
          SPOTTER를 시작할 방식을 선택해주세요.
        </p>
      </div>

      <div className="w-full flex flex-col gap-4">
        <motion.button
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.15, duration: 0.5 }}
          onClick={onSelectMaster}
          className="w-full bg-card border border-border hover:border-primary rounded-2xl p-6 flex items-start gap-5 text-left group transition-all duration-300 hover:shadow-[0_0_30px_rgba(129,140,248,0.15)]"
        >
          <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center shrink-0 group-hover:scale-110 group-hover:bg-primary/20 transition-all">
            <Building2 className="w-6 h-6 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-bold text-white mb-1.5">
              새 워크스페이스 개설
              <span className="ml-2 text-[0.625rem] text-primary font-mono uppercase tracking-wider">
                팀장
              </span>
            </h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              프랜차이즈 본사 계정을 생성하고, 매니저들을 위한 초대 코드를 발급합니다.
            </p>
          </div>
          <ChevronRight className="w-5 h-5 text-muted-foreground/60 group-hover:text-primary self-center transition-colors" />
        </motion.button>

        <motion.button
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.25, duration: 0.5 }}
          onClick={onSelectManager}
          className="w-full bg-card border border-border hover:border-emerald-500/60 rounded-2xl p-6 flex items-start gap-5 text-left group transition-all duration-300 hover:shadow-[0_0_30px_rgba(16,185,129,0.15)]"
        >
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0 group-hover:scale-110 group-hover:bg-emerald-500/20 transition-all">
            <Key className="w-6 h-6 text-emerald-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-bold text-white mb-1.5">
              초대 코드로 합류
              <span className="ml-2 text-[0.625rem] text-emerald-400 font-mono uppercase tracking-wider">
                팀원
              </span>
            </h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              팀장에게 부여받은 초대 코드를 입력하여 해당 워크스페이스에 합류합니다.
            </p>
          </div>
          <ChevronRight className="w-5 h-5 text-muted-foreground/60 group-hover:text-success self-center transition-colors" />
        </motion.button>
      </div>
    </motion.div>
  );
}
