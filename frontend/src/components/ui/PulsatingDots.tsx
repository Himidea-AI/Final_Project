/**
 * PulsatingDots — Deep Blue 3 dot 펄세이팅 로더.
 * 외부 레퍼런스 (red-500) 채용 + 색만 brand primary (#002CD1) 로 치환.
 * 텍스트 옆 인라인 (DashboardRunningPlaceholder "시뮬레이션 진행 중" 우측) 용.
 */

import { motion } from 'framer-motion';

export default function PulsatingDots() {
  return (
    <div className="flex items-center justify-center">
      <div className="flex space-x-2">
        <motion.div
          className="h-3 w-3 rounded-full bg-primary"
          animate={{
            scale: [1, 1.5, 1],
            opacity: [0.5, 1, 0.5],
          }}
          transition={{
            duration: 1,
            ease: 'easeInOut',
            repeat: Infinity,
          }}
        />
        <motion.div
          className="h-3 w-3 rounded-full bg-primary"
          animate={{
            scale: [1, 1.5, 1],
            opacity: [0.5, 1, 0.5],
          }}
          transition={{
            duration: 1,
            ease: 'easeInOut',
            repeat: Infinity,
            delay: 0.3,
          }}
        />
        <motion.div
          className="h-3 w-3 rounded-full bg-primary"
          animate={{
            scale: [1, 1.5, 1],
            opacity: [0.5, 1, 0.5],
          }}
          transition={{
            duration: 1,
            ease: 'easeInOut',
            repeat: Infinity,
            delay: 0.6,
          }}
        />
      </div>
    </div>
  );
}
