"use client";

import { useEffect } from "react";

// Lỗi khi render một trang, thường là backend chưa chạy hoặc trả lỗi
export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="w-full px-6 py-16 text-center lg:px-10">
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="mx-auto mt-2 max-w-[520px] text-[13px] text-muted">
        We couldn&apos;t load recommendations. The recommendation server may be offline or still starting up.
      </p>
      <button
        onClick={() => retry()}
        className="mt-6 rounded-[3px] bg-accent px-4 py-2 text-[13px] text-white hover:bg-accent-hover"
      >
        Try again
      </button>
    </div>
  );
}
