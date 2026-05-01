interface SectionLabelProps {
  label: string;
  subtitle?: string;
}

export function SectionLabel({ label, subtitle }: SectionLabelProps) {
  return (
    <div className="mb-6">
      <h2 className="text-xl font-semibold text-stone-100 uppercase tracking-wide">{label}</h2>
      {subtitle && <p className="mt-1 text-sm text-stone-400">{subtitle}</p>}
    </div>
  );
}
