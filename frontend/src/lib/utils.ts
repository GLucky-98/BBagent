import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const MIME_MAP: Record<string, string> = {
  ".ts": "text/typescript",
  ".tsx": "text/typescript",
  ".js": "text/javascript",
  ".jsx": "text/javascript",
  ".py": "text/x-python",
  ".json": "application/json",
  ".yaml": "text/yaml",
  ".yml": "text/yaml",
  ".md": "text/markdown",
  ".css": "text/css",
  ".html": "text/html",
  ".txt": "text/plain",
  ".env": "text/plain",
  ".gitignore": "text/plain",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".pdf": "application/pdf",
};

export function getMimeType(fileName: string): string {
  const ext = fileName.substring(fileName.lastIndexOf(".")).toLowerCase();
  return MIME_MAP[ext] ?? "text/plain";
}
