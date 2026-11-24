import { redirect } from "next/navigation";
import { getUserId } from "@/lib/session";

// Tạm thời: trang Discover (tính năng [1]) sẽ làm ở bước sau.
export default async function DiscoverPage() {
  const userId = await getUserId();
  if (userId === null) redirect("/login");

  return (
    <div className="w-full px-6 py-12">
      <h1 className="text-2xl font-semibold">Recommended for You</h1>
      <p className="mt-2 text-sm text-muted">Coming soon.</p>
    </div>
  );
}
