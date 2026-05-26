import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-black/5 dark:border-white/10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-8 text-sm text-foreground/60 sm:flex-row sm:px-6">
        <p>&copy; {new Date().getFullYear()} Lens. All rights reserved.</p>
        <div className="flex items-center gap-4">
          <Link href="/gallery" className="transition-colors hover:text-foreground">
            Gallery
          </Link>
          <Link href="/about" className="transition-colors hover:text-foreground">
            About
          </Link>
        </div>
      </div>
    </footer>
  );
}
