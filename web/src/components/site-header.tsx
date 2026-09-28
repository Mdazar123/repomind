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
      <nav className="flex items-center gap-4 text-[13px] text-[#c9c4b6] sm:gap-5">
        <Link href="/case" className="hover:text-white">
          {caseId ? `Case ${caseId}` : "Case"}
        </Link>
        <Link href="/#install" className="hover:text-white">
          Install
        </Link>
        <a
          href="https://pypi.org/project/repomind-local/"
          className="hover:text-white"
          target="_blank"
          rel="noreferrer"
        >
          PyPI
        </a>
        <a
          href="https://github.com/Mdazar123/repomind"
          className="hidden hover:text-white sm:inline"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
        <a
          href="https://github.com/Mdazar123/repomind/issues/new"
          className="hover:text-white"
          target="_blank"
          rel="noreferrer"
        >
          Feedback
        </a>
      </nav>
    </header>
  );
}
