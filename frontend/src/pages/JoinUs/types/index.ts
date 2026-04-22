export interface Plan {
  id: 'starter' | 'growth' | 'enterprise';
  name: string;
  target: string;
  price: string;
  priceNote: string;
  badge: string;
  badgeLabel?: string;
  cta: string;
  features: { text: string; included: boolean }[];
  highlighted: boolean;
}

export interface SignupFormData {
  companyName: string;
  bizNumber: string;
  contactName: string;
  position: string;
  email: string;
  phone: string;
  storeCount: string;
  password: string;
  passwordConfirm: string;
  agreeTerms: boolean;
}

export interface EnterpriseFormData {
  companyName: string;
  contactName: string;
  email: string;
  phone: string;
  storeCount: string;
  message: string;
}
