# ABM 시뮬레이션 코드 리뷰 (2026-05-09)

범위: `backend/src/simulation/` 전체  |  시점: 2026-05-09

> **이 문서는 비개발자도 읽을 수 있도록 풀어 쓴 버전입니다.** 기술 용어가 처음 등장할 때마다 괄호 안에 쉬운 설명을 붙였습니다. 코드 위치(파일:줄번호)와 비용 숫자, 계층 비율 등 핵심 수치는 그대로 보존되어 있습니다.

---

## 한 줄 진단

**페르소나(에이전트의 직업·취미·성향·배경 등 특성 묶음) 주입 실패가 무음 묵살(에러가 나도 로그를 남기지 않고 그냥 넘어감) + 정책(에이전트의 의사결정 규칙. 역할 × 날씨 × 시간대 조합) 다양성 의도(55) vs 실제(11) 불일치 + 모델명 하드코딩(코드 안에 모델 이름을 직접 박아둠).**

쉽게 말해, 가상 주민에게 다양한 성격을 입히는 단계가 조용히 실패해도 알아채기 어렵고, 시간대별로 행동이 달라야 할 정책이 사실상 1/5 수준으로 단조롭게 작동하며, 실제 호출되는 AI 모델이 설정 파일의 값과 다르게 박혀 있다는 뜻입니다.

## 비전문가용 요약

- **무엇이 문제인가요?**
  - 1,000 명 에이전트(시뮬레이션 안에서 독립적으로 행동하는 가상 개인. 여기서는 마포구 가상 주민 1,000 명)에 7,187 명 페르소나(직업/취미/배경)를 입히는 단계가 실패해도 로그가 남지 않습니다. 운영 중 "Nemotron(NVIDIA 의 LLM. 대규모 합성 페르소나 7,187 명을 생성한 출처) 풀이 실제로 적용된 시뮬인지, 아니면 가장 기본 정보만 적용된 시뮬인지" 결과만 보고는 판별할 수 없습니다.
  - 정책 카탈로그 v2 는 (역할 × 날씨 × 시간대) = 55 개의 서로 다른 정책으로 설계됐으나, LLM(Large Language Model. ChatGPT 같은 대규모 언어 모델)에 보내는 프롬프트(LLM 에게 보내는 입력 문장) 함수가 시간대 정보를 받지 않아서, 실제로는 11 개를 5 번 그대로 복사한 상태입니다. 시간대별 다양성이 1/5 로 줄어든 셈입니다.
  - Tier S(에이전트 비용·다양성 계층 중 가장 비싼 LLM 등급) 모델명이 `gpt-5.4-nano` 로 하드코딩되어 있어 설정 파일을 바꿔도 반영되지 않습니다. 비용 추적도 부정확해집니다.
- **얼마나 위험한가요?** 결과 무결성(시뮬레이션 결과를 신뢰할 수 있는지) 측면에서 가장 높은 등급(P0)입니다. 결과 신뢰도가 떨어집니다.
- **얼마나 걸리나요?** 합계 1 ~ 1.5 일.

## 가장 시급한 4 가지

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| H-1 | `simulation/agents.py:858-879` | `except Exception: pass` 무음 묵살 (예외가 나도 그냥 넘어감) | `logger.warning` (경고 로그 남기기) |
| H-2 | `simulation/policy_generator.py:254` | `build_prompt` 가 `time_block`(아침·점심·오후·저녁·심야 5 단계 시간대 구분) 인자 없음 → 정책 다양성 1/5 | 함수 시그니처에 시간대 인자 추가 |
| H-3 | `simulation/brain.py:985` | 모델명 `gpt-5.4-nano` 하드코딩 | `self.cfg.tier_s_model` 사용 (설정값 참조) |
| H-4 | `simulation/runner.py:1307-1309` | `new_store_role_dist` 가 멀티데이(여러 날) 시뮬에서 마지막 날만 반영 | 일자별 누적 로직 추가 |

---

## 1. 아키텍처 개요

이 시뮬레이션은 마포구 1,000 명의 가상 주민(에이전트)이 하루 동안 어떻게 움직이며 어느 매장을 방문하는지 시간 단위로 재현하는 ABM(Agent-Based Model. 개별 에이전트의 행동 규칙을 정의하고 시뮬레이션해 집단 패턴을 관찰하는 기법)입니다. 단순한 규칙 기반 시뮬레이션이 아니라 LLM(대규모 언어 모델)과 하드코딩(코드에 직접 박아 넣은) 로직을 섞은 하이브리드(혼합형) 구조라는 점이 특징입니다.

### 하이브리드 설계가 무엇인가

가장 중요한 설계 결정은 "비싼 LLM 호출을 최소화하면서도 결과의 다양성은 유지"하는 것입니다. 이를 위해 LLM 은 (역할 × 날씨) 조합인 11 회만 호출해 정책의 베이스(기초)를 생성하고, 거기에 시간대(time_block) 5 단계를 코드로 곱해 최종적으로 55 개의 정책 엔트리(항목)를 가진 `POLICY_CATALOG_V2`(55 개 정책 엔트리를 담은 카탈로그)를 만듭니다. 즉, LLM 호출 비용은 11 회분이지만 결과는 55 개의 고유 정책처럼 보이도록 의도된 구조입니다. 이 설계 의도가 실제 코드에서 지켜지지 않은 부분이 본 리뷰의 핵심 이슈 H-4 입니다.

### Tier S/A/B 라우팅(어떤 에이전트를 어떤 모델로 보낼지 분기)

에이전트 1,000 명을 모두 LLM 으로 돌리면 비용이 폭발하므로, 중요도와 다양성에 따라 세 계층(Tier)으로 나눕니다.

- **Tier S(50 명)**: 가장 정성적인 사고가 필요한 핵심 에이전트. Anthropic Haiku(Anthropic 회사의 LLM 등급. 비교적 정성적이고 비싼 모델)에 ephemeral cache(짧은 시간 동안 LLM 호출 결과를 재사용해 토큰 비용을 줄이는 기능)를 붙여 호출합니다.
- **Tier A(200 명)**: 적당한 다양성이 필요한 중간 계층. Gemini Flash-Lite(Google 의 LLM 등급. Haiku 보다 더 저렴) 사용.
- **Tier B(750 명)**: LLM 없이 순수 Python 규칙 엔진(if-else 로직)으로만 결정. 비용 사실상 0.

이 비율(50/200/750)은 메모리 노트의 "1000 명, 약 $0.7/일" 목표에 맞춘 것입니다.

### 계층 플래닝 (Stanford UIST 2023)

스탠퍼드의 Generative Agents (Stanford UIST 2023)(에이전트가 LLM 으로 일일 계획을 세우고 시간대별로 행동하는 논문)에서 제시한 계층적 플래닝을 따릅니다. 하루가 시작될 때 Tier S 에이전트는 daily plan / 일일 계획(에이전트가 하루 동안 무엇을 할지 미리 LLM 으로 한 번에 생성해 두고 시간대마다 조회)을 LLM 으로 한 번만 batch 호출(10 명을 한 LLM 호출로 묶어 round-trip(요청을 보내고 응답이 돌아오는 1 사이클) 비용을 줄임)로 생성하고, 시간대마다 그 계획에서 슬롯을 조회하는 방식입니다. 매 시각마다 LLM 을 부르지 않고 하루 한 번만 부르므로 비용이 24 배 절약됩니다.

### 실행 흐름

```
run_simulation()
  +-- spawn_agents()                  # 1000 Agent 생성, Tier 배분(S:50 A:200 B:750)
  +-- generate_daily_plans_batch()    # Tier S 일일 계획 LLM 배치 생성 (10명/call)
  +-- for hour in 0..23:              # 24시간 루프
       +-- GameMaster.adjust()        # 날씨/임대료/휴일/급여일/PM2.5 적용
       +-- score_stores_batch()       # 15개 인자로 매장 점수를 한꺼번에 계산
       +-- Brain.smart_decide()/_rule_decide()  # Tier 별 방문 결정
       +-- 결과를 visits_log -> density_grid -> SimulationResult 로 집계
```

> **GameMaster(시뮬레이션 환경 변수 — 날씨·임대료·휴일 등 — 를 시간마다 조정하는 클래스)** 가 매시간 외부 환경을 바꾸고, 그 환경 위에서 에이전트가 점수를 계산해 매장을 방문하는 구조입니다.

흐름의 핵심은 spawn → daily plan → 24 시간 루프 → 결과 집계 순으로 한 방향 데이터 파이프라인이라는 점입니다. 각 단계에서 어디가 깨지면 어떤 출력이 망가지는지가 본 리뷰의 핵심 시각입니다.

---

## 2. 코드 모듈 현황

`backend/src/simulation/` 디렉토리는 8 개 주요 파일로 구성됩니다. 각 파일이 어떤 책임을 지는지 정리합니다.

`agents.py` 는 Agent 데이터클래스(에이전트 한 명을 표현하는 자료 구조)와 1,000 명 에이전트 생성을 담당하는 `spawn_agents()`, 그리고 Tier B 에이전트가 LLM 없이 결정하는 `_rule_decide()` 를 담고 있습니다. 본 리뷰의 H-1(페르소나 주입 무음 묵살)이 여기서 발생합니다.

`brain.py` 는 LLM Brain(에이전트의 두뇌 역할)의 Tier S/A 라우팅과 일일 계획 배치 생성(`generate_daily_plans_batch`)을 담당합니다. Anthropic → OpenAI → Ollama → mock(가짜 응답. 테스트용 또는 실제 LLM 응답 흉내)으로 이어지는 자동 fallback / 폴백(주 경로 실패 시 대체 경로로 전환) 체인도 여기 있습니다. H-2(모델명 하드코딩)가 985 라인에서 발생합니다.

`config.py` 는 시뮬레이션 파라미터(에이전트 수, Tier 분포, 날씨 확률 등)와 비용 추정 함수(`estimate_cost`)를 담습니다. PRICING 표(LLM 단가 표)가 2026-05-09 기준으로 갱신되어 있습니다.

`persona_pool.py` 는 Nemotron 7,187 페르소나 parquet(컬럼 단위로 저장하는 효율적 파일 형식)를 로드하고 인구 분포에 맞춰 샘플링합니다. 2026-05-09 에 `_uuid_by_idx()` 캐시 최적화가 들어갔습니다.

`policy_executor.py` 는 매장 방문 의사결정의 핵심인 15 인자 점수 함수(`score_store`)와 그 벡터화(반복문 대신 numpy 등으로 한 번에 행렬 연산) 버전(`score_stores_batch`), 그리고 후보 매장을 미리 거르는 `_prefilter_candidates()` 를 담습니다.

`policy_generator.py` 는 LLM 호출로 `POLICY_CATALOG_V2` 55 엔트리를 생성하는 모듈인데, 254 라인의 `build_prompt()` 가 `time_block` 인자를 받지 않아 H-4 가 발생합니다.

`runner.py` 는 메인 오케스트레이션(전체 흐름 조율)입니다. `run_simulation()` 진입점, 24 시간 루프, `SimulationResult`(결과 데이터 구조) 직렬화가 모두 여기 있습니다. H-3(`new_store_role_dist` 멀티데이 미누적), M-1(`daily_visits_std` 하드코딩 0.0), L-1(visits_log 미리셋)이 여기서 나옵니다.

`world.py` 는 World/Store 등 세계 상태 컨테이너(시뮬레이션의 환경 정보를 모아 두는 객체)인데, M-2 의 `world.agent_by_id` 가 정의만 있고 채워지지 않아 정책 실행기가 O(N)(에이전트 수에 비례한 시간) fallback 으로 떨어지는 이슈가 있습니다.

---

## 3. 하이브리드 생성 검증 (H-4 CRITICAL)

### 설계 의도

`POLICY_CATALOG_V2` 는 5 개 역할(직장인/주부/학생/노년/관광객) × 2 개 날씨(맑음/비) × 5 개 시간대(TimeBlock — 아침·점심·오후·저녁·심야 5 단계) = 50 개에 사장(owner) 5 개를 더해 총 55 개 고유 엔트리를 갖도록 설계됐습니다. LLM 은 (역할 × 날씨) 조합 11 회만 호출해 베이스 정책을 만들고, 시간대 차이는 코드에서 곱해 비용을 11/55 로 줄이는 구조입니다.

### 무엇이 깨졌는가

`backend/src/simulation/policy_generator.py:254` 의 `build_prompt(role: Role, weather: Weather)` 시그니처(함수가 받는 인자 목록)에 `time_block` 인자가 빠져 있습니다. 따라서 55 개의 카탈로그 키 각각에 대해 LLM 을 호출하더라도, 시간대 정보가 프롬프트에 들어가지 않아 같은 11 개의 출력이 5 번 복제되는 결과가 됩니다.

### 왜 중요한가

설계 문서와 메모리 노트(2026-05-07 갱신)에는 "LLM 11 회 base + 하드코딩 5 배 확장 = 55 고유 정책"이라고 기록돼 있지만, 실제 시뮬레이션의 정책 다양성은 1/5 수준입니다. 이는 점심시간 직장인과 심야 직장인이 사실상 같은 정책으로 행동한다는 뜻이며, 시뮬레이션 결과의 시간대별 패턴이 실제보다 평탄해집니다. ABM 의 핵심 자산인 "시간대 다이내믹스(시간대마다 달라지는 행동 패턴)"가 설계 의도만큼 표현되지 않습니다.

### 어떻게 고치나

`build_prompt` 시그니처에 `time_block: TimeBlock` 인자를 추가하고, 시간대별 한국어 설명을 프롬프트에 명시적으로 주입해야 합니다. 예를 들면 다음과 같습니다.

```python
def build_prompt(role: Role, weather: Weather, time_block: TimeBlock) -> str:
    tb_desc = {
        TimeBlock.MORNING:   "오전 출근/등교 시간대",
        TimeBlock.LUNCH:     "점심시간 직장인 밀집",
        TimeBlock.AFTERNOON: "오후 여가/쇼핑",
        TimeBlock.EVENING:   "저녁 퇴근 후 외식",
        TimeBlock.NIGHT:     "심야 주류/편의점",
    }[time_block]
    return PROMPT_TEMPLATE.format(
        role_desc=ROLE_DESCRIPTIONS[role],
        weather=weather,
        time_block_desc=tb_desc,
        dongs=", ".join(MAPO_DONGS),
    )
```

이 수정은 LLM 호출 횟수를 11 → 55 회로 늘리지만, 캐시 활용을 잘하면 추가 비용은 작으며, 무엇보다 설계 의도와 실제 동작을 일치시킵니다.

---

## 4. Tier 정책 (S/A/B)

### 계층별 역할

**Tier S 는 50 명**으로 가장 정성적인 사고가 필요한 에이전트입니다. Anthropic claude-haiku-3-5 (Anthropic Haiku 등급) 에 ephemeral cache 를 붙여 호출하며, 10 명씩 묶어 batch 호출하므로 round-trip 비용이 1/10 입니다. cache_read 단가(캐시에서 읽힌 토큰의 가격. 일반 input 의 1/10 정도)가 $0.10/M(백만 토큰당 0.10 달러)으로 일반 input 의 1/10 이라 페르소나 텍스트를 캐시하면 90% 가 절약됩니다.

**Tier A 는 200 명**으로 적당한 다양성이 필요한 중간 계층입니다. Gemini Flash-Lite 를 사용하며 단가가 매우 낮아 배치 없이도 비용 부담이 적습니다.

**Tier B 는 750 명**으로 가장 큰 비중을 차지하며, LLM 을 전혀 호출하지 않고 `_rule_decide()` 의 Python 규칙으로만 결정합니다. 비용은 사실상 0 이며 ABM 의 비용 효율성을 떠받치는 핵심입니다.

### H-2: 모델명 하드코딩

`backend/src/simulation/brain.py:985` 의 `_generate_thoughts_openai` 메서드는 다음과 같이 모델명을 직접 박아두고 있습니다.

```python
model="gpt-5.4-nano"  # self.cfg.tier_s_model 무시
```

문제는 한 줄 더 아래(line 1004)에서 로그에는 `self.cfg.tier_s_model` 값을 기록한다는 점입니다. 즉, 운영자는 로그를 보고 "config 에 명시한 모델이 실제로 호출됐다"고 믿지만, 실상은 `gpt-5.4-nano` 가 호출됩니다. 이는 false attribution(잘못된 출처 표기) 이며 비용 추적과 모델 비교 실험을 모두 망가뜨립니다.

수정은 단순합니다. `model=self.cfg.tier_s_model` 로 바꾸거나, 사고(thought)와 의사결정(decision)을 분리하고 싶다면 `tier_s_thought_model` 이라는 별도 config 필드를 추가합니다.

### auto-downgrade 체인의 위험 (자동 강등 — 더 싸거나 약한 모델로 자동 전환)

Brain 은 Anthropic 호출 실패 시 OpenAI → Ollama → mock 순으로 자동 폴백합니다. 안정성을 위한 합리적 설계지만, 운영 중 mock 까지 도달했는데도 시뮬레이션은 계속 돌아간다면 결과가 실제 LLM 출력처럼 보이지만 사실은 랜덤 mock 일 수 있습니다. 폴백 시 명시적 경고 로그와 결과 메타에 `actual_brain_used` 필드(실제로 어떤 LLM 이 사용됐는지 기록)를 남기는 것을 권장합니다.

---

## 5. 비용 모델

### PRICING 표 (2026-05-09 기준)

`config.py` 의 PRICING 상수에는 Haiku input $1.00/M, cache_read $0.10/M(90% 절약), output $5.00/M, Gemini Flash-Lite 약 $0.15/M 이 명시돼 있습니다. 이 단가는 2026-05-09 기준이므로 정기적으로 갱신해야 합니다.

> **/M 의 의미**: 토큰(LLM 의 입출력 단위로, 대략 한국어 1글자가 1~2 토큰) 100 만 개당 가격. 예) Haiku input $1.00/M = 100 만 토큰 입력에 1 달러.

### estimate_cost() 의 한계

`config.py:250-281` 의 `estimate_cost()` 는 Tier S 의 동적 토큰 100 개와 캐시된 페르소나 토큰 500 개/에이전트/시간을 가정해 계산합니다. 그러나 사고 호출(thought call — 에이전트가 "왜 그 결정을 했는지" 생각을 LLM 으로 생성하는 호출)이 누락돼 있어 실제 비용은 추정치보다 큽니다.

### 메모리 노트와의 델타(차이)

메모리 노트는 ABM 1,000 명 시뮬레이션이 하루 약 **$0.7/일** 라고 기록하지만, 현재 `estimate_cost()` 는 **$1.20 ~ 1.34/일** 를 반환합니다. 여기에 thought call 까지 포함하면 더 올라갈 가능성이 있습니다. 이는 L-2 이슈로, `estimate_cost()` 에 `thought_calls_per_day` 파라미터를 추가하고, 실측 비용과 정기적으로 대조해야 합니다.

### 왜 중요한가

비용 모델은 단순한 회계 도구가 아니라 ABM 을 운영 시스템으로 끌어올릴 수 있는지를 결정하는 핵심 지표입니다. 추정치가 실측보다 작으면 운영 결정(에이전트 수 늘리기, Tier S 비율 올리기)이 잘못된 가정 위에서 이뤄집니다.

---

## 6. 페르소나 스키마 (5 레이어 — 5 단계의 정보 층)

### 5 개 레이어 구조

페르소나는 5 개 레이어로 구성됩니다.

- **L0 (기본)**: agent_id, dong(동), age, sex, tier 같은 ProfileBuilder/RDS(관계형 데이터베이스. AWS RDS) 기반 정보입니다.
- **L1 (Nemotron)**: occupation(직업), education_level(학력), persona_text(자기소개 텍스트), hobbies(취미), professional_persona(직업적 성향), cultural_background(문화 배경), career_goals(진로 목표) 등 7,187 명의 페르소나 parquet 에서 가져온 풍부한 텍스트입니다.
- **L2 (메모리)**: memory_stream(과거 행동 기록), daily_plan, current_goal 같은 런타임(시뮬 진행 중) 누적 상태입니다.
- **L3 (내부 상태)**: hunger(허기), fatigue(피로), budget_left_today(오늘 남은 예산), mood(기분) 같은 시간대별 변화 변수입니다.
- **L5 (사회)**: social_network(사회 관계망), influence_score(영향력 점수) 같은 사회적 영향력 정보입니다.

### persona_pool.py 최적화 (2026-05-09)

`backend/src/simulation/persona_pool.py:123` 의 `_uuid_by_idx()` 가 2026-05-09 에 캐시 방식으로 개선됐습니다. 이전에는 `sample()` 내 `exclude_uuids` 분기에서 `df.iloc[i].get("uuid")` 를 반복 호출했는데, 5K 에이전트 × 약 500 후보 = 2.5M 회의 iloc 호출(pandas 의 인덱스 접근 — 느린 연산)이 발생해 spawn 단계가 30 ~ 120 초씩 걸렸습니다. 현재는 dict 사전 캐시(파이썬 딕셔너리에 미리 저장)를 통해 O(1)(상수 시간) 룩업으로 바뀌어 spawn 시간이 크게 줄었습니다.

### H-1 CRITICAL: PersonaPool inject 무음 묵살

`backend/src/simulation/agents.py:859-879` 에서 페르소나 주입은 다음과 같이 처리됩니다.

```python
try:
    profile = persona_pool.sample(sex, age, rng=rng, exclude_uuids=used_uuids)
    # ... inject fields
except Exception:
    pass  # 실패해도 조용히 L0만 유지
```

### 왜 중요한가

parquet 파일이 깨졌거나, 컬럼 스키마(데이터 표의 구조)가 바뀌었거나, sample() 의 인구 분포 매칭이 0 후보를 반환했다면 페르소나 주입이 실패합니다. 그런데 `except Exception: pass` 가 모든 예외를 삼키므로, 운영자는 "Nemotron 풀이 적용된 시뮬인지, 아니면 L0(기본 5 필드)만 적용된 시뮬인지" 결과만 보고 판별할 방법이 없습니다. 이는 결과 무결성 P0 이슈입니다.

### 어떻게 고치나

```python
except Exception as e:
    logger.warning("[spawn] persona inject 실패 agent_id=%d: %s", agent_id, e)
```

최소한 warning 로그를 남기고, 가능하면 spawn 결과 메타에 `persona_inject_success_rate`(페르소나 주입 성공 비율) 같은 지표를 함께 반환해 시뮬 메타에서 즉시 확인할 수 있도록 만드는 것이 좋습니다.

### 데드 필드: budget_left_today (사용되지 않는 죽은 필드)

`backend/src/simulation/agents.py:161` 의 `budget_left_today` 는 `__post_init__`(객체 생성 직후 자동 실행되는 함수) 에서 budget 으로부터 복사되지만, 이후 spend(소비) 로직에서 차감되지 않습니다. 즉, 항상 초기값을 유지하므로 사실상 의미 없는 필드입니다(L-4). budget_fit(예산 적합성) 점수 계산에서 이 필드가 쓰인다고 가정하면 결과가 살짝 어긋날 수 있습니다.

---

## 7. 결정 루프 (Decision Loop — 매시간 어느 매장을 갈지 정하는 반복 과정)

### 15 인자 점수 함수

`policy_executor.py` 의 `score_store()` 는 15 개 인자로 매장 점수를 계산합니다. 카테고리 선호도, 거리 패널티(Haversine — 두 좌표 간 구면 거리 공식 — 으로 계산), 예산 적합성, 시간대 적합성, 혼잡 회피, 평점 가중치, 습관 보너스, 소셜 영향, 날씨 영향, 피로 패널티, 기분 조정, OFS 유동인구 점수, 인기도 부스트, 블랙리스트 패널티, 새 매장 보너스가 그 항목입니다. 15 개 인자가 곱해지거나 더해져 최종 점수가 산출되며, 이 점수가 가장 높은 매장이 방문 후보로 선정됩니다.

### 벡터화 batch 함수

`score_stores_batch()` 는 동일한 점수를 numpy 벡터 연산(반복문 대신 행렬을 한 번에 처리)으로 한꺼번에 계산합니다. 에이전트별 상수(예산, 피로, 카테고리 선호도)를 사전 계산해 매장 차원으로 broadcast(작은 배열을 큰 배열에 자동 확장 적용)하므로 성능이 30 ~ 50% 향상됩니다. 다만 OFS(유동인구) 경로는 테스트에서 `ofs_dong_score=empty` 로 검증되지 않은 상태이며, 실 데이터 환경에서 회귀(이전에 잘 되던 게 다시 망가짐)가 발생할 위험이 있습니다.

### prefilter 단계 (사전 필터링)

`_prefilter_candidates()` 는 점수 계산 전에 블랙리스트, full_seats(만석), 카테고리 선호도가 너무 낮은 매장을 미리 걸러냅니다. 매장 수가 30 ~ 40% 줄어들므로 score 계산 비용이 그만큼 줄어드는 효과가 있습니다.

### M-3: 시간 좌표계 불일치

`backend/src/simulation/policy_executor.py:912` 의 `should_visit()` 은 `h = raw_h % 24` 를 사용해 시간대를 24시간 형식으로 정규화하지만, `_rule_decide()` 는 raw_h(원본 시각, 24를 넘을 수 있음)를 그대로 사용합니다. 멀티데이 시뮬레이션처럼 시간이 24 를 넘는 환경에서 두 함수가 서로 다른 값을 보게 되며, 이로 인해 일부 결정이 일관되지 않습니다. 두 함수가 동일한 시간 좌표계를 쓰도록 통일해야 합니다.

---

## 8. peak_hours 수정 검증

커밋 c03273e5 (`feat: legal z-score(z-score — 평균에서 표준편차 몇 배 떨어졌는지) 폐점률 + ABM peak_hours fix + 시뮬 폼 회귀 복구`) 에서 peak_hours(가장 방문이 많은 시간대) 버그가 수정됐습니다. 수정 전에는 `agent._hourly_visits` 라는 존재하지 않는 속성을 참조해 `AttributeError`(없는 속성을 가리켜 발생하는 에러)가 발생했습니다.

수정 후(`backend/src/simulation/runner.py:1317-1320`)는 visits_log(방문 이벤트 전체 기록)에서 직접 시간 카운팅을 하도록 바뀌었습니다.

```python
peak_hours = Counter(
    v["hour"] for v in visits_log
    if isinstance(v.get("hour"), int)
)
```

이 방식은 visits_log 가 단일 원천(single source of truth — 같은 정보의 출처를 한 곳으로 통일)이 되어 의미적으로도 더 명확하며, 현재 단일 일자 시뮬에서는 정상 동작합니다.

### L-1 잔존 이슈: 멀티데이 미리셋

`backend/src/simulation/runner.py` 의 visits_log 는 멀티데이 시뮬레이션에서 일자 간에 리셋되지 않습니다. 따라서 3 일짜리 시뮬을 돌리면 peak_hours 가 3 일치 합산이 되어, 실제 "어느 시간이 피크인지"를 묻는 질문에 일별 변화를 반영하지 못합니다. 일자별로 visits_log 를 리셋하거나 visit 이벤트에 `date` 태그를 추가해 일별 집계가 가능하도록 바꿔야 합니다.

---

## 9. 출력 / 메트릭

### SimulationResult 의 주요 필드

`runner.py:382` 의 `SimulationResult` 는 다음 필드를 담습니다.

- **trajectory**: 시간별 에이전트 위치 리스트
- **density_grid**: 128×96 numpy 배열, 시간별 인구 밀도 히트맵(색으로 강도 표현)
- **visits_log**: 방문 이벤트 전체 로그
- **thoughts**: Tier S 사고 텍스트 (에이전트가 "왜 거기를 갔는지" 자유 서술)
- **tier_s_meta**: Tier S LLM 호출 메타 정보
- **peak_hours**: Counter(시간대별 방문 수 카운트)
- **daily_visits_std**: 일별 방문 표준편차
- **new_store_role_dist**: 신규 업종 분포

프론트엔드(웹 UI)는 density_grid 를 히트맵으로 렌더링(화면에 그리기)하고, visits_log 를 매장별 방문 카운트로 집계합니다.

### M-1: daily_visits_std 하드코딩 0.0

`backend/src/simulation/runner.py:1313-1315` 에서 `daily_visits_std_val = 0.0` 으로 하드코딩돼 있습니다. 단일 일자 시뮬에서는 표준편차가 정의되지 않아 0 이 합리적이지만, 멀티데이 시뮬레이션에서도 0 을 반환하는 것은 명백한 누락입니다. 멀티데이 일별 방문 수를 모아 numpy `std()` 로 계산하도록 바꿔야 합니다.

### H-3: new_store_role_dist 마지막 날만 반영

`backend/src/simulation/runner.py:1307-1309` 의 `new_store_role_dist` 는 에이전트의 `visited_today` 를 집계해 신규 업종 분포를 계산합니다. 그런데 `visited_today` 는 매일 밤 리셋되므로, 멀티데이 시뮬레이션에서는 마지막 날의 방문만 분포에 반영됩니다.

### 왜 중요한가

`new_store_role_dist` 는 "어떤 업종이 시뮬 기간 동안 새로 인기 끌었는가"를 보여주는 핵심 리포트 지표입니다. 마지막 날만 반영되면 운영자는 변동 추세를 잘못 해석하게 되며, 정책 권고가 단기 노이즈에 휘둘립니다. 일자별 누적 카운터 또는 visits_log 직접 집계로 바꿔야 합니다.

---

## 10. 프론트엔드 통합

### API 계약

프론트엔드는 `POST /api/simulate-abm` 으로 시뮬 파라미터(에이전트 수, 날짜 범위, 날씨 시나리오 등)를 보내고, 백엔드는 `run_simulation()` 을 호출해 `SimulationResult` 를 JSON(자바스크립트 객체 표기법 — 데이터 교환 포맷)으로 반환합니다. density_grid 같은 numpy 배열은 list 로 직렬화(객체를 전송 가능한 형태로 변환)되어 전송되며, 프론트는 이를 히트맵 라이브러리(예: deck.gl HeatmapLayer)로 렌더링합니다.

> 큰 중첩 데이터는 JSONB(PostgreSQL 의 JSON 저장 타입. 중첩 데이터 그대로 보관) 컬럼으로 DB 에 저장하면 풍부한 구조를 그대로 유지할 수 있습니다.

### asyncio 패턴 (LangGraph / asyncio — 파이썬 비동기 처리 / LangChain 의 그래프 오케스트레이션)

FastAPI(파이썬 웹 프레임워크) 컨텍스트 안에서 `generate_daily_plans_batch` 같은 async(비동기) 함수를 호출할 때 이벤트 루프(비동기 작업의 실행 스케줄러) 충돌을 피하기 위해 다음 패턴을 사용합니다.

```python
try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(generate_daily_plans_batch(...))
except RuntimeError:
    new_loop = asyncio.new_event_loop()
    new_loop.run_until_complete(...)
```

이 패턴은 FastAPI 가 이미 관리하는 이벤트 루프 위에서 또 다른 `run_until_complete` 를 부르려 할 때 발생하는 RuntimeError 를 잡아 새 루프를 만드는 방식입니다. 동작은 하지만 매번 try/except 가 등장하는 것은 가독성을 떨어뜨리므로, `nest_asyncio.apply()`(중첩된 이벤트 루프를 허용하는 라이브러리)를 한 번만 호출해 전역적으로 중첩 루프를 허용하는 방식을 검토할 수 있습니다.

---

## 11. 테스트 커버리지 (테스트가 코드의 어느 부분을 검증하고 있는지)

### 현재 테스트

ABM 시뮬레이션 관련 테스트는 두 개입니다.

- **`test_score_stores_batch_equivalence.py`**: `score_store` 와 `score_stores_batch` 가 1,000 개의 랜덤 매장에 대해 동일한 결과를 내는지 검증하는 동등성 테스트입니다. 다만 OFS 경로는 `ofs_dong_score=empty` 로 통과하므로 실제 유동인구 데이터 환경에서의 회귀는 잡지 못합니다.
- **`test_runner_day_loop_boost.py`**: `_swap_dong_hour_boost_for_day` 의 living_pop(주거 인구) 엣지케이스(드물게 발생하는 경계 사례)만 다룹니다.

### 미검증 영역

본 리뷰의 핵심 이슈들은 대부분 테스트로 잡히지 않은 영역입니다. `spawn_agents()` 의 PersonaPool inject 실패 경로(H-1), `build_prompt()` 의 time_block 반영 여부(H-4), `_generate_thoughts_openai` 의 모델 설정(H-2), 멀티데이 visits_log 누적(L-1), `budget_left_today` 차감 로직(L-4 데드 필드)은 모두 테스트 공백 상태입니다. 우선순위 1, 2 항목은 수정과 함께 회귀 테스트도 추가하는 것이 권장됩니다.

### 파일명 오해 주의

`backend/simulate_agents.py` 라는 파일명이 ABM 시뮬레이션 테스트로 오해될 수 있지만, 실제로는 LangGraph 5-agent 파이프라인(LangChain 의 그래프 기반 5-에이전트 처리 흐름) 테스트 스크립트입니다. ABM 과는 무관하며, 이름만 비슷합니다. 신규 합류자가 헷갈리지 않도록 파일명을 `test_langgraph_pipeline.py` 같은 형태로 바꾸는 것을 권장합니다.

---

## 12. 코드 품질

### 강점

타입 힌트(변수에 어떤 자료형이 들어가는지 표시)가 전반적으로 잘 붙어 있고, dataclass 와 TypedDict 가 적극 활용돼 IDE(코드 편집기) 자동완성과 런타임 검증이 모두 보장됩니다. parquet 로드는 `lru_cache`(가장 최근 사용한 결과를 메모리에 캐시) 로 1 회만 일어나도록 보장돼 있어 메모리 효율이 좋습니다. LangSmith(LangChain 의 추적·디버깅 도구) 통합 시 `_slim_inputs` 직렬화로 추적 오버헤드(부가 비용)를 줄였고, `score_stores_batch` 의 벡터화와 `_prefilter` 의 조기 차단으로 성능을 크게 끌어올렸습니다. rng seed(난수 생성기 시드 — 같은 값을 주면 같은 난수 시퀀스가 나옴) 가 고정돼 있어 동일 입력에 동일 결과가 보장되는 결정론적 재현성도 확보돼 있습니다.

### 약점

`agents.py` 의 `_gen_name()` (lines 621-625)은 데드 코드(아무도 호출하지 않는 죽은 코드)입니다. `spawn_agents` 가 실제로는 `_gen_unique_names` 를 사용하므로 `_gen_name` 은 호출되지 않지만 그대로 남아 있습니다. bare except 패턴(예외 종류를 지정하지 않고 모든 예외를 삼키는 위험한 패턴 — H-1)으로 대표되는 에러 묵살이 군데군데 보입니다. `world.agent_by_id` (M-2)는 정의만 있고 채워지지 않아 정책 실행기가 매번 O(N) fallback 으로 떨어지며, 1,000 명 × 24 시간 루프에서 누적 비용이 큽니다. `_rule_decide()` 는 300 줄 이상의 단일 함수로 시간대/날씨/카테고리/예산 분기가 한 함수에 몰려 있어 유지보수가 어렵습니다.

---

## 13. 강점 요약

이 ABM 코드베이스의 주요 강점을 정리하면 다음과 같습니다.

**비용 최적화** 측면에서, Tier B 750 명을 순수 규칙 엔진으로 처리해 LLM 호출을 최소화한 설계 결정이 핵심입니다. 이 설계가 없었다면 1,000 명 시뮬은 하루 수십 달러로 비현실적이었을 것입니다. **결정론적 재현성** 측면에서는 rng seed 고정으로 동일 입력에 동일 결과가 보장되어 디버깅(버그 추적)과 회귀 테스트가 가능합니다.

**성능 최적화** 측면에서는 `_uuid_by_idx` 캐시로 spawn 시간을 30 ~ 120 초에서 수 초로 줄였고, `score_stores_batch` 벡터화로 점수 계산을 30 ~ 50% 단축, `_prefilter` 로 매장 수를 30 ~ 40% 사전 차단했습니다. **페르소나 풍부성** 측면에서는 Nemotron 7,187 페르소나의 26 컬럼을 통합해 단순한 통계 분포가 아닌 텍스트 기반 풍부한 페르소나가 가능합니다. **계층 플래닝** 측면에서는 Stanford UIST 2023 의 daily plan → slot lookup 구조를 따라 LLM 호출 횟수를 24 배 절감했습니다.

GameMaster 모듈은 날씨, 임대료, 휴일, 급여일, PM2.5 등 외생 변수(시뮬 외부에서 주어지는 변수)를 매시간 동적으로 조정해 시뮬의 현실감을 높입니다. LangSmith 통합과 slim serialization(가벼운 직렬화)으로 추적성도 확보돼 있어 운영 디버깅이 가능합니다.

---

## 14. 리스크 / 기술 부채 (지금 당장은 동작하지만 나중에 비용이 누적되는 미해결 문제)

### CRITICAL 등급 (즉시 수정 필요)

H-1(`agents.py:859-879`)의 PersonaPool inject bare except 는 페르소나 주입 실패를 무음 묵살하므로 결과 무결성을 결정적으로 훼손할 수 있습니다. H-4(`policy_generator.py:254`)의 build_prompt time_block 미반영은 55 정책 카탈로그가 실제로 11 고유 출력으로 축소되는 설계-구현 괴리(설계 의도와 실제 코드의 차이)입니다. 두 이슈 모두 즉시 수정 대상입니다.

### HIGH 등급

H-2(`brain.py:985`)의 `gpt-5.4-nano` 모델명 하드코딩은 config 에서 지정한 모델이 무시되고 로그에는 다른 모델이 기록되는 false attribution 문제입니다. H-3(`runner.py:1307-1309`)의 `new_store_role_dist` 는 `visited_today` 가 매일 리셋되므로 멀티데이 시뮬에서 마지막 날만 반영됩니다.

### MEDIUM 등급

M-1(`runner.py:1313-1315`)은 `daily_visits_std` 가 0.0 으로 하드코딩돼 있어 멀티데이 표준편차가 항상 0 입니다. M-2(`world.py:66` + `runner.py`)는 `world.agent_by_id` 가 미채움 상태라 정책 실행기가 O(N) fallback 으로 떨어집니다. M-3(`policy_executor.py:912`)은 `should_visit()` 의 `h%24` 와 `_rule_decide` 의 raw_h 가 시간 좌표계 불일치를 일으킵니다.

### LOW 등급

L-1(`runner.py`)은 visits_log 가 멀티데이 미리셋 상태입니다. L-2(`config.py:250-281`)는 `estimate_cost()` 가 thought call 을 포함하지 않아 비용을 과소 추정합니다. L-3(`policy_executor.py:1058-1065`)은 `_adjacent_dongs`(인접 동) 가 리스트 순서 기반이라 실제 지리적 인접성을 반영하지 못합니다. L-4(`agents.py:161`)는 `budget_left_today` 가 차감되지 않는 데드 필드입니다.

---

## 15. 개선 우선순위

### 1순위: H-4 build_prompt time_block 반영

이 수정은 하이브리드 설계의 핵심 가치를 회복하는 작업입니다. 55 고유 정책이 실제로 55 개로 동작해야 ABM 의 시간대 다이내믹스가 살아나며, 메모리 노트의 "LLM 11 회 + 5 배 확장 = 55" 기록과 코드 동작이 일치합니다.

### 2순위: H-1 bare except 제거

운영 디버깅을 가능하게 만드는 가장 작은 비용의 수정입니다. warning 로그 한 줄 추가가 결과 무결성에 대한 신뢰를 회복시킵니다.

### 3순위: H-2 모델명 하드코딩 수정

config 일관성을 회복하고 비용 추적의 정확도를 보장합니다. 한 줄 수정이지만 모델 비교 실험을 가능하게 만드는 토대입니다.

### 4순위: H-3 new_store_role_dist 멀티데이 누적

멀티데이 시뮬레이션의 핵심 리포트 지표를 정확하게 만듭니다. 정책 권고가 마지막 날 노이즈(짧은 기간의 무작위 변동)에 휘둘리지 않도록 합니다.

### 5순위: M-2 world.agent_by_id 채움

정책 실행기의 O(N) fallback 을 제거해 1,000 명 × 24 시간 루프의 누적 비용을 줄입니다. 성능 최적화 측면의 다음 단계입니다.

### 6순위: L-2 estimate_cost thought 포함

비용 목표($0.70/일) 재검증을 위해 thought call 을 비용 추정에 포함해야 합니다. 운영 의사결정의 기반 데이터를 정확하게 만듭니다.

### 7순위: `_rule_decide` 300줄 분리

코드 품질 개선 차원에서 시간대/날씨/카테고리 분기를 별도 함수로 빼야 합니다. 회귀 테스트와 함께 진행하는 것이 안전합니다.

---

## 16. 메모리 노트 vs 실제 코드 델타

메모리 노트(프로젝트 진행 중 누적된 메모)의 기록과 실제 코드 상태를 대조하면 일치 항목과 불일치 항목이 명확히 드러납니다.

### 일치 항목

Tier S:50 / A:200 / B:750 비율은 `config.py` 의 `TierDistribution` 에 동일하게 명시돼 있습니다. peak_hours 수정은 `runner.py:1317-1320` 에서 `Counter` 방식으로 정상 적용된 것이 확인됩니다. `_uuid_by_idx` 최적화(2026-05-09)는 `persona_pool.py:123` 의 dict 캐시 구현으로 확인됩니다. Stanford UIST 2023 daily plan 패턴은 `brain.py` 의 `generate_daily_plans_batch` 에 구현돼 있습니다. score_store 15 인자는 `policy_executor.py` 에서 그대로 확인됩니다.

### 불일치 항목

비용 약 **$0.7/일** 목표는 `estimate_cost()` 의 약 **$1.20 ~ 1.34/일** + thought 미포함 상태와 불일치합니다(L-2). LLM 11 회 base + time_block 5 배 확장 = 55 설계는 카탈로그 55 엔트리는 존재하나 `build_prompt` 가 time_block 을 사용하지 않아 실제로는 11 고유 출력의 5 배 복제 상태로 불일치합니다(H-4).

### 이 델타가 의미하는 것

메모리 노트는 의도와 설계를 기록하는 도구이지만, 코드와 자동으로 동기화되지 않습니다. 따라서 노트와 실제 코드 사이의 정기 점검(이번 리뷰가 그 사례입니다)이 필요하며, 핵심 지표(비용, 정책 다양성)는 시뮬 메타에 자동으로 기록되도록 만들어 노트와 대조 가능하게 만드는 것이 권장됩니다.

---

_작성: 시니어 리뷰어 (Claude) | 2026-05-09_
