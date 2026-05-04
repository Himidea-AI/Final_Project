/**
 * personaSampleDialogs — ABM 대기화면 (PersonaPreviewStream) 용 샘플 페르소나 대화 pool.
 *
 * 진짜 시뮬 partial 결과 streaming 은 backend 인프라 미존재 → 카테고리별 사전 정의
 * 대화 rotate 로 "AI 가 페르소나 추론 중" 분위기 연출. 카드 하단에 "샘플" 명시 필수.
 */

export type PersonaTier = 'S' | 'A' | 'B';

export interface PersonaDialog {
  persona: string; // "30대 직장인 박씨"
  tier: PersonaTier;
  text: string; // 1~2 문장 한국어 - 해당 spot 카테고리 방문 의향/이유
}

export interface CategoryPool {
  category: string;
  dialogs: PersonaDialog[];
}

const CAFE_DIALOGS: PersonaDialog[] = [
  {
    persona: '20대 학생 김씨',
    tier: 'A',
    text: '시험기간. 콘센트 + wifi 빠르면 무조건 옴. 가격은 5천원 안쪽 선호.',
  },
  {
    persona: '30대 직장인 박씨',
    tier: 'S',
    text: '점심 후 동료랑 잠깐. 회의 분위기 가능한 좌석 있으면 주 3회 방문 가능.',
  },
  {
    persona: '40대 주부 이씨',
    tier: 'B',
    text: '아이 픽업 전 1시간. 편안한 의자 + 디저트 종류 다양하면 매주 옴.',
  },
  {
    persona: '20대 프리랜서 최씨',
    tier: 'S',
    text: '하루 종일 작업할 자리. 좌석 회전율 압박 느끼면 안 옴.',
  },
  {
    persona: '50대 자영업자 정씨',
    tier: 'B',
    text: '거래처 미팅 장소. 조용하고 주차 가까우면 단골 가능.',
  },
  {
    persona: '20대 직장인 윤씨',
    tier: 'A',
    text: '출근 전 7시 30분 테이크아웃. 모바일 주문 빠르면 매일 옴.',
  },
  {
    persona: '30대 부부 한씨',
    tier: 'B',
    text: '주말 오후 산책 후. 외부 좌석 있으면 강아지 동반 방문.',
  },
  {
    persona: '60대 노년 강씨',
    tier: 'B',
    text: '오전 9시쯤 친구들과. 메뉴 사진 크고 대형 글씨면 편함.',
  },
];

const RESTAURANT_DIALOGS: PersonaDialog[] = [
  {
    persona: '30대 직장인 박씨',
    tier: 'S',
    text: '점심 한정 1만원 이하 정식 있으면 주 4회 방문. 대기 5분 이상은 패스.',
  },
  {
    persona: '20대 커플 김씨',
    tier: 'A',
    text: '데이트 코스. 인스타 인증샷 가능한 인테리어 + 객단가 2~3만원선 선호.',
  },
  {
    persona: '40대 가족 이씨',
    tier: 'B',
    text: '주말 점심 4인. 아이 메뉴 + 룸 좌석 있으면 한 달 한 번은 옴.',
  },
  {
    persona: '30대 회사원 정씨',
    tier: 'A',
    text: '회식 가능 인원 10~15명. 단체 코스 + 주류 라인업 풍부하면 분기 1회 잡음.',
  },
  {
    persona: '50대 부부 윤씨',
    tier: 'B',
    text: '저녁 외식. 시끄럽지 않고 음식 짜지 않으면 단골 가능.',
  },
  {
    persona: '20대 학생 최씨',
    tier: 'B',
    text: '친구 생일. 5인 메뉴 + 케이크 반입 OK 면 예약함.',
  },
  {
    persona: '30대 직장인 한씨',
    tier: 'A',
    text: '혼밥 자리. 카운터석 있고 1인 메뉴 명확하면 주 2회 옴.',
  },
  {
    persona: '40대 사업자 강씨',
    tier: 'S',
    text: '거래처 접대. 위치 알기 쉽고 발렛 가능 + 코스요리 5만원 이상이면 선호.',
  },
];

const PUB_DIALOGS: PersonaDialog[] = [
  {
    persona: '30대 직장인 박씨',
    tier: 'S',
    text: '회식 2차. 안주 푸짐 + 1만원대 술 라인업이면 매주 옴.',
  },
  {
    persona: '20대 친구모임 김씨',
    tier: 'A',
    text: '6명 이상 단체석 필수. 새벽까지 영업하면 주 1회 단골.',
  },
  {
    persona: '40대 사장님 이씨',
    tier: 'B',
    text: '직원 회식. 룸 + 주류 다양 + 결제 법인카드 OK 면 분기 1회.',
  },
  {
    persona: '20대 데이트 정씨',
    tier: 'A',
    text: '와인 위주 분위기 좋은 곳. 시끄럽지 않고 안주 1.5~2만원이면 매월 옴.',
  },
  {
    persona: '30대 동호회 윤씨',
    tier: 'B',
    text: '월례 모임 8명. 예약 가능 + 1인 2만원선 안주 코스 있으면 정착.',
  },
  {
    persona: '20대 직장인 최씨',
    tier: 'S',
    text: '퇴근 후 혼술. 카운터석 + 5천원 이하 단품 안주 있으면 주 2~3회 옴.',
  },
  {
    persona: '40대 친구모임 한씨',
    tier: 'B',
    text: '동창 모임. 조용하고 안주 정갈하면 분기 1회 잡힘.',
  },
  {
    persona: '30대 커플 강씨',
    tier: 'A',
    text: '데이트 마무리 1잔. 좌석 좁아도 분위기만 좋으면 옴.',
  },
];

const CONVENIENCE_DIALOGS: PersonaDialog[] = [
  {
    persona: '20대 1인가구 김씨',
    tier: 'A',
    text: '도시락 + 음료 매일 1회. 신상 도시락 자주 들어오면 충성도 높음.',
  },
  {
    persona: '30대 직장인 박씨',
    tier: 'S',
    text: '출근길 커피 + 아침. 7시 정각 오픈 + 결제 빠르면 주 5일 옴.',
  },
  {
    persona: '40대 주부 이씨',
    tier: 'B',
    text: '저녁 반찬 + 우유. 신선식품 코너 있으면 주 3회 옴.',
  },
  {
    persona: '20대 학생 정씨',
    tier: 'B',
    text: '시험기간 야식. 24시간 + 라면/치킨 핫박스 있으면 매일.',
  },
  {
    persona: '60대 노년 윤씨',
    tier: 'B',
    text: '담배 + 막걸리. 친절하고 거스름돈 정확하면 단골.',
  },
  {
    persona: '30대 1인가구 최씨',
    tier: 'A',
    text: '택배 보관 + 야식. 보관함 여유 있고 영업시간 길면 매주 4회.',
  },
  {
    persona: '20대 커플 한씨',
    tier: 'B',
    text: '데이트 후 음료. 신상 디저트 자주 입고되면 주 1~2회.',
  },
  {
    persona: '40대 직장인 강씨',
    tier: 'A',
    text: '점심 샐러드 + 단백질음료. 헬스 타깃 상품 다양하면 주 4회.',
  },
];

const DEFAULT_DIALOGS: PersonaDialog[] = [
  {
    persona: '30대 직장인 박씨',
    tier: 'S',
    text: '동선상 들리기 좋은 위치. 가격 합리적이면 주 1~2회 가능.',
  },
  {
    persona: '20대 학생 김씨',
    tier: 'A',
    text: '학교/회사 이동길. 빠르고 저렴하면 자주 옴.',
  },
  {
    persona: '40대 가족 이씨',
    tier: 'B',
    text: '주말 외출. 주차 + 가족친화 분위기면 월 1~2회 옴.',
  },
  {
    persona: '20대 1인가구 정씨',
    tier: 'A',
    text: '집 근처. 영업시간 길면 활용도 높음.',
  },
  {
    persona: '50대 자영업자 윤씨',
    tier: 'B',
    text: '거래처 미팅용. 주차 + 깔끔한 인테리어 필요.',
  },
  {
    persona: '30대 부부 최씨',
    tier: 'B',
    text: '주말 데이트 코스. 분위기 좋으면 매월 옴.',
  },
  {
    persona: '20대 직장인 한씨',
    tier: 'A',
    text: '퇴근길 동선. 결제 빠르면 단골 됨.',
  },
  {
    persona: '60대 노년 강씨',
    tier: 'B',
    text: '도보 거리. 친절하고 익숙한 메뉴면 자주 옴.',
  },
];

/**
 * 카테고리별 pool. 키는 backend businessType 값과 한국어 표기 둘 다 매칭 가능하게.
 */
export const SAMPLE_DIALOG_POOLS: CategoryPool[] = [
  { category: 'cafe', dialogs: CAFE_DIALOGS },
  { category: '카페', dialogs: CAFE_DIALOGS },
  { category: 'restaurant', dialogs: RESTAURANT_DIALOGS },
  { category: '음식점', dialogs: RESTAURANT_DIALOGS },
  { category: 'pub', dialogs: PUB_DIALOGS },
  { category: '주점', dialogs: PUB_DIALOGS },
  { category: 'bar', dialogs: PUB_DIALOGS },
  { category: 'convenience', dialogs: CONVENIENCE_DIALOGS },
  { category: '편의점', dialogs: CONVENIENCE_DIALOGS },
  { category: 'default', dialogs: DEFAULT_DIALOGS },
];

/**
 * 카테고리 키워드 → dialog list. 매칭 안 되면 default pool 반환.
 */
export function pickDialogPool(businessType?: string | null): PersonaDialog[] {
  if (!businessType) return DEFAULT_DIALOGS;
  const lower = businessType.toLowerCase();
  for (const pool of SAMPLE_DIALOG_POOLS) {
    if (lower.includes(pool.category.toLowerCase())) return pool.dialogs;
  }
  return DEFAULT_DIALOGS;
}
