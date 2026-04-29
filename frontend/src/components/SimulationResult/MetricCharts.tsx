import React from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from 'recharts';
import { motion } from 'framer-motion';
import { Target, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';
import { AnalysisMetrics } from '../../types';

interface MetricChartsProps {
  metrics: AnalysisMetrics;
}

const GRADE_COLORS = {
  EXCELLENT: '#10B981', // Emerald-500
  GOOD: '#3B82F6', // Blue-500
  NORMAL: '#EAB308', // Yellow-500
  RISKY: '#EF4444', // Red-500
};

const GRADE_LABELS = {
  EXCELLENT: '최우수 상권',
  GOOD: '우수 상권',
  NORMAL: '보통 상권',
  RISKY: '주의 상권',
};

const MetricCharts: React.FC<MetricChartsProps> = ({ metrics }) => {
  const themeColor = GRADE_COLORS[metrics.district_grade] || GRADE_COLORS.NORMAL;

  // Radar 데이터 (경쟁 점수 시각화)
  const radarData = [
    { subject: '경객 수', A: (metrics.competition_score || 0.7) * 100, fullMark: 100 },
    { subject: '매출 성장', A: Math.min((metrics.growth_rate || 5) * 5, 100), fullMark: 100 },
    { subject: '임대료 적정성', A: metrics.rent_affordability === 'SAFE' ? 90 : 40, fullMark: 100 },
    { subject: '유동 인구', A: 85, fullMark: 100 },
    { subject: '정주 인구', A: 65, fullMark: 100 },
  ];

  // 성장률 바 차트 데이터
  const growthData = [{ name: '전년 대비 성장률', value: metrics.growth_rate || 0 }];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 bg-white/50 backdrop-blur-md rounded-2xl border border-gray-100 shadow-xl">
      {/* 1. 등급 요약 카드 */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="flex flex-col items-center justify-center p-6 rounded-2xl bg-white shadow-lg border-t-8 h-full"
        style={{ borderTopColor: themeColor }}
      >
        <span className="text-xs font-black text-gray-300 uppercase tracking-widest mb-2">
          Total Grade
        </span>
        <motion.div
          initial={{ y: 10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.8 }}
          className="text-6xl font-black mb-4 tracking-tighter"
          style={{ color: themeColor }}
        >
          {metrics.district_grade}
        </motion.div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-gray-50 text-gray-700 font-bold border border-gray-100 shadow-sm">
          {metrics.district_grade === 'EXCELLENT' || metrics.district_grade === 'GOOD' ? (
            <CheckCircle size={18} className="text-emerald-500" />
          ) : (
            <AlertTriangle size={18} className="text-amber-500" />
          )}
          {GRADE_LABELS[metrics.district_grade]}
        </div>
      </motion.div>

      {/* 2. 성장성 바 차트 */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.2, duration: 0.6 }}
        className="p-6 rounded-2xl bg-white shadow-lg border border-gray-50 h-full"
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="p-2 bg-blue-50 rounded-lg">
            <TrendingUp size={18} className="text-blue-500" />
          </div>
          <h3 className="font-black text-gray-800 tracking-tight">성장 추이 분석</h3>
        </div>
        <div className="h-[120px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={growthData} layout="vertical">
              <XAxis type="number" hide domain={[0, 30]} />
              <YAxis dataKey="name" type="category" hide />
              <Tooltip
                cursor={{ fill: 'rgba(59, 130, 246, 0.05)' }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="bg-white/90 backdrop-blur-md p-3 shadow-2xl rounded-xl border border-blue-50">
                        <p className="text-[0.625rem] font-bold text-gray-400 uppercase mb-1">
                          매출 성장률
                        </p>
                        <span className="text-xl font-black text-blue-600">
                          +{payload[0].value}%
                        </span>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Bar
                dataKey="value"
                radius={[0, 10, 10, 0]}
                barSize={45}
                animationDuration={2000}
                animationBegin={500}
              >
                <Cell fill={themeColor} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-[0.6875rem] text-center text-gray-400 font-medium mt-2 leading-relaxed">
          과거 12개월 대비 평균 매출이{' '}
          <span className="font-bold underline" style={{ color: themeColor }}>
            {metrics.growth_rate}% 쾌속 성장
          </span>{' '}
          중입니다.
        </p>
      </motion.div>

      {/* 3. 경쟁 분석 레이더 차트 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.6 }}
        className="p-6 rounded-2xl bg-white shadow-lg border border-gray-50 md:col-span-2"
      >
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-red-50 rounded-lg">
              <Target size={18} className="text-red-500" />
            </div>
            <h3 className="font-black text-gray-800 tracking-tight">5차원 입지 정밀 진단</h3>
          </div>
          <span className="text-[0.625rem] font-black bg-gray-100 px-2 py-1 rounded text-gray-500">
            AI AGENT ENGINE v1.2
          </span>
        </div>
        <div className="h-[280px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
              <PolarGrid stroke="#f1f5f9" />
              <PolarAngleAxis
                dataKey="subject"
                tick={{ fontSize: 11, fill: '#94a3b8', fontWeight: 700 }}
              />
              <Radar
                name="Score"
                dataKey="A"
                stroke={themeColor}
                fill={themeColor}
                fillOpacity={0.3}
                animationDuration={2500}
                animationBegin={800}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-3 gap-2 mt-4">
          <div className="p-3 bg-gray-50 rounded-xl text-center">
            <p className="text-[0.5625rem] font-bold text-gray-400 uppercase">경쟁 지수</p>
            <p className="text-sm font-black text-gray-700">
              {(metrics.competition_score * 10).toFixed(1)}/10
            </p>
          </div>
          <div className="p-3 bg-gray-50 rounded-xl text-center">
            <p className="text-[0.5625rem] font-bold text-gray-400 uppercase">임대료</p>
            <p className="text-sm font-black text-gray-700">{metrics.rent_affordability}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-xl text-center">
            <p className="text-[0.5625rem] font-bold text-gray-400 uppercase">종합 점수</p>
            <p className="text-sm font-black text-blue-600">84.2</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default MetricCharts;
