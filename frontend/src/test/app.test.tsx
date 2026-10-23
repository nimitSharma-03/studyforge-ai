import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import App from '../App';
import { ToastProvider } from '../components/ui/Toast';
import { ServerProvider } from '../hooks/useServer';
import { api, ApiError } from '../services/api';
import Landing from '../pages/Landing';
import Dashboard from '../pages/Dashboard';
import Materials from '../pages/Materials';
import Upload from '../pages/Upload';
import Learn from '../pages/Learn';
import { ExamRunner } from '../pages/QuizTake';
import QuizResults from '../pages/QuizResults';
import { validateFile } from '../utils/validation';
import { doc, quiz, renderAt, result, topicDetail, topics } from './utils';

const emptyProgress = {
  documents_ready: 0, documents_total: 0, attempts_submitted: 0, attempts_in_progress: 0, questions_answered: 0,
  questions_correct: 0, average_accuracy: null, min_answers_for_accuracy: 5, min_answers_per_topic: 5, topics: [],
  weak_topics: [], insufficient_topics: [], recommendations: [], recent_activity: [], accuracy_trend: [],
};

describe('Landing page', () => {
  it('presents the product and primary actions', () => {
    renderAt(<Landing />);
    expect(screen.getByRole('heading', { level: 1, name: /from notes to knowledge/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /start studying/i })).toHaveAttribute('href', '/app');
    expect(screen.getByRole('link', { name: /explore features/i })).toHaveAttribute('href', '#features');
    expect(screen.getByText(/hosted version/i)).toBeInTheDocument();
  });
});

describe('Navigation', () => {
  it('moves between app sections from the sidebar', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ status: 'ok', version: '1', environment: 'test', database: 'ok', database_backend: 'sqlite', llm_enabled: false, max_upload_mb: 25 });
    vi.spyOn(api, 'documents').mockResolvedValue([]);
    vi.spyOn(api, 'progress').mockResolvedValue(emptyProgress);
    render(
      <MemoryRouter initialEntries={['/app']}>
        <ServerProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </ServerProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: /welcome to studyforge/i })).toBeInTheDocument();
    const nav = screen.getAllByRole('navigation', { name: 'Main' })[0];
    await userEvent.click(within(nav).getByRole('link', { name: /my materials/i }));
    expect(await screen.findByRole('heading', { name: 'My Materials' })).toBeInTheDocument();
    expect(screen.getByText(/no documents uploaded/i)).toBeInTheDocument();
  });
});

describe('Dashboard', () => {
  it('shows an empty state with upload and demo actions for new users', async () => {
    vi.spyOn(api, 'documents').mockResolvedValue([]);
    vi.spyOn(api, 'progress').mockResolvedValue(emptyProgress);
    renderAt(<Dashboard />);
    expect(await screen.findByText(/no study material yet/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try the demo notes/i })).toBeInTheDocument();
  });

  it('reports real metrics and hides accuracy without enough data', async () => {
    vi.spyOn(api, 'documents').mockResolvedValue([doc()]);
    vi.spyOn(api, 'progress').mockResolvedValue({ ...emptyProgress, documents_ready: 1, documents_total: 1, attempts_submitted: 1, questions_answered: 3, questions_correct: 2 });
    renderAt(<Dashboard />);
    expect(await screen.findByText('Documents processed')).toBeInTheDocument();
    expect(screen.getByText(/shown after 5\+ answered questions/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Foundations of NLP' })).toBeInTheDocument();
  });

  it('explains when the backend is unreachable', async () => {
    vi.spyOn(api, 'documents').mockRejectedValue(new ApiError(0, 'network_error', 'Cannot reach the StudyForge server.'));
    vi.spyOn(api, 'progress').mockResolvedValue(emptyProgress);
    renderAt(<Dashboard />);
    expect(await screen.findByRole('heading', { name: /server unavailable/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});

describe('Materials', () => {
  it('lists documents with status, counts and processing errors', async () => {
    vi.spyOn(api, 'documents').mockResolvedValue([
      doc(),
      doc({ id: 'd2', name: 'Scanned handout', status: 'failed', error_code: 'scanned_pdf', error_message: 'This PDF appears to be scanned images.' }),
    ]);
    renderAt(<Materials />);
    expect(await screen.findByRole('link', { name: 'Foundations of NLP' })).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText(/appears to be scanned images/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /study/i })).toHaveAttribute('href', '/app/learn/d1');
  });

  it('confirms deletion and shows the related data that will be removed', async () => {
    vi.spyOn(api, 'documents').mockResolvedValue([doc()]);
    vi.spyOn(api, 'deleteImpact').mockResolvedValue({ document_id: 'd1', topics: 2, questions: 40, quiz_attempts: 3 });
    const del = vi.spyOn(api, 'deleteDocument').mockResolvedValue(undefined);
    renderAt(<Materials />);
    await userEvent.click(await screen.findByRole('button', { name: /more actions/i }));
    await userEvent.click(screen.getByRole('menuitem', { name: /delete/i }));
    expect(await screen.findByText(/3 quiz attempts that used this material/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /delete permanently/i }));
    await waitFor(() => expect(del).toHaveBeenCalledWith('d1'));
    expect(await screen.findByText(/no documents uploaded/i)).toBeInTheDocument();
  });
});

describe('Upload', () => {
  it('validates file type and size on the client', () => {
    expect(validateFile(new File(['x'], 'notes.txt'), 25)).toMatch(/not supported/);
    expect(validateFile(new File([], 'empty.pdf'), 25)).toMatch(/empty/);
    const big = new File(['x'], 'big.pdf');
    Object.defineProperty(big, 'size', { value: 26 * 1024 * 1024 });
    expect(validateFile(big, 25)).toMatch(/maximum size is 25 MB/);
    expect(validateFile(new File(['%PDF'], 'ok.pdf'), 25)).toBeNull();
  });

  it('rejects unsupported files without uploading', async () => {
    const upload = vi.spyOn(api, 'upload');
    renderAt(<Upload />);
    // Bypass the input's accept filter, as a user picking "All files" in the dialog would.
    fireEvent.change(screen.getByTestId('file-input'), { target: { files: [new File(['hello'], 'notes.txt', { type: 'text/plain' })] } });
    expect(await screen.findByText(/notes.txt” is not supported/i)).toBeInTheDocument();
    expect(upload).not.toHaveBeenCalled();
  });

  it('shows server errors with a way to choose another file', async () => {
    vi.spyOn(api, 'upload').mockRejectedValue(new ApiError(413, 'file_too_large', 'Files must be 25 MB or smaller.'));
    renderAt(<Upload />);
    await userEvent.upload(screen.getByTestId('file-input'), new File(['%PDF-1.4'], 'notes.pdf', { type: 'application/pdf' }));
    expect(await screen.findByText('Files must be 25 MB or smaller.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /choose another/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^retry$/i })).not.toBeInTheDocument();
  });
});

describe('Learn', () => {
  it('shows topic navigation and switches topics', async () => {
    vi.spyOn(api, 'documents').mockResolvedValue([doc()]);
    vi.spyOn(api, 'topics').mockResolvedValue(topics);
    const topic = vi.spyOn(api, 'topic').mockImplementation(async (id) => topicDetail(topics.find((t) => t.id === id)!));
    renderAt(<Learn />, { path: '/app/learn/:documentId/:topicId', route: '/app/learn/d1/11' });
    expect(await screen.findByRole('heading', { level: 2, name: 'Tokenization' })).toBeInTheDocument();
    expect(screen.getByText(/tokenization overview sentence/i)).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Topics' });
    await userEvent.click(within(nav).getByRole('link', { name: /word embeddings/i }));
    expect(await screen.findByRole('heading', { level: 2, name: 'Word Embeddings' })).toBeInTheDocument();
    expect(topic).toHaveBeenCalledWith(12);
  });
});

describe('Quiz', () => {
  it('records answers, review marks and submits all responses', async () => {
    vi.spyOn(api, 'saveResponses').mockResolvedValue(quiz);
    const submit = vi.spyOn(api, 'submitQuiz').mockResolvedValue(result);
    renderAt(<ExamRunner quiz={quiz} />, { path: '/app/practice/:quizId', route: '/app/practice/q1' });
    expect(screen.getByText('Question 1 of 2')).toBeInTheDocument();
    expect(screen.queryByText(/correct answer/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('radio', { name: /tokenization/i }));
    expect(screen.getByText('1 of 2 answered')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByText('Question 2 of 2')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /mark for review/i }));
    await userEvent.click(screen.getByRole('button', { name: /finish/i }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/1 question unanswered/i)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: /submit quiz/i }));
    await waitFor(() => expect(submit).toHaveBeenCalled());
    const [, responses] = submit.mock.calls[0];
    expect(responses).toEqual([
      { question_id: 'a', selected_index: 0, marked_for_review: false },
      { question_id: 'b', selected_index: null, marked_for_review: true },
    ]);
    expect(await screen.findByTestId('navigated')).toBeInTheDocument();
  });

  it('does not send a late autosave after submitting', async () => {
    const save = vi.spyOn(api, 'saveResponses').mockResolvedValue(quiz);
    const submit = vi.spyOn(api, 'submitQuiz').mockResolvedValue(result);
    renderAt(<ExamRunner quiz={quiz} />, { path: '/app/practice/:quizId', route: '/app/practice/q1' });
    await userEvent.click(screen.getByRole('radio', { name: /tokenization/i }));
    await userEvent.click(screen.getAllByRole('button', { name: /^submit$/i })[0]);
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /submit quiz/i }));
    await waitFor(() => expect(submit).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 900)); // longer than the 700 ms autosave debounce
    expect(save).not.toHaveBeenCalled();
    expect(submit.mock.calls[0][1][0]).toMatchObject({ question_id: 'a', selected_index: 0 });
  });

  it('displays the server-computed score and explains wrong answers', async () => {
    vi.spyOn(api, 'quizResult').mockResolvedValue(result);
    renderAt(<QuizResults />, { path: '/app/practice/:quizId/results', route: '/app/practice/q1/results' });
    expect(await screen.findByText('50%')).toBeInTheDocument();
    expect(screen.getByText('1 of 2 correct')).toBeInTheDocument();
    expect(screen.getByText(/BLEU is a different concept/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry 1 missed/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: /incorrect/i }));
    expect(screen.queryByText(/which term matches splitting/i)).not.toBeInTheDocument();
  });
});

describe('API client', () => {
  it('creates a workspace, sends the token and maps network failures', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/api/workspaces')) return new Response(JSON.stringify({ token: 'sfw_test_token_123456789012345678901234' }), { status: 201 });
      if (url.endsWith('/api/documents')) {
        expect(new Headers(init?.headers).get('X-Workspace-Token')).toBe('sfw_test_token_123456789012345678901234');
        return new Response('[]', { status: 200 });
      }
      throw new TypeError('Failed to fetch');
    });
    vi.stubGlobal('fetch', fetchMock);
    const { resetWorkspace } = await import('../services/api');
    resetWorkspace();
    await expect(api.documents()).resolves.toEqual([]);
    await expect(api.progress()).rejects.toMatchObject({ code: 'network_error', status: 0 });
    vi.unstubAllGlobals();
  });

  it('surfaces backend error codes and messages', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) =>
      url.endsWith('/api/workspaces')
        ? new Response(JSON.stringify({ token: 'sfw_test_token_123456789012345678901234' }), { status: 201 })
        : new Response(JSON.stringify({ detail: 'Document not found.', code: 'document_not_found' }), { status: 404 }),
    ));
    await expect(api.document('missing')).rejects.toMatchObject({ status: 404, code: 'document_not_found', message: 'Document not found.' });
    vi.unstubAllGlobals();
  });
});
