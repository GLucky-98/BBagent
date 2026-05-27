import { X, File } from "lucide-react";
import { Highlight, themes } from "prism-react-renderer";
import { useAppStore } from "../../store";

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
        <pre className="p-4 text-xs font-mono leading-relaxed overflow-auto bg-[--color-background]">
          <code>
            {tokens.map((line, i) => (
              <div
                key={i}
                {...getLineProps({ line })}
                className="table-row"
              >
                <span className="table-cell text-right pr-4 text-[--color-muted-foreground]/40 select-none w-12">
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
    <div className="p-4 text-sm leading-relaxed text-[--color-foreground] whitespace-pre-wrap">
      {content}
    </div>
  );
}

function ImageViewer({
  src,
}: {
  src: string;
}) {
  return (
    <div className="flex items-center justify-center h-full p-4 bg-[--color-muted]/20">
      <img
        src={src}
        alt="Preview"
        className="max-w-full max-h-full object-contain rounded-md"
      />
    </div>
  );
}

function UnsupportedViewer({ fileName }: { fileName: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground] p-8">
      <File className="w-12 h-12 mb-3 text-[--color-muted-foreground]/30" />
      <p className="text-sm font-medium">Preview not available</p>
      <p className="text-xs text-[--color-muted-foreground]/60 mt-1 text-center">
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
  name: string
) {
  if (!content) {
    return <UnsupportedViewer fileName={name} />;
  }

  if (mimeType.startsWith("image/")) {
    return <ImageViewer src={content} />;
  }

  if (
    mimeType === "text/markdown" ||
    mimeType.endsWith("/markdown")
  ) {
    return <MarkdownViewer content={content} />;
  }

  if (mimeType === "application/pdf") {
    return <UnsupportedViewer fileName={name} />;
  }

  if (mimeType.startsWith("text/") || mimeType === "application/json") {
    return <CodeViewer content={content} mimeType={mimeType} />;
  }

  return <UnsupportedViewer fileName={name} />;
}

export function PanelC_FilePreview() {
  const previewFile = useAppStore((s) => s.previewFile);
  const closeFilePreview = useAppStore((s) => s.closeFilePreview);

  if (!previewFile) return null;

  return (
    <div className="w-[360px] shrink-0 border-l border-[--color-border] bg-white flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[--color-border] shrink-0">
        <span className="text-sm font-medium truncate flex-1">
          {previewFile.name}
        </span>
        <button
          onClick={closeFilePreview}
          className="p-1 rounded hover:bg-[--color-secondary] text-[--color-muted-foreground] shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {renderPreview(
          previewFile.mimeType,
          previewFile.content,
          previewFile.name
        )}
      </div>
    </div>
  );
}
