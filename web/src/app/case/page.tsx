import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { CaseDesk } from "@/components/case-desk";
import report from "@/data/demo-report.json";

export default function CasePage() {
  return (
    <div className="min-h-full pb-16">
      <SiteHeader caseId={report.id} />
      <div className="mx-auto w-full max-w-5xl px-3 sm:px-8">
        <div className="mb-6 flex items-center justify-between">
          <p className="font-mono text-[11px] tracking-[0.18em] text-[#c9c4b6] uppercase">
            Played from a real local run
          </p>
          <Link href="/" className="text-sm text-[#c9c4b6] hover:text-white">
            Back
          </Link>
        </div>
        <CaseDesk />
      </div>
    </div>
  );
}
