/**
 * SpotterAgentWorkflow — AI 에이전트 파이프라인 시각화
 * LangGraph 5-노드 워크플로우를 Drawer 안에서 표시.
 * App.tsx Phase C Round 3 코드 스플릿으로 추출 — 기능 변경 없음.
 *
 * 백엔드 아키텍처(Parallel Analysis) 반영:
 * - Supervisor LLM 제거 → 하드코딩 parallel_analysis 라우터로 교체
 * - Market / Population / Legal 3개 에이전트 동시(Parallel) 실행
 */
import { useState, useEffect } from 'react';
import { LayoutGroup, motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Circle, CircleDotDashed } from 'lucide-react';

const spotterAgentTasks = [
  {
    id: '1',
    title: 'Parallel Analysis Node (병렬 라우터)',
    description:
      'LLM 개입 없이 하드코딩된 코드로 3개의 전문 에이전트를 동시에(Parallel) 병렬 호출하여 속도를 극대화합니다.',
    status: 'completed' as const,
    priority: 'high',
    dependencies: [] as string[],
    subtasks: [
      {
        id: '1.1',
        title: '파라미터 추출 및 쿼리 최적화',
        description: '사용자 입력값 파싱 및 DB 쿼리 파라미터 생성',
        status: 'completed' as const,
        tools: ['Python', 'Regex'],
      },
      {
        id: '1.2',
        title: '하위 에이전트 병렬 분배 (Simultaneous Dispatch)',
        description: 'Market, Population, Legal 에이전트 동시 실행 트리거',
        status: 'completed' as const,
        tools: ['LangGraph Parallel'],
      },
    ],
  },
  {
    id: '2',
    title: 'Market Analyst (상권 & 경쟁 분석)',
    description: 'pgvector DB에서 상권의 매출 현황과 카니발리제이션 위험도를 계산합니다.',
    status: 'in-progress' as const,
    priority: 'high',
    dependencies: ['1'],
    subtasks: [
      {
        id: '2.1',
        title: '경쟁점 반경 검색 (Vector Search)',
        description: 'HNSW 인덱스를 활용한 500m 내 동종 업계 검색',
        status: 'completed' as const,
        tools: ['pgvector', 'PostgreSQL'],
      },
      {
        id: '2.2',
        title: '예상 매출 LSTM 추론',
        description: '최근 3년 매출 데이터를 기반으로 향후 12개월 매출 예측',
        status: 'in-progress' as const,
        tools: ['LSTM Model', 'TensorFlow'],
      },
      {
        id: '2.3',
        title: '카니발리제이션 타격률 계산',
        description: '인접 가맹점 간의 상권 중첩도 기반 매출 하락률 도출',
        status: 'pending' as const,
        tools: ['Cannibalization Engine'],
      },
    ],
  },
  {
    id: '3',
    title: 'Population Analyst (유동인구 분석)',
    description: 'KT 통신망 데이터를 기반으로 시간대별, 성별/연령별 유동인구를 군집화합니다.',
    status: 'in-progress' as const,
    priority: 'medium',
    dependencies: ['1'],
    subtasks: [
      {
        id: '3.1',
        title: '시간대별 유동인구 집계',
        description: '06시~02시까지의 시간대별 트래픽 분포 계산',
        status: 'completed' as const,
        tools: ['KT API'],
      },
      {
        id: '3.2',
        title: '핵심 타겟(Primary Target) 매칭',
        description: '브랜드 타겟층(2030 여성)과 해당 상권 유동인구 비율 대조',
        status: 'in-progress' as const,
        tools: ['Demographic Scraper'],
      },
    ],
  },
  {
    id: '4',
    title: 'Legal Analyst (법률 리스크 RAG)',
    description:
      '상가임대차보호법 및 지역 규제 데이터를 검색하여 권리금/임대료 리스크를 판단합니다.',
    status: 'in-progress' as const,
    priority: 'high',
    dependencies: ['1'],
    subtasks: [
      {
        id: '4.1',
        title: '문서 청크 검색 (Similarity Search)',
        description: '관련 법률 문서 및 최근 판례 RAG 검색',
        status: 'in-progress' as const,
        tools: ['Sentence-Transformers', 'Vector DB'],
      },
      {
        id: '4.2',
        title: '리스크 요약 및 경고 생성',
        description: '검색된 판례를 바탕으로 LLM 기반 위험 요소 3줄 요약',
        status: 'pending' as const,
        tools: ['Gemini 1.5 Pro'],
      },
    ],
  },
  {
    id: '5',
    title: 'Strategy Synthesizer (최종 종합)',
    description:
      '병렬 실행된 3개 에이전트의 결과를 취합하여 7대 지표를 정규화하고 최종 인사이트를 작성합니다.',
    status: 'pending' as const,
    priority: 'high',
    dependencies: ['2', '3', '4'],
    subtasks: [
      {
        id: '5.1',
        title: '0~100점 정규화 (Normalization)',
        description: '7개 주요 메트릭을 레이더 차트용 점수로 변환',
        status: 'pending' as const,
        tools: ['Math Module'],
      },
      {
        id: '5.2',
        title: '종합 매력도 및 BEP 산출',
        description: '투자금 대비 손익분기점(BEP) 도달 개월 수 계산',
        status: 'pending' as const,
        tools: ['ROI Calculator'],
      },
    ],
  },
];

type TaskStatus = 'completed' | 'in-progress' | 'pending';
type AgentTask = {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: string;
  dependencies: string[];
  subtasks: {
    id: string;
    title: string;
    description: string;
    status: TaskStatus;
    tools: string[];
  }[];
};

function SpotterAgentWorkflow() {
  const [tasks, setTasks] = useState<AgentTask[]>(spotterAgentTasks as AgentTask[]);
  // 병렬 실행 중인 3개 (Market/Population/Legal) 모두 펼쳐두어 동시성 시각화
  const [expandedTasks, setExpandedTasks] = useState<string[]>(['2', '3', '4']);
  const [expandedSubtasks, setExpandedSubtasks] = useState<Record<string, boolean>>({});

  // 병렬(Parallel) 처리 시뮬레이션 — 3개 에이전트가 약간의 시차로 동시 완료
  useEffect(() => {
    const t1 = setTimeout(() => toggleSubtaskStatus('2', '2.2'), 2000);
    const t2 = setTimeout(() => toggleSubtaskStatus('3', '3.2'), 2500);
    const t3 = setTimeout(() => toggleSubtaskStatus('4', '4.1'), 3000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleTaskExpansion = (taskId: string) => {
    setExpandedTasks((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId],
    );
  };
  const toggleSubtaskExpansion = (taskId: string, subtaskId: string) => {
    const key = `${taskId}-${subtaskId}`;
    setExpandedSubtasks((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleSubtaskStatus = (taskId: string, subtaskId: string) => {
    setTasks((prev) =>
      prev.map((task) => {
        if (task.id === taskId) {
          const updatedSubtasks = task.subtasks.map((subtask) => {
            if (subtask.id === subtaskId)
              return {
                ...subtask,
                status: (subtask.status === 'completed' ? 'pending' : 'completed') as TaskStatus,
              };
            return subtask;
          });
          const allCompleted = updatedSubtasks.every((s) => s.status === 'completed');
          return {
            ...task,
            subtasks: updatedSubtasks,
            status: (allCompleted ? 'completed' : 'in-progress') as TaskStatus,
          };
        }
        return task;
      }),
    );
  };

  const variants = {
    hidden: { opacity: 0, y: -5 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { type: 'spring' as const, stiffness: 500, damping: 30 },
    },
    listVisible: {
      opacity: 1,
      height: 'auto',
      transition: { duration: 0.25, staggerChildren: 0.05, when: 'beforeChildren' as const },
    },
    listHidden: {
      opacity: 0,
      height: 0,
      overflow: 'hidden' as const,
      transition: { duration: 0.2 },
    },
  };

  return (
    <div className="w-full font-sans text-[#e2e8f0]">
      <LayoutGroup>
        <ul className="space-y-1">
          {tasks.map((task, index) => {
            const isExpanded = expandedTasks.includes(task.id);
            const isCompleted = task.status === 'completed';
            return (
              <motion.li
                key={task.id}
                className={index !== 0 ? 'mt-2 pt-2 border-t border-[#3a3633]' : ''}
                initial="hidden"
                animate="visible"
                variants={variants}
              >
                <motion.div
                  className="group flex items-center px-3 py-2.5 rounded-lg hover:bg-[#2c2825] transition-colors cursor-pointer"
                  onClick={() => toggleTaskExpansion(task.id)}
                >
                  <div className="mr-3 shrink-0">
                    <AnimatePresence mode="wait">
                      <motion.div
                        key={task.status}
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                      >
                        {task.status === 'completed' ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                        ) : task.status === 'in-progress' ? (
                          <CircleDotDashed className="w-5 h-5 text-[#818cf8] animate-spin-slow" />
                        ) : (
                          <Circle className="w-5 h-5 text-[#404040]" />
                        )}
                      </motion.div>
                    </AnimatePresence>
                  </div>
                  <div className="flex-1 flex justify-between items-center min-w-0">
                    <div className="truncate pr-4">
                      <span
                        className={`text-sm font-bold ${isCompleted ? 'text-[#9ca3af] line-through decoration-[#3a3633]' : 'text-[#e2e8f0]'}`}
                      >
                        {task.title}
                      </span>
                    </div>
                    <div className="flex shrink-0 gap-2 items-center">
                      {task.dependencies.length > 0 && (
                        <div className="hidden sm:flex gap-1 mr-2">
                          {task.dependencies.map((dep) => (
                            <span
                              key={dep}
                              className="px-1.5 py-0.5 rounded bg-[#2c2825] border border-[#3a3633] text-[9px] font-mono text-[#9ca3af]"
                            >
                              Step {dep} 완료 후
                            </span>
                          ))}
                        </div>
                      )}
                      <span
                        className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${isCompleted ? 'bg-emerald-500/10 text-emerald-500' : task.status === 'in-progress' ? 'bg-[#818cf8]/10 text-[#818cf8]' : 'bg-[#3a3633] text-[#9ca3af]'}`}
                      >
                        {task.status.replace('-', ' ')}
                      </span>
                    </div>
                  </div>
                </motion.div>
                <AnimatePresence mode="wait">
                  {isExpanded && task.subtasks.length > 0 && (
                    <motion.div
                      className="relative overflow-hidden ml-[22px] pl-4 border-l-2 border-dashed border-[#3a3633] mt-2 mb-3"
                      variants={variants}
                      initial="listHidden"
                      animate="listVisible"
                      exit="listHidden"
                      layout
                    >
                      <ul className="space-y-1">
                        {task.subtasks.map((subtask) => {
                          const subtaskKey = `${task.id}-${subtask.id}`;
                          const isSubExp = expandedSubtasks[subtaskKey];
                          return (
                            <motion.li
                              key={subtask.id}
                              className="flex flex-col"
                              variants={variants}
                              layout
                            >
                              <div
                                className="flex items-center p-1.5 rounded-md hover:bg-[#2c2825] cursor-pointer transition-colors"
                                onClick={() => toggleSubtaskExpansion(task.id, subtask.id)}
                              >
                                <div
                                  className="mr-2"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleSubtaskStatus(task.id, subtask.id);
                                  }}
                                >
                                  {subtask.status === 'completed' ? (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                  ) : subtask.status === 'in-progress' ? (
                                    <CircleDotDashed className="w-4 h-4 text-[#818cf8] animate-spin-slow" />
                                  ) : (
                                    <Circle className="w-4 h-4 text-[#404040]" />
                                  )}
                                </div>
                                <span
                                  className={`text-xs ${subtask.status === 'completed' ? 'text-[#6b7280] line-through' : 'text-[#d1d5db]'}`}
                                >
                                  {subtask.title}
                                </span>
                              </div>
                              <AnimatePresence mode="wait">
                                {isSubExp && (
                                  <motion.div
                                    className="ml-6 pl-3 border-l border-dashed border-[#404040] py-2"
                                    variants={variants}
                                    initial="listHidden"
                                    animate="listVisible"
                                    exit="listHidden"
                                    layout
                                  >
                                    <p className="text-[11px] text-[#9ca3af] mb-2 leading-relaxed">
                                      {subtask.description}
                                    </p>
                                    <div className="flex flex-wrap items-center gap-1.5">
                                      <span className="text-[9px] font-mono text-[#6b7280] uppercase">
                                        Tools:
                                      </span>
                                      {subtask.tools.map((tool) => (
                                        <span
                                          key={tool}
                                          className="px-1.5 py-0.5 rounded bg-[#1e1b18] border border-[#3a3633] text-[9px] font-mono text-[#818cf8]"
                                        >
                                          {tool}
                                        </span>
                                      ))}
                                    </div>
                                  </motion.div>
                                )}
                              </AnimatePresence>
                            </motion.li>
                          );
                        })}
                      </ul>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.li>
            );
          })}
        </ul>
      </LayoutGroup>
    </div>
  );
}

export default SpotterAgentWorkflow;
