export function DiffView({ diff }: { diff: string }) {
  const lines = diff.replace(/\n$/, "").split("\n");
  return (
    <pre className="overflow-x-auto font-mono text-[12.5px] leading-6">
      {lines.map((line, index) => {
        let className = "px-4 text-[#6f6a60]";
        if (line.startsWith("@@")) className = "px-4 text-[#7a6840]";
        else if (line.startsWith("+") && !line.startsWith("+++"))
          className = "bg-[#e4f0e4] px-4 text-[#1b5c3a]";
        else if (line.startsWith("-") && !line.startsWith("---"))
          className = "bg-[#f6e4de] px-4 text-[#8d3324]";
        return (
          <div key={`${index}-${line}`} className={className}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}
