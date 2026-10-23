import { FlaskConical, Upload } from 'lucide-react';
import { Button, ButtonLink } from './ui/Button';
import { EmptyState } from './ui/EmptyState';
import { useLoadSample } from '../hooks/useLoadSample';

/** Shown on study pages when the workspace has no successfully processed documents. */
export function NoDocuments({ purpose }: { purpose: string }) {
  const sample = useLoadSample();
  return (
    <EmptyState
      illustration
      title="No processed documents yet"
      description={`Upload study material first — ${purpose} are built from the documents you upload.`}
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
  );
}
