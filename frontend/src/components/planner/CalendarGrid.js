import { addDays, endOfMonth, endOfWeek, format, isSameMonth, isToday, startOfMonth, startOfWeek } from "date-fns";

export const dragData = (e, payload) => e.dataTransfer.setData("application/json", JSON.stringify(payload));

export function PlanChip({ item, color, onClick }) {
  return (
    <button draggable onDragStart={(e) => dragData(e, { kind: "plan", id: item.id })} onClick={onClick}
      data-testid={`plan-chip-${item.id}`}
      className="w-full text-left text-[11px] leading-tight px-1.5 py-1 rounded border-l-[3px] bg-[#FFFDF9] hover:bg-[#F4EFE6] shadow-sm truncate cursor-grab active:cursor-grabbing"
      style={{ borderLeftColor: color || "#A8A29E" }}>
      {item.episode?.episode_number ? `#${item.episode.episode_number} ` : ""}{item.episode?.title || item.title}
    </button>
  );
}

export function CalendarGrid({ month, items, seriesById, onDrop, onOpen }) {
  const start = startOfWeek(startOfMonth(month));
  const end = endOfWeek(endOfMonth(month));
  const days = [];
  for (let d = start; d <= end; d = addDays(d, 1)) days.push(d);
  const byDate = {};
  items.forEach((i) => { if (i.date) (byDate[i.date] = byDate[i.date] || []).push(i); });

  return (
    <div className="card-warm overflow-hidden" data-testid="planner-calendar">
      <div className="grid grid-cols-7 bg-[#F4EFE6]/70 border-b border-[#E7E0D6]">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => <div key={d} className="eyebrow !text-stone-500 px-2 py-2">{d}</div>)}
      </div>
      <div className="grid grid-cols-7">
        {days.map((d) => {
          const key = format(d, "yyyy-MM-dd");
          return (
            <div key={key} onDragOver={(e) => e.preventDefault()} onDrop={(e) => onDrop(e, key)} data-testid={`calendar-day-${key}`}
              className={`min-h-[108px] border-b border-r border-[#EFE8DC] p-1.5 space-y-1 transition-colors ${isSameMonth(d, month) ? "" : "bg-[#FAF7F2] opacity-60"}`}>
              <div className={`text-xs f-mono w-6 h-6 grid place-items-center rounded-full ${isToday(d) ? "bg-[#B45309] text-white" : "text-stone-500"}`}>{format(d, "d")}</div>
              {(byDate[key] || []).map((i) => <PlanChip key={i.id} item={i} color={seriesById[i.series_id]?.color} onClick={() => onOpen(i)} />)}
            </div>
          );
        })}
      </div>
    </div>
  );
}
