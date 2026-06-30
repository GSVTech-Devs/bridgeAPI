"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getUserApiDocs, type UserDocOperation } from "@/lib/api";
import Markdown from "@/components/Markdown";

const BRIDGE_BASE =
  process.env.NEXT_PUBLIC_BRIDGE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

type Doc = {
  api_id: string;
  api_name: string;
  slug?: string | null;
  base_url: string;
  custom_docs_md?: string | null;
  operations: UserDocOperation[];
};

function methodPill(method: string): string {
  switch (method.toUpperCase()) {
    case "GET": return "bg-emerald-100 text-emerald-700";
    case "POST": return "bg-blue-100 text-blue-700";
    case "PUT": return "bg-amber-100 text-amber-700";
    case "PATCH": return "bg-violet-100 text-violet-700";
    case "DELETE": return "bg-rose-100 text-rose-700";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return (
    <button
      onClick={handleCopy}
      title="Copiar"
      className="ml-2 p-1 rounded hover:bg-surface-container-high transition-colors text-on-surface-variant hover:text-primary shrink-0"
    >
      <span className="material-symbols-outlined text-[16px]">{copied ? "check" : "content_copy"}</span>
    </button>
  );
}

/** Monta a URL do bridge para um endpoint: {BRIDGE}/apis/{slug}/<path>/{seu-token}. */
function bridgeUrl(slug: string | null | undefined, path: string): string | null {
  if (!slug) return null;
  const clean = path.replace(/^\//, "");
  return `${BRIDGE_BASE}/apis/${slug}/${clean}/{seu-token}`;
}

function OperationCard({ op, slug }: { op: UserDocOperation; slug: string | null | undefined }) {
  const url = bridgeUrl(slug, op.path);
  const queryParams = op.parameters.filter((p) => p.in === "query");
  const pathParams = op.parameters.filter((p) => p.in === "path");
  const params = [...pathParams, ...queryParams];

  return (
    <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant/15">
      <div className="flex items-center gap-3 mb-1">
        <span className={`text-center text-[11px] font-black uppercase rounded-md px-2.5 py-1 ${methodPill(op.method)}`}>
          {op.method}
        </span>
        <code className="font-mono text-sm text-on-surface break-all">{op.path}</code>
      </div>
      {op.summary && <p className="text-on-surface font-bold mt-2">{op.summary}</p>}
      {op.description && <Markdown className="mt-1">{op.description}</Markdown>}

      {url && (
        <div className="bg-surface-container-low rounded-lg p-3 mt-4">
          <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">URL Bridge</div>
          <div className="flex items-start gap-1">
            <code className="font-mono text-xs break-all leading-relaxed flex-1 text-on-surface">{url}</code>
            <CopyButton value={url} />
          </div>
          <p className="text-[11px] text-on-surface-variant mt-2">
            Substitua <code className="font-mono">{"{seu-token}"}</code> pela sua chave Bridge.{" "}
            <Link href="/dashboard/keys" className="text-primary hover:underline">ver chaves →</Link>
          </p>
        </div>
      )}

      {params.length > 0 && (
        <div className="mt-4">
          <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-2">Parâmetros</div>
          <div className="rounded-lg border border-outline-variant/10 overflow-hidden">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-outline-variant/10">
                {params.map((p) => (
                  <tr key={`${p.in}-${p.name}`} className="align-top">
                    <td className="px-3 py-2 font-mono text-on-surface whitespace-nowrap">{p.name}</td>
                    <td className="px-3 py-2 text-on-surface-variant whitespace-nowrap">
                      <span className="text-xs">{p.in}{p.type ? ` · ${p.type}` : ""}</span>
                      {p.required && <span className="ml-1 text-[10px] font-bold text-error uppercase">obrigatório</span>}
                    </td>
                    <td className="px-3 py-2 text-on-surface-variant">{p.description ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {op.request_example && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Exemplo de corpo</div>
            <CopyButton value={op.request_example} />
          </div>
          <pre className="bg-surface-container-low rounded-lg p-3 text-xs font-mono text-on-surface overflow-x-auto">{op.request_example}</pre>
        </div>
      )}

      {op.responses.length > 0 && (
        <div className="mt-4">
          <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-2">Respostas</div>
          <div className="space-y-2">
            {op.responses.map((r) => (
              <div key={r.status} className="text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-on-surface">{r.status}</span>
                  <span className="text-on-surface-variant text-xs">{r.description ?? ""}</span>
                </div>
                {r.example && (
                  <pre className="bg-surface-container-low rounded-lg p-3 text-xs font-mono text-on-surface overflow-x-auto mt-1">{r.example}</pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ApiDocsPage() {
  const params = useParams<{ apiId: string }>();
  const apiId = params?.apiId;
  const [doc, setDoc] = useState<Doc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiId) return;
    getUserApiDocs(apiId)
      .then((data) => setDoc(data))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, [apiId]);

  return (
    <div className="max-w-4xl mx-auto">
      <Link
        href="/dashboard/catalog"
        className="inline-flex items-center gap-1 text-on-surface-variant hover:text-primary text-sm mb-6"
      >
        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
        Voltar ao catálogo
      </Link>

      {loading && (
        <div className="flex items-center justify-center py-16 text-on-surface-variant gap-2">
          <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Carregando…
        </div>
      )}
      {error && <div role="alert" className="p-6 text-error bg-error-container rounded-xl">{error}</div>}

      {!loading && !error && doc && (
        <>
          <div className="mb-10">
            <h1 className="text-4xl font-headline font-extrabold text-on-surface tracking-tight mb-2">{doc.api_name}</h1>
            <p className="text-on-surface-variant text-lg">Documentação e endpoints disponíveis.</p>
          </div>

          {doc.custom_docs_md && (
            <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant/15 mb-6">
              <Markdown>{doc.custom_docs_md}</Markdown>
            </div>
          )}

          {doc.operations.length === 0 && !doc.custom_docs_md ? (
            <div className="text-center py-16 text-on-surface-variant">
              <span className="material-symbols-outlined text-5xl mb-4 block opacity-40">menu_book</span>
              <p>Documentação ainda não disponível para esta API.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {doc.operations.map((op, i) => (
                <OperationCard key={`${op.method}-${op.path}-${i}`} op={op} slug={doc.slug} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
