/**
 * 슈퍼어드민 brand picker 관련 타입.
 * 백엔드 응답 (`backend/src/api/admin_brands.py`) 와 1:1.
 */

export interface AdminBrand {
  brand_name: string;
  corp_name: string | null;
  biz_number: string | null;
  /** canonical 업종 key — '한식', '커피' 등. App.tsx 의 BUSINESS_TYPE_BACKEND_KEY 와 매칭. */
  business_type: string;
  /** CS100001 ~ CS100010 */
  cs_code: string;
  industry_medium: string | null;
  franchise_count: number | null;
  avg_sales: number | null;
  source: 'ftc' | 'biz_brand_mapping';
}

export interface SupportedIndustry {
  /** canonical key — '한식', '커피' 등 */
  key: string;
  /** UI 표시명 — '한식음식점', '커피-음료' */
  label: string;
  /** CS100001 ~ CS100010 */
  cs_code: string;
  kakao_category?: string;
}

export interface AdminBrandsResponse {
  total: number;
  page: number;
  size: number;
  supported_industries: SupportedIndustry[];
  items: AdminBrand[];
}

export interface AdminIndustriesResponse {
  industries: SupportedIndustry[];
}

export interface AdminBrandsQuery {
  q?: string;
  /** canonical key */
  industry?: string;
  page?: number;
  size?: number;
}
