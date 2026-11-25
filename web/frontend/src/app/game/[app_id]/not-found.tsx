import Link from "next/link";

export default function GameNotFound() {
  return (
    <div className="w-full px-6 py-16 text-center lg:px-10">
      <h1 className="text-2xl font-semibold">Game not found</h1>
      <p className="mt-2 text-[13px] text-muted">This app_id is not in the recommendation catalog.</p>
      <Link href="/browse" className="mt-6 inline-block rounded-[3px] bg-accent px-4 py-2 text-[13px] text-white">
        Browse by Tags
      </Link>
    </div>
  );
}
