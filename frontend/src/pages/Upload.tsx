import { useRef, useState, type DragEvent } from 'react';
import { CheckCircle2, FileText, FileType2, FlaskConical, Presentation, RotateCcw, UploadCloud } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { DocumentOverview } from '../components/DocumentOverview';
import { Card, CardBody } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Alert, IndeterminateBar, ProgressBar } from '../components/ui/Feedback';
import { useServer } from '../hooks/useServer';
import { useLoadSample } from '../hooks/useLoadSample';
import { api, ApiError } from '../services/api';
import type { DocumentDetail } from '../types/api';
import { validateFile } from '../utils/validation';
import { cn, formatBytes } from '../utils/format';

type Phase = { kind: 'idle' } | { kind: 'uploading'; progress: number } | { kind: 'processing' } | { kind: 'done'; doc: DocumentDetail } | { kind: 'error'; message: string; retryable: boolean };

export default function Upload() {
  const { maxUploadMb } = useServer();
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' });
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const sample = useLoadSample();

  const start = async (f: File) => {
    setFile(f);
    const problem = validateFile(f, maxUploadMb);
    if (problem) {
      setPhase({ kind: 'error', message: problem, retryable: false });
      return;
    }
    setPhase({ kind: 'uploading', progress: 0 });
    try {
      const doc = await api.upload(f, (fraction) => {
        // Once all bytes are sent the server is extracting and analysing; show that honestly.
        setPhase(fraction >= 1 ? { kind: 'processing' } : { kind: 'uploading', progress: fraction });
      });
      setPhase({ kind: 'done', doc });
    } catch (err) {
      const e = err instanceof ApiError ? err : null;
      setPhase({
        kind: 'error',
        message: e?.message ?? 'The upload failed.',
        retryable: !e || e.isNetwork || e.status >= 500 || e.status === 429,
      });
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void start(f);
  };

  const reset = () => {
    setPhase({ kind: 'idle' });
    setFile(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const busy = phase.kind === 'uploading' || phase.kind === 'processing';

  return (
    <>
      <PageHeader
        title="Upload material"
        description="StudyForge reads the text, headings and page or slide numbers of your document, then builds topics, guides and questions."
      />
      {phase.kind !== 'done' && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                if (!busy) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={busy ? (e) => e.preventDefault() : onDrop}
              className={cn(
                'flex flex-col items-center justify-center rounded-xl border-2 border-dashed bg-surface px-6 py-14 text-center transition-colors',
                dragging ? 'border-brand-500 bg-brand-50' : 'border-line-strong',
              )}
            >
              {busy ? (
                <div className="w-full max-w-sm" aria-live="polite">
                  <p className="font-medium text-ink">{file?.name}</p>
                  <p className="text-sm text-muted">{file && formatBytes(file.size)}</p>
                  {phase.kind === 'uploading' ? (
                    <>
                      <ProgressBar value={phase.progress} className="mt-5" label="Upload progress" />
                      <p className="mt-2 text-sm text-muted">Uploading… {Math.round(phase.progress * 100)}%</p>
                    </>
                  ) : (
                    <>
                      <IndeterminateBar className="mt-5" />
                      <p className="mt-2 text-sm text-muted">
                        Extracting text and analysing topics on the server. This usually takes a few seconds; large documents can take
                        up to two minutes.
                      </p>
                    </>
                  )}
                </div>
              ) : (
                <>
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                    <UploadCloud className="h-6 w-6" aria-hidden />
                  </span>
                  <p className="mt-4 font-medium text-ink">Drag and drop a file here</p>
                  <p className="mt-1 text-sm text-muted">PDF, DOCX or PPTX · up to {maxUploadMb} MB</p>
                  <Button className="mt-5" onClick={() => inputRef.current?.click()}>
                    Choose file
                  </Button>
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".pdf,.docx,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    className="sr-only"
                    data-testid="file-input"
                    aria-label="Choose a file to upload"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) void start(f);
                    }}
                  />
                </>
              )}
            </div>
            {phase.kind === 'error' && (
              <Alert
                tone="danger"
                title="Upload failed"
                className="mt-4"
                action={
                  <div className="flex gap-2">
                    {phase.retryable && file && (
                      <Button size="sm" variant="secondary" onClick={() => void start(file)} icon={<RotateCcw className="h-3.5 w-3.5" />}>
                        Retry
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={reset}>
                      Choose another
                    </Button>
                  </div>
                }
              >
                {phase.message}
              </Alert>
            )}
          </div>
          <div className="space-y-4">
            <Card>
              <CardBody className="space-y-4">
                <p className="text-sm font-semibold text-ink">Supported formats</p>
                {[
                  { icon: FileText, name: 'PDF', text: 'Must contain selectable text. Scanned PDFs need OCR first.' },
                  { icon: FileType2, name: 'Word (.docx)', text: 'Heading styles become topics. Legacy .doc is not supported.' },
                  { icon: Presentation, name: 'PowerPoint (.pptx)', text: 'Slide titles, bullets and speaker notes are read.' },
                ].map(({ icon: Icon, name, text }) => (
                  <div key={name} className="flex gap-3">
                    <Icon className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-hidden />
                    <div>
                      <p className="text-sm font-medium text-ink">{name}</p>
                      <p className="text-xs text-muted">{text}</p>
                    </div>
                  </div>
                ))}
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <p className="text-sm font-semibold text-ink">No notes at hand?</p>
                <p className="mt-1 text-xs text-muted">
                  Load a short, synthetic “Foundations of NLP” document created for demonstrations.
                </p>
                <Button variant="secondary" size="sm" className="mt-3" onClick={sample.load} loading={sample.loading} disabled={busy} icon={<FlaskConical className="h-4 w-4" />}>
                  Use demo notes
                </Button>
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {phase.kind === 'done' && (
        <>
          <div className="mb-6 flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 sm:flex-row sm:items-center">
            <CheckCircle2 className={cn('h-6 w-6 shrink-0', phase.doc.status === 'ready' ? 'text-success' : 'text-danger')} aria-hidden />
            <div className="flex-1">
              <p className="font-medium text-ink">
                {phase.doc.duplicate
                  ? 'This file was already uploaded — showing the existing analysis.'
                  : phase.doc.status === 'ready'
                    ? `“${phase.doc.name}” is ready to study.`
                    : `“${phase.doc.name}” could not be processed.`}
              </p>
              <p className="text-sm text-muted">{phase.doc.original_filename}</p>
            </div>
            <Button variant="secondary" onClick={reset}>
              Upload another
            </Button>
          </div>
          <DocumentOverview doc={phase.doc} />
        </>
      )}
    </>
  );
}
