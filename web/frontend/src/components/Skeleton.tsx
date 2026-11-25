// Khung xám nhấp nháy khi trang đang chờ dữ liệu
export function CardsSkeleton({ rows = 4, tall = false }: { rows?: number; tall?: boolean }) {
  return (
    <div className="w-full animate-pulse px-6 py-10 lg:px-10">
      <div className="h-7 w-72 rounded bg-surface" />
      <div className="mt-3 h-4 w-96 max-w-full rounded bg-surface" />
      <div className="mt-8 flex flex-col gap-6">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className={`rounded-[4px] bg-bg-deep ${tall ? "h-[230px]" : "h-[130px]"}`} />
        ))}
      </div>
    </div>
  );
}
