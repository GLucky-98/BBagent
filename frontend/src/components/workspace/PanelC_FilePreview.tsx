import { forwardRef } from "react";
import { X, File, Loader2, AlertCircle } from "lucide-react";
import { Highlight, themes } from "prism-react-renderer";
import ReactMarkdown from "react-markdown";
import { useAppStore } from "../../store";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

function getFileUrl(path: string): string {
  return `${API_BASE}/files/raw?path=${encodeURIComponent(path)}`;
}

function LoadingViewer() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-(--color-muted-foreground) p-8 gap-3">
      <Loader2 className="w-8 h-8 animate-spin" />
      <span className="text-sm">Loading file...</span>
    </div>
  );
}

function ErrorViewer({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-(--color-muted-foreground) p-8 gap-3">
      <AlertCircle className="w-10 h-10 text-red-400" />
      <p className="text-sm font-medium text-red-500">Failed to load file</p>
      <p className="text-xs text-center max-w-[280px]">{message}</p>
    </div>
  );
}

function CodeViewer({
  content,
  mimeType,
}: {
  content: string;
  mimeType: string;
}) {
  const lang =
    mimeType === "text/typescript"
      ? "tsx"
      : mimeType === "text/javascript"
        ? "js"
        : mimeType === "text/x-python"
          ? "python"
          : mimeType === "text/html"
            ? "html"
            : mimeType === "text/css"
              ? "css"
              : mimeType === "application/json"
                ? "json"
                : mimeType === "text/yaml"
                  ? "yaml"
                  : mimeType === "text/markdown"
                    ? "markdown"
                    : "text";

  return (
    <Highlight theme={themes.github} code={content} language={lang}>
      {({ tokens, getLineProps, getTokenProps }) => (
        <pre className="p-4 text-xs font-mono leading-relaxed overflow-auto bg-(--color-background)">
          <code>
            {tokens.map((line, i) => (
              <div
                key={i}
                {...getLineProps({ line })}
                className="table-row"
              >
                <span className="table-cell text-right pr-4 text-(--color-muted-foreground)/40 select-none w-12">
                  {i + 1}
                </span>
                <span className="table-cell">
                  {line.map((token, key) => (
                    <span key={key} {...getTokenProps({ token })} />
                  ))}
                </span>
              </div>
            ))}
          </code>
        </pre>
      )}
    </Highlight>
  );
}

function MarkdownViewer({ content }: { content: string }) {
  return (
    <div className="p-4 text-sm leading-relaxed text-(--color-foreground) prose prose-sm max-w-none overflow-auto">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}

function ImageViewer({ path, name }: { path: string; name: string }) {
  return (
    <div className="flex items-center justify-center h-full p-4 bg-(--color-muted)/20">
      <img
        src={getFileUrl(path)}
        alt={name}
        className="max-w-full max-h-full object-contain rounded-md"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    </div>
  );
}

function PdfViewer({ path, name }: { path: string; name: string }) {
  return (
    <iframe
      src={getFileUrl(path)}
      title={name}
      className="w-full h-full border-0"
    />
  );
}

function UnsupportedViewer({ fileName }: { fileName: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-(--color-muted-foreground) p-8">
      <File className="w-12 h-12 mb-3 text-(--color-muted-foreground)/30" />
      <p className="text-sm font-medium">Preview not available</p>
      <p className="text-xs text-(--color-muted-foreground)/60 mt-1 text-center">
        &quot;{fileName}&quot; cannot be previewed in the browser.
        <br />
        Open in an external editor to view its contents.
      </p>
    </div>
  );
}

function renderPreview(
  mimeType: string,
  content: string | null,
  error: string | undefined,
  path: string,
  name: string
) {
  if (error) {
    return <ErrorViewer message={error} />;
  }

  if (content === null) {
    return <LoadingViewer />;
  }

  if (mimeType.startsWith("image/")) {
    return <ImageViewer path={path} name={name} />;
  }

  if (mimeType === "application/pdf") {
    return <PdfViewer path={path} name={name} />;
  }

  if (mimeType === "text/markdown") {
    return <MarkdownViewer content={content} />;
  }

  if (mimeType.startsWith("text/") || mimeType === "application/json") {
    return <CodeViewer content={content} mimeType={mimeType} />;
  }

  return <UnsupportedViewer fileName={name} />;
}

interface Props {
  width: number;
}

export const PanelC_FilePreview = forwardRef<HTMLDivElement, Props>(
  ({ width }, ref) => {
    const previewFile = useAppStore((s) => s.previewFile);
    const closeFilePreview = useAppStore((s) => s.closeFilePreview);

    if (!previewFile) return null;

    return (
      <div
        ref={ref}
        className="shrink-0 border-l border-(--color-rule-soft) bg-(--color-background) flex flex-col overflow-hidden"
        style={{ width }}
      >
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-(--color-rule-soft) shrink-0">
          <div className="flex items-center gap-2 font-mono text-[12px] text-(--color-foreground) min-w-0">
            <File className="w-3.5 h-3.5 shrink-0 text-(--color-ink-3)" />
            <span className="truncate">{previewFile.name}</span>
          </div>
        <button
          onClick={closeFilePreview}
          className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {renderPreview(
          previewFile.mimeType,
          previewFile.content,
          previewFile.error,
          previewFile.path,
          previewFile.name
        )}
      </div>
    </div>
  );
});

PanelC_FilePreview.displayName = "PanelC_FilePreview";
