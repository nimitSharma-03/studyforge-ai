import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpenText, ClipboardCheck, RotateCcw, ShieldCheck, Upload, Zap } from 'lucide-react';
import type { Recommendation } from '../types/api';
import { api, ApiError } from '../services/api';
import { useToast } from './ui/Toast';
import { Button } from './ui/Button';

const ICONS = {
  revise: BookOpenText,
  practice: ClipboardCheck,
  start: Zap,
  retry: RotateCcw,
  maintain: ShieldCheck,
  upload: Upload,
};

/** Recommendations come from the backend progress summary; each one links to a concrete action. */
export function RecommendationList({ items }: { items: Recommendation[] }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  if (!items.length) return <p className="text-sm text-muted">Nothing to suggest right now.</p>;

  const act = async (r: Recommendation, key: string) => {
    try {
      setBusy(key);
      if (r.kind === 'upload') navigate('/app/upload');
      else if (r.kind === 'revise' || r.kind === 'maintain') navigate(`/app/learn/${r.document_id}/${r.topic_id}`);
      else if (r.kind === 'start') navigate(`/app/practice?document=${r.document_id}`);
      else if (r.kind === 'retry' && r.attempt_id) {
        const quiz = await api.retryQuiz(r.attempt_id);
        navigate(`/app/practice/${quiz.id}`);
      } else if (r.kind === 'practice' && r.document_id && r.topic_id) {
        const quiz = await api.createQuiz({ mode: 'topic', document_ids: [r.document_id], topic_ids: [r.topic_id] });
        navigate(`/app/practice/${quiz.id}`);
      }
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not start that activity.', 'error');
    } finally {
      setBusy(null);
    }
  };

  const labels = { revise: 'Open guide', maintain: 'Open guide', start: 'Choose test', retry: 'Retry now', practice: 'Practise', upload: 'Upload' };

  return (
    <ul className="space-y-4">
      {items.map((r, i) => {
        const Icon = ICONS[r.kind];
        const key = `${r.kind}-${r.topic_id ?? r.attempt_id ?? i}`;
        return (
          <li key={key} className="flex gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-600">
              <Icon className="h-4 w-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink">{r.title}</p>
              <p className="text-xs text-muted">{r.detail}</p>
              <Button size="sm" variant="ghost" className="-ml-3 mt-1 text-brand-700" loading={busy === key} onClick={() => act(r, key)}>
                {labels[r.kind]}
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
