import { ACCEPTED_EXTENSIONS } from '../config';
import { formatBytes } from './format';

/** Client-side pre-check; the server repeats every check (type signature, size, content). */
export function validateFile(file: File, maxMb: number): string | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(ext)) {
    return `“${file.name}” is not supported. Upload a PDF, DOCX or PPTX file.`;
  }
  if (file.size === 0) return 'This file is empty.';
  if (file.size > maxMb * 1024 * 1024) return `This file is ${formatBytes(file.size)}. The maximum size is ${maxMb} MB.`;
  return null;
}
