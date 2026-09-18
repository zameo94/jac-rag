"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useTenant } from "@/features/tenants/TenantProvider";
import { api } from "@/lib/api";
import type { Document } from "@/lib/types";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentsPanel() {
  const t = useTranslations("documents");
  const common = useTranslations("common");
  const { activeTenant } = useTenant();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const tenantId = activeTenant?.id ?? null;

  const load = useCallback(async () => {
    if (!tenantId) return;
    try {
      setDocuments(await api.documents.list(tenantId));
      setError(null);
    } catch (err) {
      setError(err);
    }
  }, [tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!tenantId) return;
    const hasPending = documents.some(
      (doc) => doc.status === "pending" || doc.status === "processing",
    );
    if (!hasPending) return;
    const timer = setInterval(() => {
      void load();
    }, 2500);
    return () => clearInterval(timer);
  }, [documents, tenantId, load]);

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !tenantId) return;
    setUploading(true);
    setError(null);
    try {
      const created = await api.documents.upload(tenantId, file);
      setDocuments((current) => [created, ...current]);
    } catch (err) {
      setError(err);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete(documentId: number) {
    if (!tenantId) return;
    if (!window.confirm(common("confirmDelete"))) return;
    try {
      await api.documents.remove(tenantId, documentId);
      setDocuments((current) => current.filter((doc) => doc.id !== documentId));
    } catch (err) {
      setError(err);
    }
  }

  if (!tenantId) return null;

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <div className="flex flex-col items-end gap-1">
          <label className="cursor-pointer rounded bg-slate-900 px-4 py-2 text-sm text-white">
            {uploading ? t("uploading") : t("upload")}
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              disabled={uploading}
              onChange={handleUpload}
            />
          </label>
          <span className="text-xs text-slate-500">{t("supported")}</span>
        </div>
      </div>

      <ErrorMessage error={error} />

      {documents.length === 0 ? (
        <p className="text-sm text-slate-500">{t("empty")}</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="py-2">{t("filename")}</th>
              <th className="py-2">{t("size")}</th>
              <th className="py-2">{common("status")}</th>
              <th className="py-2">{t("chunks")}</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id} className="border-b border-slate-100">
                <td className="py-2">{doc.filename}</td>
                <td className="py-2 text-slate-500">{formatSize(doc.size)}</td>
                <td className="py-2">
                  <span className="rounded bg-slate-100 px-2 py-0.5">
                    {t(`status.${doc.status}`)}
                  </span>
                  {doc.error && (
                    <span className="ml-2 text-xs text-red-600">
                      {doc.error === "no_text_layer" ? t("errorNoTextLayer") : doc.error}
                    </span>
                  )}
                </td>
                <td className="py-2 text-slate-500">{doc.chunk_count ?? "-"}</td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    onClick={() => handleDelete(doc.id)}
                    className="text-sm text-red-600 hover:underline"
                  >
                    {common("delete")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
