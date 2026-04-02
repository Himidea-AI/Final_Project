from typing import List, Optional
from pydantic import BaseModel, Field
from .models import SimulationRequest, SimulationResult

class AgentState(BaseModel):
    """
    LangGraph 에이전트 간의 워크플로우를 관통하며 지속적으로 유지·변경될 전역 상태.
    LGP 스택의 설계에 따라, 노드들이 결과를 이곳에 업데이트합니다.
    """
    request: SimulationRequest = Field(..., description="사용자 초기 요청 사항")
    
    # 1. 수집된 맥락(Context) 데이터 상태 (이후 트랙 A 데이터 파이프라인에서 채움)
    raw_population_data: Optional[dict] = Field(default=None, description="유동/주거 인구 데이터")
    raw_commercial_data: Optional[dict] = Field(default=None, description="상권 및 업종 데이터")
    
    # 2. 분석 중간 결과 상태
    market_analysis_summary: str = Field(default="", description="상권 분석가의 중간 요약 데이터")
    competition_analysis_summary: str = Field(default="", description="경쟁/카니발리제이션 분석 중간 요약")
    
    # 3. 에이전트 순환 제어 및 로그 기록
    messages: List[str] = Field(default_factory=list, description="에이전트 판단 과정 등의 메시지 로그")
    is_completed: bool = Field(default=False, description="충분한 분석이 이루어져 시뮬레이션 종료 가능 여부")
    
    # 4. 최종 결과물
    final_result: Optional[SimulationResult] = Field(default=None, description="분석이 끝난 후 프론트엔드로 전달할 결과")
