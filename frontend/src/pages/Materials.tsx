import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, BookOpenText, FlaskConical, MoreHorizontal, Pencil, Search, Trash2, Upload } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button, ButtonLink, IconButton } from '../components/ui/Button';
import { Dialog } from '../components/ui/Dialog';
import { EmptyState } from '../components/ui/EmptyState';
import { Alert, ErrorState, PageLoader } from '../components/ui/Feedback';
import { useToast } from '../components/ui/Toast';
import { useApi } from '../hooks/useApi';
import { useLoadSample } from '../hooks/useLoadSample';
import { api, ApiError } from '../services/api';
import type { DeleteImpact, DocumentSummary } from '../types/api';
import { FILE_TYPE_LABEL, formatBytes, formatDate, pluralize } from '../utils/format';

function StatusBadge({ status }: { status: DocumentSummary['status'] }) {
  if (status === 'ready') return <Badge tone="success">Ready</Badge>;
  if (status === 'failed') return <Badge tone="danger">Failed</Badge>;
  return <Badge tone="info">Processing</Badge>;
}

export function RenameDialog({ doc, onClose, onRenamed }: { doc: DocumentSummary | null; onClose: () => void; onRenamed: (d: DocumentSummary) => void }) {
  const [name, setName] = useState(doc?.name ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [lastId, setLastId] = useState(doc?.id);
  if (doc?.id !== lastId) {
    setLastId(doc?.id);
    setName(doc?.name ?? '');
    setError(undefined);
  }
  const save = async () => {
    if (!doc) return;
    setSaving(true);
    try {
      onRenamed(await api.renameDocument(doc.id, name));
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not rename the document.');
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog
      open={!!doc}
      onClose={onClose}
      title="Rename document"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} loading={saving} disabled={!name.trim()}>
            Save
          </Button>
        </>
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <label htmlFor="doc-name" className="label">
          Display name
        </label>
        <input id="doc-name" className="field" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} autoFocus />
        {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      </form>
    </Dialog>
  );
}

export function DeleteDialog({ doc, onClose, onDeleted }: { doc: DocumentSummary | null; onClose: () => void; onDeleted: (id: string) => void }) {
  const impact = useApi<DeleteImpact>(() => api.deleteImpact(doc!.id), [doc?.id], !!doc);
  const [deleting, setDeleting] = useState(false);
  const toast = useToast();
  const remove = async () => {
    if (!doc) return;
    setDeleting(true);
    try {
      await api.deleteDocument(doc.id);
      toast(`Deleted “${doc.name}”.`);
      onDeleted(doc.id);
      onClose();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not delete the document.', 'error');
    } finally {
      setDeleting(false);
    }
  };
  return (
    <Dialog
      open={!!doc}
      onClose={onClose}
      title="Delete this document?"
      description={doc ? `“${doc.name}” will be permanently removed.` : undefined}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" onClick={remove} loading={deleting} disabled={impact.loading} icon={<Trash2 className="h-4 w-4" />}>
            Delete permanently
          </Button>
        </>
      }
    >
      {impact.data ? (
        <div className="rounded-md border border-line bg-subtle px-4 py-3 text-sm">
          <p className="font-medium text-ink">This also deletes:</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-body">
            <li>{pluralize(impact.data.topics, 'topic')} and their learning guides</li>
            <li>{pluralize(impact.data.questions, 'generated question')}</li>
            <li>
              {pluralize(impact.data.quiz_attempts, 'quiz attempt')} that used this material
              {impact.data.quiz_attempts > 0 && ' (and their contribution to your progress)'}
            </li>
          </ul>
        </div>
      ) : impact.error ? (
        <p className="text-sm text-danger">{impact.error.message}</p>
      ) : (
        <p className="text-sm text-muted">Checking related data…</p>
      )}
    </Dialog>
  );
}

export default function Materials() {
  const docs = useApi(() => api.documents(), []);
  const [query, setQuery] = useState('');
  const [renaming, setRenaming] = useState<DocumentSummary | null>(null);
  const [deleting, setDeleting] = useState<DocumentSummary | null>(null);
  const [menu, setMenu] = useState<string | null>(null);
  const sample = useLoadSample();

  const header = (
    <PageHeader
      title="My Materials"
      description="Documents you have uploaded. Original files are discarded after extraction; the extracted text is kept for studying."
      actions={
        <ButtonLink to="/app/upload" icon={<Upload className="h-4 w-4" />}>
          Upload material
        </ButtonLink>
      }
    />
  );
  if (docs.loading) return <PageLoader />;
  if (docs.error) return (<>{header}<ErrorState error={docs.error} onRetry={docs.reload} /></>);
  const all = docs.data ?? [];
  const items = all.filter((d) => d.name.toLowerCase().includes(query.trim().toLowerCase()));

  const updateDoc = (d: DocumentSummary) => docs.setData(all.map((x) => (x.id === d.id ? { ...x, ...d } : x)));
  const removeDoc = (id: string) => docs.setData(all.filter((x) => x.id !== id));

  return (
    <>
      {header}
      {all.length === 0 ? (
        <EmptyState
          illustration
          title="No documents uploaded"
          description="Upload lecture notes in PDF, DOCX or PPTX format to start building learning guides and practice tests."
          action={
            <>
              <ButtonLink to="/app/upload" icon={<Upload className="h-4 w-4" />}>
                Upload material
              </ButtonLink>
              <Button variant="secondary" onClick={sample.load} loading={sample.loading} icon={<FlaskConical className="h-4 w-4" />}>
                Try the demo notes
              </Button>
            </>
          }
        />
      ) : (
        <Card>
          <div className="flex items-center gap-3 border-b border-line px-4 py-3">
            <div className="relative w-full max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
              <input
                className="field pl-9"
                placeholder="Search materials"
                aria-label="Search materials"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <p className="ml-auto hidden text-sm text-muted sm:block">{pluralize(all.length, 'document')}</p>
          </div>
          {items.length === 0 ? (
            <p className="px-5 py-10 text-center text-sm text-muted">No documents match “{query}”.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-line bg-subtle/60 text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">Document</th>
                    <th className="px-3 py-2.5 font-medium">Status</th>
                    <th className="px-3 py-2.5 font-medium">Uploaded</th>
                    <th className="px-3 py-2.5 font-medium">Extracted</th>
                    <th className="px-3 py-2.5 font-medium">Topics</th>
                    <th className="px-3 py-2.5 font-medium">Questions</th>
                    <th className="px-5 py-2.5 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {items.map((d) => (
                    <tr key={d.id} className="align-top">
                      <td className="px-5 py-3">
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 flex h-8 w-10 shrink-0 items-center justify-center rounded bg-subtle text-2xs font-semibold text-muted">
                            {FILE_TYPE_LABEL[d.file_type]}
                          </span>
                          <div className="min-w-0">
                            <Link to={`/app/materials/${d.id}`} className="font-medium text-ink hover:text-brand-700">
                              {d.name}
                            </Link>
                            <p className="text-xs text-muted">
                              {d.original_filename} · {formatBytes(d.size_bytes)}
                              {d.is_sample && ' · demonstration content'}
                            </p>
                            {d.status === 'failed' && d.error_message && (
                              <p className="mt-1 flex max-w-md items-start gap-1.5 text-xs text-danger-ink">
                                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                                {d.error_message}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3"><StatusBadge status={d.status} /></td>
                      <td className="whitespace-nowrap px-3 py-3 text-body">{formatDate(d.created_at)}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-body">
                        {d.status === 'ready' ? (
                          <>
                            {pluralize(d.unit_count, d.unit_label)}
                            <span className="block text-xs text-muted">{pluralize(d.chunk_count, 'chunk')} · {d.word_count.toLocaleString()} words</span>
                          </>
                        ) : '—'}
                      </td>
                      <td className="px-3 py-3 tabular-nums text-body">{d.status === 'ready' ? d.topic_count : '—'}</td>
                      <td className="px-3 py-3 tabular-nums text-body">{d.status === 'ready' ? d.question_count : '—'}</td>
                      <td className="px-5 py-3">
                        <div className="relative flex items-center justify-end gap-1">
                          {d.status === 'ready' && (
                            <ButtonLink to={`/app/learn/${d.id}`} size="sm" variant="subtle" icon={<BookOpenText className="h-3.5 w-3.5" />}>
                              Study
                            </ButtonLink>
                          )}
                          <ButtonLink to={`/app/materials/${d.id}`} size="sm" variant="ghost">
                            Open
                          </ButtonLink>
                          <IconButton label={`More actions for ${d.name}`} onClick={() => setMenu(menu === d.id ? null : d.id)} aria-expanded={menu === d.id}>
                            <MoreHorizontal className="h-4 w-4" />
                          </IconButton>
                          {menu === d.id && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setMenu(null)} aria-hidden />
                              <div role="menu" className="absolute right-0 top-9 z-20 w-40 animate-fade-in rounded-md border border-line bg-surface py-1 shadow-raised">
                                <button role="menuitem" type="button" className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-subtle" onClick={() => { setMenu(null); setRenaming(d); }}>
                                  <Pencil className="h-4 w-4 text-muted" /> Rename
                                </button>
                                <button role="menuitem" type="button" className="flex w-full items-center gap-2 px-3 py-2 text-sm text-danger hover:bg-danger-soft" onClick={() => { setMenu(null); setDeleting(d); }}>
                                  <Trash2 className="h-4 w-4" /> Delete
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      {all.some((d) => d.status === 'failed') && (
        <Alert tone="info" className="mt-4">
          Failed documents cannot be retried in place because the original file is not kept. Delete the entry and upload a corrected
          file (for example, a PDF exported with selectable text).
        </Alert>
      )}
      <RenameDialog doc={renaming} onClose={() => setRenaming(null)} onRenamed={updateDoc} />
      <DeleteDialog doc={deleting} onClose={() => setDeleting(null)} onDeleted={removeDoc} />
    </>
  );
}
