import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/site-header";
import report from "@/data/demo-report.json";

const steps = [
  ["Recon", "Index files, routes, and tests. Notes are a lead, not proof."],
  ["Security", "File auth defects that point at a line."],
  ["Performance", "File loops that ignore a batch API."],
  ["Critic", "Reject a theory that cannot cause the symptom."],
  ["Proof", "Keep the patch only if a failing test starts passing."],
];

export default function HomePage() {
  return (
    <div className="min-h-full">
      <SiteHeader caseId={report.id} />
      <main className="mx-auto w-full max-w-6xl px-5 pb-20 sm:px-8">
        <section className="grid items-end gap-10 border-b border-white/10 pb-12 pt-8 lg:grid-cols-[1.4fr_0.8fr] lg:pt-16">
          <div>
            <p className="font-mono text-[11px] tracking-[0.22em] text-[#e2f36b] uppercase">
              Local · private · test-proven
            </p>
            <h1 className="mt-4 max-w-3xl font-heading text-5xl leading-[1.02] tracking-tight text-[#f6f1e6] sm:text-7xl">
              A patch is filed only after the test goes green.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-[#c9c4b6]">
              RepoMind reads a Python repository on your machine. Two specialists file
              what they can point at. A critic throws out the theory that does not
              explain the symptom. The edit runs in a sandbox, and the case closes only
              when a red test turns green.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button
                render={<Link href="/case" />}
                className="h-11 bg-[#e2f36b] px-4 text-[#1c1b16] hover:bg-[#d4e85a]"
              >
                Open case {report.id}
              </Button>
              <Button
                variant="outline"
                render={<a href="#install" />}
                className="h-11 border-white/20 bg-transparent px-4 text-[#f6f1e6] hover:bg-white/5"
              >
                Install the CLI
              </Button>
            </div>
          </div>
          <div className="paper p-6">
            <p className="font-mono text-[11px] tracking-[0.18em] text-[#8a8478] uppercase">
              {report.id} · {report.repo_name}
            </p>
            <p className="mt-3 font-heading text-3xl leading-tight text-[#1c1b16]">
              Fresh tokens were not expired. The clock was.
            </p>
            <dl className="mt-6 space-y-3 text-sm text-[#3c382f]">
              <div className="flex justify-between gap-4 border-b border-[#e6e0d4] pb-3">
                <dt>Critic</dt>
                <dd>Rejected the latency lead</dd>
              </div>
              <div className="flex justify-between gap-4 border-b border-[#e6e0d4] pb-3">
                <dt>Cause</dt>
                <dd className="text-right font-mono text-xs">tokens.py:19</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt>tests/test_tokens.py</dt>
                <dd className="text-[#1e6b45]">failed, then passed</dd>
              </div>
            </dl>
          </div>
        </section>

        <section className="grid gap-px bg-white/10 py-px sm:grid-cols-2 lg:grid-cols-5">
          {steps.map(([title, body], index) => (
            <div key={title} className="bg-[#141613] px-4 py-6">
              <p className="font-mono text-[11px] text-[#e2f36b]">0{index + 1}</p>
              <h2 className="mt-3 font-heading text-2xl text-[#f6f1e6]">{title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-[#c9c4b6]">{body}</p>
            </div>
          ))}
        </section>

        <section id="install" className="grid gap-8 py-16 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <p className="font-mono text-[11px] tracking-[0.22em] text-[#e2f36b] uppercase">
              CLI
            </p>
            <h2 className="mt-3 font-heading text-4xl text-[#f6f1e6]">
              Your repository stays on your machine.
            </h2>
            <p className="mt-4 leading-relaxed text-[#c9c4b6]">
              Install it from GitHub. The command is{" "}
              <code className="text-[#f6f1e6]">repomind</code>. The PyPI name{" "}
              <code className="text-[#f6f1e6]">repomind</code> already belongs to another
              project, so this package is{" "}
              <code className="text-[#f6f1e6]">repomind-local</code>.
            </p>
          </div>
          <div className="paper p-6 font-mono text-[13px] leading-7 text-[#1c1b16]">
            <p>pip install &quot;git+https://github.com/Mdazar123/repomind.git&quot;</p>
            <p>repomind demo</p>
            <p className="mt-4 text-[#8a8478]"># then point it at a Python project</p>
            <p>repomind scan .</p>
          </div>
        </section>

        <section className="grid gap-6 border-t border-white/10 py-12 md:grid-cols-3">
          <div>
            <h3 className="font-heading text-2xl">No source upload</h3>
            <p className="mt-2 text-sm leading-relaxed text-[#c9c4b6]">
              Indexing, the critic, and pytest all run where the code already is. This
              site shows one finished case. It does not receive your repository.
            </p>
          </div>
          <div>
            <h3 className="font-heading text-2xl">Evidence, then a model</h3>
            <p className="mt-2 text-sm leading-relaxed text-[#c9c4b6]">
              Findings come from the AST and the tests. A local Qwen coder model is
              optional and only rewrites the case note. There is no paid API key.
            </p>
          </div>
          <div>
            <h3 className="font-heading text-2xl">Built by Md Azhar</h3>
            <p className="mt-2 text-sm leading-relaxed text-[#c9c4b6]">
              Python, LangGraph, and a Next.js case file.{" "}
              <a className="text-[#e2f36b] underline-offset-4 hover:underline" href="https://github.com/Mdazar123">
                GitHub
              </a>
              {" · "}
              <a
                className="text-[#e2f36b] underline-offset-4 hover:underline"
                href="https://azarmdportfolio.netlify.app/"
              >
                Portfolio
              </a>
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
