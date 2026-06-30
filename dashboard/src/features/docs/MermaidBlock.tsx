import { useEffect, useRef, useState } from "react";

// Singleton mermaid loader — only initializes once per page load.
let _mermaidPromise: Promise<typeof import("mermaid").default> | null = null;

function loadMermaid() {
  if (!_mermaidPromise) {
    _mermaidPromise = import("mermaid").then((mod) => {
      const mermaid = mod.default;
      const dark = document.documentElement.classList.contains("dark");
      mermaid.initialize({
        startOnLoad: false,
        theme: dark ? "dark" : "default",
        fontFamily: "Inter, IBM Plex Sans, system-ui, sans-serif",
        fontSize: 13,
      });
      return mermaid;
    });
  }
  return _mermaidPromise;
}

let _counter = 0;

export function MermaidBlock({ code }: { code: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = `mermaid-${++_counter}`;
    let cancelled = false;

    loadMermaid().then(async (mermaid) => {
      if (cancelled || !containerRef.current) return;
      try {
        const { svg } = await mermaid.render(id, code.trim());
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    });

    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    return (
      <pre className="my-4 overflow-x-auto rounded border border-neg bg-neg-bg px-3 py-2 text-xs text-neg">
        {error}
      </pre>
    );
  }

  return (
    <div
      ref={containerRef}
      className="my-6 flex justify-center overflow-x-auto [&_svg]:max-w-full"
    />
  );
}
