"use client";

import { useState } from "react";
import { steamHeader } from "@/lib/api";

// Ảnh header.jpg từ CDN của Steam; game đã bị gỡ thì không có ảnh -> hiện tên game trên nền tối
export function GameImage({ appId, title, className = "" }: { appId: number; title: string; className?: string }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div className={`grid place-items-center bg-surface-2 p-4 text-center text-sm text-muted ${className}`}>
        {title}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- ảnh CDN ngoài, không cần tối ưu qua server Next
    <img
      src={steamHeader(appId)}
      alt={title}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`object-cover ${className}`}
    />
  );
}
