import { Compass } from 'lucide-react';
import { ButtonLink } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';

export default function NotFound() {
  return (
    <div className="container-page py-16">
      <EmptyState
        icon={<Compass className="h-5 w-5" />}
        title="Page not found"
        description="The page you are looking for does not exist or has moved."
        action={
          <>
            <ButtonLink to="/app">Go to dashboard</ButtonLink>
            <ButtonLink to="/" variant="secondary">
              Home
            </ButtonLink>
          </>
        }
      />
    </div>
  );
}
