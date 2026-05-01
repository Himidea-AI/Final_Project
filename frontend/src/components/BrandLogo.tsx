import { useState } from 'react';
import { Building2 } from 'lucide-react';

const BRAND_LOGOS: Record<string, string> = {
  BBQ: '/logos/bbq.png',
  교촌: '/logos/kyochon.png',
  스타벅스: '/logos/starbucks.png',
  이디야: '/logos/ediya.png',
  맘스터치: '/logos/momstouch.png',
};

const getLogoUrl = (name?: string): string | null => {
  if (!name) return null;
  for (const [key, url] of Object.entries(BRAND_LOGOS)) {
    if (name.includes(key)) return url;
  }
  return null;
};

const getInitial = (name: string): string =>
  name
    .replace(/[^가-힣a-zA-Z0-9]/g, '')
    .charAt(0)
    .toUpperCase();

type BrandLogoTone = 'accent' | 'muted';

type BrandLogoProps = {
  name?: string;
  className?: string;
  isUser?: boolean;
  tone?: BrandLogoTone;
  title?: string;
};

export function BrandLogo({
  name,
  className = 'w-8 h-8 text-xs rounded-full',
  isUser = false,
  tone = 'accent',
  title,
}: BrandLogoProps) {
  const [imgError, setImgError] = useState(false);
  const logoUrl = !isUser ? getLogoUrl(name) : null;

  if (logoUrl && !imgError) {
    return (
      <img
        src={logoUrl}
        alt={`${name ?? ''} logo`}
        title={title}
        className={`object-contain bg-white border border-[#3a3633] shrink-0 ${className}`}
        onError={() => setImgError(true)}
      />
    );
  }

  if (name) {
    const initial = getInitial(name);

    const toneClass = isUser
      ? tone === 'accent'
        ? 'bg-[#818cf8]/20 border-[#818cf8]/50 text-[#818cf8]'
        : 'bg-[#2c2825] border-[#3a3633] text-[#9ca3af]'
      : 'bg-[#818cf8]/20 border-[#818cf8]/50 text-[#818cf8]';

    return (
      <div
        title={title}
        className={`flex items-center justify-center shrink-0 font-bold border ${toneClass} ${className}`}
      >
        {initial}
      </div>
    );
  }

  return (
    <div
      title={title}
      className={`flex items-center justify-center shrink-0 bg-[#2c2825] border border-[#3a3633] text-[#9ca3af] ${className}`}
    >
      <Building2 className="w-1/2 h-1/2" />
    </div>
  );
}
