import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ChevronLeft, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { DocumentOverview } from '../components/DocumentOverview';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ErrorState, PageLoader } from '../components/ui/Feedback';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { DeleteDialog, RenameDialog } from './Materials';
import { FILE_TYPE_LABEL, formatBytes, formatDate } from '../utils/format';
import type { DocumentSummary } from '../types/api';

export default function DocumentDetail() {
  const { documentId = '' } = useParams();
  const doc = useApi(() => api.document(documentId), [documentId]);
  const [renaming, setRenaming] = useState<DocumentSummary | null>(null);
  const [deleting, setDeleting] = useState<DocumentSummary | null>(null);
  const navigate = useNavigate();

  if (doc.loading) return <PageLoader label="Loading document…" />;
  if (doc.error) {
    return (
      <>
        <BackLink />
        <ErrorState error={doc.error} onRetry={doc.error.status === 404 ? undefined : doc.reload} />
      </>
    );
  }
  const d = doc.data!;
  return (
    <>
      <BackLink />
      <PageHeader
        title={d.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge>{FILE_TYPE_LABEL[d.file_type]}</Badge>
            {d.is_sample && <Badge tone="brand">Demonstration content</Badge>}
            <span>
              {d.original_filename} · {formatBytes(d.size_bytes)} · uploaded {formatDate(d.created_at, true)}
            </span>
          </span>
        }
        actions={
          <>
            <Button variant="secondary" size="sm" icon={<Pencil className="h-4 w-4" />} onClick={() => setRenaming(d)}>
              Rename
            </Button>
            <Button variant="secondary" size="sm" icon={<Trash2 className="h-4 w-4" />} onClick={() => setDeleting(d)}>
              Delete
            </Button>
          </>
        }
      />
      <DocumentOverview doc={d} />
      <RenameDialog doc={renaming} onClose={() => setRenaming(null)} onRenamed={(r) => doc.setData({ ...d, ...r })} />
      <DeleteDialog doc={deleting} onClose={() => setDeleting(null)} onDeleted={() => navigate('/app/materials')} />
    </>
  );
}

function BackLink() {
  return (
    <Link to="/app/materials" className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink">
      <ChevronLeft className="h-4 w-4" /> My Materials
    </Link>
  );
}
