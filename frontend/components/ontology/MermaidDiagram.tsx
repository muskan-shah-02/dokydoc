"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Copy, Check, Download, AlertCircle } from "lucide-react";

interface MermaidDiagramProps {
  syntax: string;
  title?: string;
  className?: string;
}

export function MermaidDiagram({ syntax, title, className = "" }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [rendered, setRendered] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const idRef = useRef(`mermaid-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    if (!syntax || !containerRef.current) return;

    setRendered(false);
    setError("");

    let cancelled = false;

    import("mermaid").then((m) => {
      if (cancelled) return;
      const mermaid = m.default;

      mermaid.initialize({
        startOnLoad: false,
        theme: "base",
        themeVariables: {
          primaryColor: "#e0e7ff",
          primaryTextColor: "#1e1b4b",
          primaryBorderColor: "#6366f1",
          lineColor: "#6366f1",
          secondaryColor: "#f0fdf4",
          tertiaryColor: "#fef3c7",
          background: "#ffffff",
          mainBkg: "#ffffff",
          nodeBorder: "#6366f1",
          clusterBkg: "#f8fafc",
          titleColor: "#1e1b4b",
          edgeLabelBackground: "#ffffff",
          fontSize: "13px",
        },
        flowchart: { curve: "basis", htmlLabels: true },
        sequence: { actorMargin: 60, messageMargin: 20 },
        er: { layoutDirection: "TB", minEntityWidth: 100 },
      });

      mermaid
        .render(idRef.current, syntax)
        .then(({ svg }) => {
          if (cancelled || !containerRef.current) return;
          containerRef.current.innerHTML = svg;
          // Make SVG responsive
          const svgEl = containerRef.current.querySelector("svg");
          if (svgEl) {
            svgEl.style.width = "100%";
            svgEl.style.height = "auto";
            svgEl.style.maxHeight = "500px";
          }
          setRendered(true);
        })
        .catch((err) => {
          if (cancelled) return;
          setError(String(err?.message ?? "Failed to render diagram"));
          setRendered(true);
        });
    });

    return () => {
      cancelled = true;
    };
  }, [syntax]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(syntax);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadSVG = () => {
    const svgEl = containerRef.current?.querySelector("svg");
    if (!svgEl) return;
    const blob = new Blob([svgEl.outerHTML], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title ?? "diagram"}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        {title && <p className="text-xs font-medium text-gray-500">{title}</p>}
        <div className="ml-auto flex gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-md border bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
          >
            {copied ? <Check className="h-3 w-3 text-green-600" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copied" : "Copy Mermaid"}
          </button>
          <button
            onClick={handleDownloadSVG}
            disabled={!rendered || !!error}
            className="flex items-center gap-1 rounded-md border bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          >
            <Download className="h-3 w-3" />
            SVG
          </button>
        </div>
      </div>

      {/* Render area */}
      <div className="relative rounded-lg border bg-white p-4 overflow-auto min-h-[200px]">
        {!rendered && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Rendering diagram...</span>
          </div>
        )}
        {error && (
          <div className="flex flex-col gap-2 p-4">
            <div className="flex items-center gap-2 text-red-600 text-sm">
              <AlertCircle className="h-4 w-4" />
              <span>Diagram render error: {error}</span>
            </div>
            <pre className="mt-2 rounded bg-gray-50 p-3 text-xs text-gray-700 overflow-auto whitespace-pre-wrap">
              {syntax}
            </pre>
          </div>
        )}
        <div ref={containerRef} className={rendered && !error ? "block" : "hidden"} />
      </div>
    </div>
  );
}
