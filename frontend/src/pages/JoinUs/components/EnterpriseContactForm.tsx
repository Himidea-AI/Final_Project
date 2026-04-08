import { useState, useCallback } from "react";
import { motion } from "framer-motion";

interface FormData {
  companyName: string;
  contactName: string;
  email: string;
  phone: string;
  storeCount: string;
  message: string;
}

const INITIAL: FormData = {
  companyName: "",
  contactName: "",
  email: "",
  phone: "",
  storeCount: "",
  message: "",
};

function formatPhone(v: string) {
  const n = v.replace(/\D/g, "").slice(0, 11);
  if (n.length <= 3) return n;
  if (n.length <= 7) return `${n.slice(0, 3)}-${n.slice(3)}`;
  return `${n.slice(0, 3)}-${n.slice(3, 7)}-${n.slice(7)}`;
}

const fieldClass =
  "w-full px-4 py-3 rounded-xl bg-[#1c1c1c] border border-[#333333] text-[#fafafa] text-sm placeholder-[#555] outline-none transition-colors duration-200 focus:border-[#818cf8]";
const labelClass = "block text-xs text-[#a1a1aa] font-medium mb-1.5";

interface Props {
  onSuccess: () => void;
}

export default function EnterpriseContactForm({ onSuccess }: Props) {
  const [form, setForm] = useState(INITIAL);
  const set = useCallback(
    (key: keyof FormData, val: string) => setForm((p) => ({ ...p, [key]: val })),
    []
  );

  const allValid =
    form.companyName && form.contactName && form.email && form.phone && form.storeCount;

  const handleSubmit = () => {
    if (!allValid) return;
    console.log("Enterprise inquiry:", form);
    onSuccess();
  };

  const fields = [
    { key: "companyName" as const, label: "기업명", placeholder: "프랜차이즈 본부명" },
    { key: "contactName" as const, label: "담당자명", placeholder: "홍길동" },
    { key: "email" as const, label: "이메일", placeholder: "name@company.com" },
    { key: "phone" as const, label: "연락처", placeholder: "010-0000-0000" },
    { key: "storeCount" as const, label: "현재 가맹점 수", placeholder: "예: 45" },
  ];

  return (
    <div className="flex flex-col gap-4 w-full">
      {fields.map((f, i) => (
        <motion.div
          key={f.key}
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05, duration: 0.4 }}
        >
          <label className={labelClass}>{f.label}</label>
          <input
            type="text"
            value={form[f.key]}
            onChange={(e) =>
              set(f.key, f.key === "phone" ? formatPhone(e.target.value) : e.target.value)
            }
            placeholder={f.placeholder}
            className={fieldClass}
          />
        </motion.div>
      ))}

      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25, duration: 0.4 }}
      >
        <label className={labelClass}>문의 내용</label>
        <textarea
          value={form.message}
          onChange={(e) => set("message", e.target.value)}
          placeholder="도입 관련 문의사항을 작성해주세요"
          rows={4}
          className={`${fieldClass} resize-none`}
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
        className="mt-1 p-3 rounded-lg bg-[#818cf8]/5 border border-[#818cf8]/20"
      >
        <p className="text-xs text-[#a5b4fc]">
          영업팀이 1영업일 내 연락드립니다.
        </p>
      </motion.div>

      <motion.button
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
        onClick={handleSubmit}
        disabled={!allValid}
        className={`w-full py-3.5 rounded-xl font-bold text-sm tracking-wider mt-2 transition-all duration-300 ${
          allValid
            ? "bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:scale-[1.02] active:scale-[0.98]"
            : "bg-[#262626] text-[#555] cursor-not-allowed"
        }`}
      >
        문의 제출
      </motion.button>
    </div>
  );
}
