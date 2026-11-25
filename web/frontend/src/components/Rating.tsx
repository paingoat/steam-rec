// "Very Positive · 92% positive" + thanh xanh/đỏ như thiết kế
export function Rating({ rating, positive, className = "" }: { rating: string; positive?: number; className?: string }) {
  if (!rating) return null;
  return (
    <div className={`text-[12px] ${className}`}>
      <span className="text-link">{rating}</span>
      {positive !== undefined && (
        <>
          <span className="text-muted"> · {positive}% positive</span>
          <div className="mt-1.5 flex h-[3px] overflow-hidden rounded-full bg-negative">
            <div className="bg-link" style={{ width: `${positive}%` }} />
          </div>
        </>
      )}
    </div>
  );
}
