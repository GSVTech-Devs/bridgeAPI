"use client";

import { isValidElement, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/** Extrai o texto cru de um nó (o conteúdo do <code> dentro do <pre>). */
function extractText(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (isValidElement(node)) {
    return extractText((node.props as { children?: ReactNode }).children);
  }
  return "";
}

/** Bloco de código com destaque próprio e botão de copiar. */
function CodeBlock({ children }: { children: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const text = extractText(children).replace(/\n$/, "");

  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="relative my-3 group">
      <button
        type="button"
        onClick={copy}
        title="Copiar"
        aria-label="Copiar código"
        className="absolute top-2 right-2 z-10 p-1.5 rounded-md bg-surface-container-high/80 text-on-surface-variant hover:text-primary hover:bg-surface-container-highest transition-colors"
      >
        <span className="material-symbols-outlined text-[16px]">
          {copied ? "check" : "content_copy"}
        </span>
      </button>
      <pre className="bg-surface-container-highest border border-outline-variant/25 rounded-lg p-4 pr-12 text-xs font-mono text-on-surface overflow-x-auto [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-on-surface">
        {children}
      </pre>
    </div>
  );
}

/**
 * Renderiza Markdown (descrições de operações vindas do openapi.json e a doc
 * personalizada do admin) com os tokens visuais do app. Não habilita HTML cru:
 * o conteúdo vem do spec de uma API externa ou do admin, então mantemos só o
 * subconjunto seguro de Markdown/GFM.
 */
const components: Components = {
  h1: ({ children }) => (
    <h1 className="text-lg font-bold text-on-surface mt-4 mb-2">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-bold text-on-surface mt-4 mb-2">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-bold uppercase tracking-wider text-on-surface-variant mt-4 mb-1">
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-sm font-bold text-on-surface mt-3 mb-1">{children}</h4>
  ),
  p: ({ children }) => (
    <p className="text-sm text-on-surface-variant leading-relaxed my-2">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc pl-5 my-2 space-y-1 text-sm text-on-surface-variant">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-5 my-2 space-y-1 text-sm text-on-surface-variant">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-on-surface">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-primary hover:underline"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="font-mono text-xs bg-surface-container-high text-on-surface rounded px-1 py-0.5">
      {children}
    </code>
  ),
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-outline-variant/40 pl-3 my-3 text-sm text-on-surface-variant italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-outline-variant/20" />,
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-outline-variant/10">
      <table className="w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-surface-container-low text-on-surface-variant">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left font-bold text-xs uppercase tracking-wider">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 align-top text-on-surface-variant border-t border-outline-variant/10">
      {children}
    </td>
  ),
};

export default function Markdown({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
