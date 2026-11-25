"use client";

import { useState } from "react";
import { steamHeader } from "@/lib/api";

const capsule = (appId: number) => `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/capsule_616x353.jpg`;

// Ảnh từ CDN của Steam: capsule (to) -> header.jpg -> tên game trên nền tối nếu game đã bị gỡ
export function GameImage({
  appId,
  title,
  variant = "header",
  className = "",
}: {
  appId: number;
  title: string;
  variant?: "header" | "capsule";
  className?: string;
}) {
  const sources = variant === "capsule" ? [capsule(appId), steamHeader(appId)] : [steamHeader(appId)];
  const [i, setI] = useState(0);

  if (i >= sources.length) {
    return (
      <div className={`grid place-items-center bg-surface-2 p-4 text-center text-sm text-muted ${className}`}>
        {title}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- ảnh CDN ngoài, không cần tối ưu qua server Next
    <img
      src={sources[i]}
      alt={title}
      loading="lazy"
      onError={() => setI(i + 1)}
      className={`object-cover ${className}`}
    />
  );
}
