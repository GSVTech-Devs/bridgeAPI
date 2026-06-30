import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renderiza Markdown (descrições de operações vindas do openapi.json) com os
 * tokens visuais do app. Não habilita HTML cru: o conteúdo vem do spec de uma
 * API externa, então mantemos só o subconjunto seguro de Markdown/GFM.
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
  pre: ({ children }) => (
    <pre className="bg-surface-container-low rounded-lg p-3 my-3 text-xs font-mono text-on-surface overflow-x-auto [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
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
