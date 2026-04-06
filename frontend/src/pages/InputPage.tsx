/**
 * 조건 입력 화면 — 업종, 브랜드, 예산, 위치 선택 → 시뮬레이션 실행
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { analyzeLocation } from '../api/client';
import { useSimulation } from '../contexts/SimulationContext';
import type { SimulationInput } from '../types';

const DONG_LIST = [
  "공덕동", "아현동", "도화동", "용강동", "대흥동", 
  "염리동", "신수동", "서강동", "서교동", "합정동", 
  "망원1동", "망원2동", "연남동", "성산1동", "성산2동", "상암동"
];

function InputPage() {
  const navigate = useNavigate();
  const { setSimulationResult } = useSimulation();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    industry: '카페',
    brandName: '',
    targetDong: DONG_LIST[0],
    existingStores: [''],
    budget: '',
    rent: '',
    simulateScenario: {
      competitorEntry: false,
      rentIncrease: false,
    }
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, checked } = e.target;
    setFormData(prev => ({ 
      ...prev, 
      simulateScenario: { ...prev.simulateScenario, [name]: checked } 
    }));
  };

  const handleExistingStoreChange = (index: number, value: string) => {
    const newStores = [...formData.existingStores];
    newStores[index] = value;
    setFormData(prev => ({ ...prev, existingStores: newStores }));
  };

  const addExistingStore = () => {
    setFormData(prev => ({ ...prev, existingStores: [...prev.existingStores, ''] }));
  };

  const removeExistingStore = (index: number) => {
    const newStores = formData.existingStores.filter((_val, i) => i !== index);
    setFormData(prev => ({ ...prev, existingStores: newStores }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    // Map formData to SimulationInput
    let businessType: "cafe" | "restaurant" | "convenience" = "cafe";
    if (formData.industry === "음식점") businessType = "restaurant";
    if (formData.industry === "편의점") businessType = "convenience";

    const scenarios = [];
    if (formData.simulateScenario.competitorEntry) scenarios.push("competitor_entry");
    if (formData.simulateScenario.rentIncrease) scenarios.push("rent_increase");

    const inputData: SimulationInput = {
      business_type: businessType,
      brand_name: formData.brandName,
      target_district: formData.targetDong,
      existing_stores: formData.existingStores.map(addr => ({ district: "", address: addr, monthly_revenue: 0 })),
      initial_investment: Number(formData.budget) || 0,
      monthly_rent: Number(formData.rent) || 0,
      simulation_months: 12,
      scenarios: scenarios
    };

    console.log("Submitting Simulation Form: ", inputData);
    
    if (!inputData.brand_name) {
      console.warn("경고: 브랜드명이 비어 있어 제출이 중단될 수 있습니다.");
    }

    try {
      console.log("서버에 요청 보냄! (POST /api/analyze)");
      console.log("전송 데이터 상세: ", JSON.stringify(inputData, null, 2));

      const result = await analyzeLocation(inputData);
      console.log("Analysis Result Received:", result);
      
      if (result.status === "success") {
        // 결과 상태 업데이트
        setSimulationResult(result.data);
        // 즉시 지도 페이지로 이동
        navigate('/map');
      } else {
        alert("분석 실패: " + result.message);
      }
    } catch (error) {
      console.error("서버 통신 오류 상세: ", error);
      alert("서버 통신 중 오류가 발생했습니다. 개발자 도구(F12) 콘솔을 확인하세요.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 lg:p-8 bg-white shadow rounded-lg mt-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">시뮬레이션 조건 입력</h2>
        <p className="mt-2 text-sm text-gray-600">
          신규 프랜차이즈 출점 후보지를 검토하기 위한 매장 정보 및 시뮬레이션 변수를 입력해 주세요.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* 1. 기본 정보 */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-gray-900 border-b pb-2">1. 매장 기본 정보</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">업종</label>
              <select
                name="industry"
                value={formData.industry}
                onChange={handleInputChange}
                className="w-full rounded-md border border-gray-300 p-2 focus:border-blue-500 focus:ring-blue-500"
              >
                <option value="카페">☕ 카페</option>
                <option value="음식점">🍔 음식점</option>
                <option value="편의점">🏪 편의점</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">브랜드명</label>
              <input
                type="text"
                name="brandName"
                placeholder="예: 매가커피"
                value={formData.brandName}
                onChange={handleInputChange}
                required
                className="w-full rounded-md border border-gray-300 p-2 focus:border-blue-500 focus:ring-blue-500"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">후보지 (마포구 내 행정동)</label>
              <select
                name="targetDong"
                value={formData.targetDong}
                onChange={handleInputChange}
                className="w-full rounded-md border border-gray-300 p-2 focus:border-blue-500 focus:ring-blue-500"
              >
                {DONG_LIST.map(dong => (
                  <option key={dong} value={dong}>{dong}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* 2. 재무 조건 */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-gray-900 border-b pb-2">2. 재무 관련 정보</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">초기 투자 예산 (만원)</label>
              <input
                type="number"
                name="budget"
                placeholder="예: 5000"
                value={formData.budget}
                onChange={handleInputChange}
                className="w-full rounded-md border border-gray-300 p-2 focus:border-blue-500 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">월 임대료 (만원, 0 입력 시 자동 추정)</label>
              <input
                type="number"
                name="rent"
                placeholder="예: 300"
                value={formData.rent}
                onChange={handleInputChange}
                className="w-full rounded-md border border-gray-300 p-2 focus:border-blue-500 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* 3. 기존 매장 정보 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b pb-2">
            <h3 className="text-lg font-medium text-gray-900">3. 기존 운영 매장 (카니발리제이션 분석용)</h3>
            <button
              type="button"
              onClick={addExistingStore}
              className="px-3 py-1 text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded"
            >
              + 매장 추가
            </button>
          </div>
          {formData.existingStores.map((store, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                type="text"
                placeholder="도로명 주소 등 기존 매장 위치 입력"
                value={store}
                onChange={(e) => handleExistingStoreChange(index, e.target.value)}
                className="flex-1 rounded-md border border-gray-300 p-2 focus:border-blue-500 focus:ring-blue-500"
              />
              {formData.existingStores.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeExistingStore(index)}
                  className="px-3 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded"
                >
                  제거
                </button>
              )}
            </div>
          ))}
        </div>

        {/* 4. 시나리오 변수 */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-gray-900 border-b pb-2">4. 분석 시나리오(What-If)</h3>
          <div className="flex flex-col space-y-3 sm:flex-row sm:space-y-0 sm:space-x-6">
            <label className="flex items-center">
              <input
                type="checkbox"
                name="competitorEntry"
                checked={formData.simulateScenario.competitorEntry}
                onChange={handleCheckboxChange}
                className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">핵심 경쟁사 동시 진입 가정</span>
            </label>
            <label className="flex items-center">
              <input
                type="checkbox"
                name="rentIncrease"
                checked={formData.simulateScenario.rentIncrease}
                onChange={handleCheckboxChange}
                className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">1년 내 임대료 20% 상승 가정</span>
            </label>
          </div>
        </div>

        {/* 하단 버튼 */}
        <div className="pt-6 border-t flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className={`px-6 py-3 font-semibold text-white rounded-md shadow focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors duration-200 ${
              loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'
            }`}
          >
            {loading ? 'AI 분석 중...' : '시뮬레이션 실행하기'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default InputPage;
