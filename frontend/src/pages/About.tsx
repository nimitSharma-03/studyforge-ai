import { Github } from 'lucide-react';
import { Card, CardBody } from '../components/ui/Card';
import { GITHUB_URL } from '../config';

const ARCHITECTURE = [
  ['React + Vite frontend', 'TypeScript, Tailwind CSS, Recharts. Static site; talks to the API over HTTPS with an anonymous workspace token.'],
  ['FastAPI backend', 'Pydantic schemas, SQLAlchemy ORM, rate limiting, server-side quiz scoring and in-memory exports.'],
  ['NLP pipeline', 'Pure Python + scikit-learn. Runs synchronously on upload and stores topics, chunks, guides and questions.'],
  ['Database', 'SQLite for local development; PostgreSQL in production. Original files are not stored.'],
];

const PIPELINE = [
  ['Extraction', 'PyMuPDF reads PDF text spans with font sizes (larger or bold short lines become headings); python-docx uses heading styles and tables; python-pptx reads slide titles, bullets, tables and notes. Every block keeps its page, section or slide number. Repeated running headers and page numbers are removed; scanned PDFs are detected when pages contain images but no text.'],
  ['Normalisation', 'Unicode NFKC, quote and bullet normalisation, repair of words hyphenated across line breaks, and regex sentence segmentation that respects abbreviations such as “e.g.” and “Dr.”.'],
  ['Topic segmentation', 'The deepest heading level that yields at most 40 sections is used to split topics; tiny sections are merged and “(cont.)” slides are joined. Documents without headings fall back to a TextTiling-style algorithm: adjacent paragraph windows are compared with TF-IDF cosine similarity and the document is cut at the deepest similarity valleys.'],
  ['Keyphrases', 'Candidate phrases are runs of content words between stopwords, punctuation and common verbs. They are ranked with TF-IDF, treating topics as documents, and boosted when they appear in headings or as defined terms.'],
  ['Definitions', 'Lexical patterns such as “X is defined as Y”, “X refers to Y”, “X is the process of Y” and glossary lines “X: Y”. Weaker “X is a Y” matches are kept only when X is a known keyphrase or acronym.'],
  ['Learning guides', 'Sentences are ranked by TF-IDF degree centrality (TextRank-style), keyphrase coverage and position; maximal marginal relevance removes near-duplicates. Cue phrases identify relationships (“whereas”, “depends on”) and examples (“such as”, “for example”).'],
  ['Retrieval & QA', 'Chunks that respect topic and paragraph boundaries are indexed with a TF-IDF vectoriser (light stemming, unigrams and bigrams). Answers are the best-matching sentences, labelled supported / partial / insufficient using the similarity score and query-term coverage.'],
  ['Question generation', 'Definition MCQs (term ↔ description), cloze deletions of key concepts in central sentences, “such as” example questions, pattern-based short answers (“used for”, “consists of”, “because”), compare-and-contrast and topic outline long answers.'],
  ['Validation', 'Exactly four distinct options, correct-answer mapping verified, answer present in the source sentence, no option repeated in the stem, balanced option lengths, distractors not sharing roots with the answer or defined in terms of it, a completion probe against the source text, and duplicate/near-duplicate removal. Rejected candidates are counted and shown.'],
];

const LIMITATIONS = [
  'Rule-based generation favours definitional, factual and well-structured notes; narrative or highly mathematical material yields fewer questions.',
  'No part-of-speech tagger is used, so keyphrases are approximations and occasionally include non-noun words.',
  'TF-IDF similarity is lexical: paraphrased questions with different vocabulary may be marked as insufficient evidence.',
  'Scanned PDFs are not supported without external OCR; equations, images and diagrams are ignored.',
  'Accounts are anonymous browser workspaces. Clearing browser storage loses access to that workspace.',
  'On the free hosting tier the server sleeps when idle and the free PostgreSQL database has a limited lifetime.',
];

const FUTURE = [
  'Optional transformer embeddings (e.g. sentence-transformers) for semantic retrieval when a GPU or more memory is available.',
  'OCR for scanned notes and support for equations and figures.',
  'Spaced-repetition scheduling based on per-question history.',
  'Optional user accounts with sign-in for cross-device access.',
  'Human-in-the-loop editing and rating of generated questions to measure question quality.',
];

export default function About() {
  return (
    <div className="mx-auto max-w-4xl">
      <p className="eyebrow">About the project</p>
      <h1 className="mt-2 text-3xl font-semibold">StudyForge AI: An NLP-Based Personalized Learning and Examination Preparation Platform</h1>
      <p className="mt-4 text-lg leading-8 text-body">
        StudyForge AI is a document-grounded study platform built as a college NLP lab project. It processes a student's own lecture
        notes into topics, learning guides, exam-style questions and practice tests, using deterministic NLP that runs on a CPU.
      </p>

      <div className="mt-10 grid gap-6 md:grid-cols-2">
        <Card>
          <CardBody>
            <h2 className="text-lg font-semibold">Problem statement</h2>
            <p className="mt-2 text-sm leading-6 text-body">
              Before exams, students hold large amounts of unstructured material — slides, scanned handouts and notes — but little
              time to organise it. Generic chatbots answer from general knowledge rather than the syllabus taught in class, and can
              state incorrect information confidently. Students need revision material and practice questions that are drawn from,
              and traceable to, their own course content.
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <h2 className="text-lg font-semibold">Purpose</h2>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-body">
              <li>Organise uploaded notes into topics with page/slide references.</li>
              <li>Produce concise and detailed extractive learning guides.</li>
              <li>Generate and validate exam-oriented questions.</li>
              <li>Offer timed mid- and end-semester practice with server-side scoring.</li>
              <li>Track topic-level accuracy and recommend what to revise.</li>
            </ul>
          </CardBody>
        </Card>
      </div>

      <section className="mt-12">
        <h2 className="text-2xl font-semibold">Architecture</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {ARCHITECTURE.map(([name, text]) => (
            <div key={name} className="rounded-lg border border-line bg-surface p-4">
              <p className="font-semibold text-ink">{name}</p>
              <p className="mt-1 text-sm text-body">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-2xl font-semibold">NLP pipeline and offline question generation</h2>
        <p className="mt-2 text-sm text-muted">
          No language model is required. Every stage is rule-based or uses classical statistics (TF-IDF, cosine similarity), so results
          are reproducible and the whole pipeline runs offline.
        </p>
        <ol className="mt-5 space-y-4">
          {PIPELINE.map(([name, text], i) => (
            <li key={name} className="flex gap-4">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-navy text-xs font-semibold text-white">{i + 1}</span>
              <div>
                <p className="font-semibold text-ink">{name}</p>
                <p className="mt-0.5 text-sm leading-6 text-body">{text}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="mt-5 rounded-md border border-line bg-subtle px-4 py-3 text-sm text-body">
          An optional adapter for a locally running Ollama model can add free-form explanations. It is disabled by default, is
          clearly labelled when used, and the rest of the application never depends on it.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="text-2xl font-semibold">Technologies</h2>
        <p className="mt-2 text-sm leading-6 text-body">
          React 18, TypeScript, Vite, Tailwind CSS, Lucide icons, Recharts · Python 3.11, FastAPI, Pydantic, SQLAlchemy, SQLite /
          PostgreSQL · PyMuPDF, python-docx, python-pptx, scikit-learn, NumPy · pytest, Ruff, Vitest, React Testing Library · GitHub
          Actions, Render.
        </p>
      </section>

      <div className="mt-12 grid gap-6 md:grid-cols-2">
        <section>
          <h2 className="text-2xl font-semibold">Limitations</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-body">
            {LIMITATIONS.map((l) => <li key={l}>{l}</li>)}
          </ul>
        </section>
        <section>
          <h2 className="text-2xl font-semibold">Future scope</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-body">
            {FUTURE.map((l) => <li key={l}>{l}</li>)}
          </ul>
        </section>
      </div>

      <a
        href={GITHUB_URL}
        target="_blank"
        rel="noreferrer"
        className="mt-12 inline-flex items-center gap-2 rounded-md border border-line-strong bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-subtle"
      >
        <Github className="h-4 w-4" /> Source code and documentation on GitHub
      </a>
    </div>
  );
}
