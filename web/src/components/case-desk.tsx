"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DiffView } from "@/components/diff-view";
import report from "@/data/demo-report.json";

type Memo = {
  agent: string;
  title: string;
  body: string;
  tone: string;
};

const LABELS: Record<string, string> = {
  recon: "Recon",
  security: "Security",
  performance: "Performance",
  hypothesis: "Hypothesis",
  critic: "Critic",
  fix: "Fix",
  proof: "Proof",
};

const memos = (report.log as Memo[]).filter((memo) => memo.agent !== "publish");

export function CaseDesk() {
  const [shown, setShown] = useState(1);
  const done = shown >= memos.length;

  useEffect(() => {
    if (done) return;
    const timer = window.setTimeout(() => setShown((count) => count + 1), 480);
    return () => window.clearTimeout(timer);
  }, [done, shown]);

  const visible = memos.slice(0, shown);
  const proof = report.proof;
  const root = report.root_cause;

  return (
    <article className="paper mx-auto w-full max-w-5xl rounded-[2px] px-5 py-8 sm:px-10 sm:py-12">
      <div className="flex flex-wrap items-start justify-between gap-6 border-b border-[#ddd6c8] pb-6">
        <div>
          <p className="font-mono text-[11px] tracking-[0.22em] text-[#8a8478] uppercase">
            Case file · local sandbox · source untouched
          </p>
          <h1 className="mt-3 font-heading text-4xl tracking-tight text-[#1c1b16] sm:text-5xl">
            {report.id}
          </h1>
          <p className="mt-2 text-[#5e594e]">
            {report.repo_name} · tokens rejected on a fresh session
          </p>
        </div>
        <div className={`stamp px-3 py-2 font-mono text-[11px] ${done ? "stamp-green" : ""}`}>
          {done ? "Proven" : "Open"}
        </div>
      </div>

      <blockquote className="mt-8 border-l-2 border-[#1c1b16] pl-4 text-lg leading-relaxed text-[#1c1b16]">
        {report.problem}
      </blockquote>

      <div className="mt-6 flex flex-wrap gap-2">
        <Badge variant="outline" className="border-[#ddd6c8] bg-transparent text-[#5e594e]">
          {report.index.file_count} files
        </Badge>
        <Badge variant="outline" className="border-[#ddd6c8] bg-transparent text-[#5e594e]">
          {report.index.routes.length} routes
        </Badge>
        <Badge variant="outline" className="border-[#ddd6c8] bg-transparent text-[#5e594e]">
          {report.index.tests.length} tests
        </Badge>
        <Button
          variant="outline"
          size="sm"
          className="ml-auto border-[#1c1b16] bg-transparent text-[#1c1b16] hover:bg-[#1c1b16] hover:text-[#f3efe4]"
          onClick={() => setShown(done ? 1 : memos.length)}
        >
          {done ? "Replay" : "Skip to the finding"}
        </Button>
      </div>

      <ol className="mt-8 space-y-3">
        {visible.map((memo, index) => (
          <li
            key={`${memo.agent}-${memo.title}-${index}`}
            className={`border px-4 py-4 ${
              memo.tone === "challenge"
                ? "border-[#e4c7c0] bg-[#fbf6f3]"
                : memo.tone === "proven"
                  ? "border-[#c9dfd1] bg-[#f4f8f5]"
                  : "border-[#e6e0d4] bg-white/40"
            }`}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-[11px] tracking-[0.16em] text-[#8a8478] uppercase">
                {LABELS[memo.agent] ?? memo.agent}
              </p>
              <p className="text-sm font-medium text-[#1c1b16]">{memo.title}</p>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-[#3c382f]">
              {memo.body}
            </p>
          </li>
        ))}
      </ol>

      {done && root && (
        <section className="mt-10 grid gap-8 border-t border-[#ddd6c8] pt-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="font-mono text-[11px] tracking-[0.18em] text-[#8a8478] uppercase">
              Root cause
            </p>
            <h2 className="mt-2 font-heading text-3xl leading-tight text-[#1c1b16]">
              {root.title}
            </h2>
            <p className="mt-3 font-mono text-sm text-[#1e6b45]">
              {root.file}:{root.line}
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-[#3c382f]">{root.detail}</p>
            <pre className="mt-4 overflow-x-auto border border-[#e6e0d4] bg-[#1c1b16] p-4 font-mono text-[12px] leading-6 text-[#f3efe4]">
              {root.snippet}
            </pre>
            {report.also_found[0] && (
              <p className="mt-4 text-sm leading-relaxed text-[#5e594e]">
                Set aside: {report.also_found[0].title}. The critic kept it off the cause
                because a slow ledger read cannot mint a 401.
              </p>
            )}
          </div>
          <div>
            <p className="font-mono text-[11px] tracking-[0.18em] text-[#8a8478] uppercase">
              Sandbox edit
            </p>
            <p className="mt-2 text-[15px] text-[#3c382f]">{report.patch.explanation}</p>
            <div className="mt-4 border border-[#e6e0d4] bg-white/70">
              <DiffView diff={report.patch.diff} />
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="border border-[#e4c7c0] bg-[#fbf6f3] p-4">
                <p className="font-mono text-[11px] tracking-[0.16em] text-[#a33b2b] uppercase">
                  Before
                </p>
                <p className="mt-2 text-2xl text-[#1c1b16]">Failed</p>
                <p className="mt-2 font-mono text-xs leading-5 text-[#5e594e]">
                  {proof.baseline.output
                    .split("\n")
                    .filter((line) => line.includes("assert") || line.trim().startsWith("E "))
                    .slice(0, 3)
                    .join("\n") || proof.tests[0]}
                </p>
              </div>
              <div className="border border-[#c9dfd1] bg-[#f4f8f5] p-4">
                <p className="font-mono text-[11px] tracking-[0.16em] text-[#1e6b45] uppercase">
                  After
                </p>
                <p className="mt-2 text-2xl text-[#1c1b16]">Passed</p>
                <p className="mt-1 font-mono text-xs text-[#5e594e]">
                  {proof.patched.output.trim().split("\n").slice(-2).join(" · ")}
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {done && (
        <p className="mt-8 border-t border-[#ddd6c8] pt-6 text-[15px] leading-relaxed text-[#3c382f]">
          {report.summary}
        </p>
      )}
    </article>
  );
}
