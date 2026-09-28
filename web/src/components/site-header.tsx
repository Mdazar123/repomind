import Link from "next/link";

export function SiteHeader({ caseId }: { caseId?: string }) {
  return (
    <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
      <Link href="/" className="flex items-center gap-3">
        <span className="grid size-8 place-items-center border border-[#e2f36b]/70 text-[11px] font-medium tracking-[0.14em] text-[#e2f36b]">
          RM
        </span>
        <span className="text-[15px] tracking-tight">RepoMind</span>
      </Link>
      <nav className="flex items-center gap-5 text-[13px] text-[#c9c4b6]">
        {caseId ? (
          <Link href="/case" className="hidden font-mono text-[#e2f36b] sm:inline">
            {caseId}
          </Link>
        ) : (
          <Link href="/case" className="hover:text-white">
            Paystream case
          </Link>
        )}
        <a
          href="https://github.com/Mdazar123"
          className="hover:text-white"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </nav>
    </header>
  );
}
