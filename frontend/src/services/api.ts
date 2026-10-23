import type {
  AskResponse,
  ContentPage,
  DeleteImpact,
  DocumentDetail,
  DocumentSummary,
  Health,
  IncorrectItem,
  LLMExplanation,
  ProgressSummary,
  QuestionBankPage,
  QuestionSetRequest,
  QuestionSetResponse,
  Quiz,
  QuizCreate,
  QuizHistoryItem,
  QuizResult,
  ResponseIn,
  TopicDetail,
  TopicSummary,
  WorkspaceInfo,
} from '../types/api';

/** Base URL of the backend. Empty in development (Vite proxies /api); set VITE_API_BASE_URL in production. */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const TOKEN_KEY = 'studyforge.workspaceToken';
const TOKEN_HEADER = 'X-Workspace-Token';

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
  get isNetwork() {
    return this.status === 0;
  }
}

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: the token lives only for this page load */
  }
}

let memoryToken: string | null = null;
let pendingWorkspace: Promise<string> | null = null;

async function parseError(response: Response): Promise<ApiError> {
  let code = 'http_error';
  let message = `Request failed (${response.status}).`;
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') message = body.detail;
    if (typeof body?.code === 'string') code = body.code;
  } catch {
    /* non-JSON error body */
  }
  if (response.status === 502 || response.status === 503 || response.status === 504) {
    if (code === 'http_error') {
      code = 'server_unavailable';
      message = 'The StudyForge server is starting up or temporarily unavailable. Please try again in a moment.';
    }
  }
  return new ApiError(response.status, code, message);
}

const networkError = () =>
  new ApiError(
    0,
    'network_error',
    'Cannot reach the StudyForge server. Check your connection; if the server was idle it may take up to a minute to wake up.',
  );

async function ensureWorkspace(): Promise<string> {
  const existing = memoryToken ?? readToken();
  if (existing) {
    memoryToken = existing;
    return existing;
  }
  if (!pendingWorkspace) {
    pendingWorkspace = (async () => {
      let response: Response;
      try {
        response = await fetch(`${API_BASE}/api/workspaces`, { method: 'POST' });
      } catch {
        throw networkError();
      }
      if (!response.ok) throw await parseError(response);
      const body = (await response.json()) as { token: string };
      memoryToken = body.token;
      writeToken(body.token);
      return body.token;
    })().finally(() => {
      pendingWorkspace = null;
    });
  }
  return pendingWorkspace;
}

export function resetWorkspace() {
  memoryToken = null;
  writeToken(null);
}

async function request<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const token = await ensureWorkspace();
  const headers = new Headers(init.headers);
  headers.set(TOKEN_HEADER, token);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api${path}`, { ...init, headers });
  } catch {
    throw networkError();
  }
  if (response.status === 401 && !retried) {
    // The stored workspace was deleted (e.g. the database was reset): start a fresh one.
    resetWorkspace();
    return request<T>(path, init, true);
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

function query(params: Record<string, string | number | boolean | (string | number)[] | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : '';
}

/** Upload with real transfer progress (fetch has no upload progress events). */
function uploadWithProgress(file: File, onProgress: (fraction: number) => void, retried = false): Promise<DocumentDetail> {
  return ensureWorkspace().then(
    (token) =>
      new Promise<DocumentDetail>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_BASE}/api/documents`);
        xhr.setRequestHeader(TOKEN_HEADER, token);
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) onProgress(event.loaded / event.total);
        };
        xhr.onerror = () => reject(networkError());
        xhr.onload = async () => {
          const response = new Response(xhr.responseText, { status: xhr.status });
          if (xhr.status === 401 && !retried) {
            resetWorkspace();
            uploadWithProgress(file, onProgress, true).then(resolve, reject);
            return;
          }
          if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
          else reject(await parseError(response));
        };
        const form = new FormData();
        form.append('file', file);
        xhr.send(form);
      }),
  );
}

/** Fetch a file with the workspace header and hand it to the browser as a download. */
async function download(path: string, fallbackName: string) {
  const token = await ensureWorkspace();
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api${path}`, { headers: { [TOKEN_HEADER]: token } });
  } catch {
    throw networkError();
  }
  if (!response.ok) throw await parseError(response);
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="([^"]+)"/);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = match?.[1] ?? fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export type ExportFormat = 'md' | 'txt' | 'pdf';

export const api = {
  health: async (): Promise<Health> => {
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/api/health`);
    } catch {
      throw networkError();
    }
    if (!response.ok && response.status !== 503) throw await parseError(response);
    return response.json();
  },
  workspace: () => request<WorkspaceInfo>('/workspaces/me'),
  deleteWorkspace: async () => {
    await request<void>('/workspaces/me', { method: 'DELETE' });
    resetWorkspace();
  },

  documents: () => request<DocumentSummary[]>('/documents'),
  document: (id: string) => request<DocumentDetail>(`/documents/${id}`),
  upload: uploadWithProgress,
  loadSample: () => request<DocumentDetail>('/documents/sample', { method: 'POST' }),
  renameDocument: (id: string, name: string) =>
    request<DocumentSummary>(`/documents/${id}`, { method: 'PATCH', ...json({ name }) }),
  deleteImpact: (id: string) => request<DeleteImpact>(`/documents/${id}/delete-impact`),
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: 'DELETE' }),
  content: (id: string, offset = 0, limit = 20, topicId?: number) =>
    request<ContentPage>(`/documents/${id}/content${query({ offset, limit, topic_id: topicId })}`),
  topics: (id: string) => request<TopicSummary[]>(`/documents/${id}/topics`),
  topic: (id: number) => request<TopicDetail>(`/topics/${id}`),
  ask: (documentId: string, question: string, topicId?: number | null) =>
    request<AskResponse>(`/documents/${documentId}/ask`, { method: 'POST', ...json({ question, topic_id: topicId ?? null }) }),
  llmExplanation: (topicId: number) => request<LLMExplanation>(`/topics/${topicId}/llm-explanation`, { method: 'POST' }),

  questionBank: (params: {
    document_id: string;
    topic_id?: number[];
    difficulty?: string[];
    question_type?: string[];
    category?: string[];
    search?: string;
    offset?: number;
    limit?: number;
  }) => request<QuestionBankPage>(`/questions${query(params)}`),
  generateQuestionSet: (body: QuestionSetRequest) =>
    request<QuestionSetResponse>('/questions/generate', { method: 'POST', ...json(body) }),

  createQuiz: (body: QuizCreate) => request<Quiz>('/quizzes', { method: 'POST', ...json(body) }),
  quizzes: () => request<QuizHistoryItem[]>('/quizzes'),
  quiz: (id: string) => request<Quiz>(`/quizzes/${id}`),
  saveResponses: (id: string, responses: ResponseIn[]) =>
    request<Quiz>(`/quizzes/${id}/responses`, { method: 'PUT', ...json({ responses }) }),
  submitQuiz: (id: string, responses: ResponseIn[], durationSeconds?: number) =>
    request<QuizResult>(`/quizzes/${id}/submit`, {
      method: 'POST',
      ...json({ responses, duration_seconds: durationSeconds }),
    }),
  quizResult: (id: string) => request<QuizResult>(`/quizzes/${id}/result`),
  retryQuiz: (id: string) => request<Quiz>(`/quizzes/${id}/retry`, { method: 'POST' }),
  deleteQuiz: (id: string) => request<void>(`/quizzes/${id}`, { method: 'DELETE' }),

  progress: () => request<ProgressSummary>('/progress/summary'),
  incorrect: (limit = 50) => request<IncorrectItem[]>(`/progress/incorrect${query({ limit })}`),

  exportNotes: (documentId: string, format: ExportFormat, mode: 'concise' | 'detailed') =>
    download(`/exports/documents/${documentId}/notes${query({ format, mode })}`, `revision-notes.${format}`),
  exportQuestions: (
    documentId: string,
    format: ExportFormat,
    filters: { answers: boolean; topic_id?: number[]; difficulty?: string[]; question_type?: string[]; category?: string[] },
  ) => download(`/exports/documents/${documentId}/questions${query({ format, ...filters })}`, `question-bank.${format}`),
  exportQuiz: (quizId: string, format: 'md' | 'txt' | 'pdf') =>
    download(`/exports/quizzes/${quizId}${query({ format })}`, `quiz-results.${format}`),
};
