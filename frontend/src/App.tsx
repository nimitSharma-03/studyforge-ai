import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { AppLayout } from './layouts/AppLayout';
import { PublicLayout } from './layouts/PublicLayout';
import { PageLoader } from './components/ui/Feedback';
import Landing from './pages/Landing';
import NotFound from './pages/NotFound';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Materials = lazy(() => import('./pages/Materials'));
const DocumentDetail = lazy(() => import('./pages/DocumentDetail'));
const Upload = lazy(() => import('./pages/Upload'));
const Learn = lazy(() => import('./pages/Learn'));
const QuestionBank = lazy(() => import('./pages/QuestionBank'));
const PracticeSetup = lazy(() => import('./pages/PracticeSetup'));
const QuizTake = lazy(() => import('./pages/QuizTake'));
const QuizResults = lazy(() => import('./pages/QuizResults'));
const Progress = lazy(() => import('./pages/Progress'));
const About = lazy(() => import('./pages/About'));

export default function App() {
  return (
    <Suspense fallback={<div className="p-8"><PageLoader /></div>}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Landing />} />
          <Route path="about" element={<div className="container-page py-12"><About /></div>} />
        </Route>
        <Route path="app" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="materials" element={<Materials />} />
          <Route path="materials/:documentId" element={<DocumentDetail />} />
          <Route path="upload" element={<Upload />} />
          <Route path="learn" element={<Learn />} />
          <Route path="learn/:documentId" element={<Learn />} />
          <Route path="learn/:documentId/:topicId" element={<Learn />} />
          <Route path="questions" element={<QuestionBank />} />
          <Route path="practice" element={<PracticeSetup />} />
          <Route path="practice/:quizId" element={<QuizTake />} />
          <Route path="practice/:quizId/results" element={<QuizResults />} />
          <Route path="progress" element={<Progress />} />
          <Route path="about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
