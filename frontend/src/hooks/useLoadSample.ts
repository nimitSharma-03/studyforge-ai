import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../components/ui/Toast';
import { api, ApiError } from '../services/api';

/** Adds the bundled demonstration notes to the workspace and opens the processing summary. */
export function useLoadSample() {
  const [loading, setLoading] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();
  const load = async () => {
    setLoading(true);
    try {
      const doc = await api.loadSample();
      toast(doc.duplicate ? 'The demo notes are already in your materials.' : 'Demo notes processed successfully.');
      navigate(`/app/materials/${doc.id}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not load the demo notes.', 'error');
    } finally {
      setLoading(false);
    }
  };
  return { load, loading };
}
