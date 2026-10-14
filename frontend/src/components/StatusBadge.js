import { STATUS_LABELS } from "@/lib/api";

const STYLES = {
  draft: "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]",
  outline_approved: "bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]",
  script_complete: "bg-[#F3E8FF] text-[#6B21A8] border-[#E9D5FF]",
  published: "bg-[#DCFCE7] text-[#15803D] border-[#86EFAC]",
};

export function StatusBadge({ status, testId }) {
  return (
    <span
      data-testid={testId || "status-badge"}
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full border text-xs font-semibold whitespace-nowrap ${STYLES[status] || STYLES.draft}`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}
