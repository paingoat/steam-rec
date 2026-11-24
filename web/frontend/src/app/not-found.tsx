import Link from "next/link";

export default function NotFound() {
  return (
    <div className="w-full px-6 py-16 text-center lg:px-10">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-[13px] text-muted">The page you are looking for doesn&apos;t exist.</p>
      <Link href="/" className="mt-6 inline-block rounded-[3px] bg-accent px-4 py-2 text-[13px] text-white">
        Go home
      </Link>
    </div>
  );
}
