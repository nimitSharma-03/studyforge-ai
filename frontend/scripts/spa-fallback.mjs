// Copies the SPA shell to 404.html so hosts that serve 404.html for unknown paths still boot the
// React router on deep links (e.g. /app/learn/...). Render's rewrite rule is the primary mechanism.
import { copyFileSync } from 'node:fs';

copyFileSync('dist/index.html', 'dist/404.html');
console.log('spa-fallback: wrote dist/404.html');
