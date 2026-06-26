import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Highlight, themes } from "prism-react-renderer";
import { cn } from "../lib/utils";

// ── Extract text content from React children ──
function extractText(children: React.ReactNode): string {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(extractText).join("");
  if (children && typeof children === "object" && "props" in (children as React.ReactElement)) {
    const el = children as React.ReactElement<{ children?: React.ReactNode }>;
    return extractText(el.props.children);
  }
  return "";
}

// ── prism-react-renderer supported language list ──
const SUPPORTED_LANGUAGES = new Set([
  "text", "bash", "c", "clike", "cpp", "css", "dart", "diff", "go", "graphql",
  "ini", "java", "javascript", "json", "kotlin", "latex", "less", "lua",
  "makefile", "markdown", "markup", "objectivec", "ocaml", "pascal", "perl",
  "php", "powershell", "python", "r", "reason", "ruby", "rust", "sass",
  "scala", "scss", "sql", "swift", "tsx", "typescript", "vim", "visual",
  "wasm", "yaml", "zig",
]);

// language alias mapping (common aliases → supported language names)
const LANGUAGE_ALIASES: Record<string, string> = {
  sh: "bash", shell: "bash", zsh: "bash", fish: "bash",
  js: "javascript", ts: "typescript", jsx: "tsx", py: "python",
  rb: "ruby", rs: "rust", golang: "go", kt: "kotlin",
  yml: "yaml", tf: "hcl", hcl: "hcl",
  dockerfile: "docker", make: "makefile",
  cxx: "cpp", cc: "cpp", csharp: "csharp", cs: "csharp",
  objj: "objectivec", objc: "objectivec",
  plaintext: "text", txt: "text", conf: "ini", cfg: "ini",
  console: "bash", terminal: "bash", cmd: "bash",
  html: "markup", xml: "markup", svg: "markup",
  md: "markdown", tex: "latex",
};

function resolveLanguage(lang: string): string {
  const lower = lang.toLowerCase().trim();
  if (SUPPORTED_LANGUAGES.has(lower)) return lower;
  if (LANGUAGE_ALIASES[lower]) return LANGUAGE_ALIASES[lower];
  return "text";
}

// ── Code block renderer with syntax highlighting ──
const CodeBlock = memo(function CodeBlock({ language, code }: { language: string; code: string }) {
  const resolvedLang = resolveLanguage(language || "text");

  return (
    <Highlight code={code} language={resolvedLang} theme={themes.vsLight}>
      {({ className: cls, style, tokens, getLineProps, getTokenProps }) => (
        <pre
          className={cn("text-[12.5px] font-mono rounded-lg p-3 my-2 overflow-x-auto border border-(--color-border) max-w-full whitespace-pre", cls)}
          style={style}
        >
          {tokens.map((line, i) => (
            <div key={i} {...getLineProps({ line })}>
              {line.map((token, key) => (
                <span key={key} {...getTokenProps({ token })} />
              ))}
            </div>
          ))}
        </pre>
      )}
    </Highlight>
  );
});

// ── fix unclosed code blocks in streaming Markdown ──
function fixStreamingMarkdown(content: string): string {
  const lines = content.split('\n');
  let fenceCount = 0;
  for (const line of lines) {
    const trimmed = line.trimStart();
    if (trimmed.startsWith('```')) {
      fenceCount++;
    }
  }
  if (fenceCount % 2 !== 0) {
    return content + '\n```';
  }
  return content;
}

// ── preprocess: fix non-standard Markdown syntax from LLM output ──
// LLM (especially in Chinese contexts) often omits required spaces after Markdown markers, causing parse failures.
// e.g. `##Title` → `## Title`, `-listitem` → `- listitem`, `1.item` → `1. item`
//
// Also converts literal escape sequences (\n, \t) to real characters, preventing line break loss from JSON double-encoding.
function normalizeMarkdown(content: string): string {
  return content
    // 1. convert literal \n, \t to real characters
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    // 2. fix Markdown markers missing spaces line by line
    .split('\n')
    .map((line) => {
      // fix heading missing space: ##text → ## text (## followed by non-space, non-# char)
      const headingMatch = line.match(/^(#{1,6})([^\s#])/);
      if (headingMatch) {
        return headingMatch[1] + ' ' + headingMatch[2] + line.slice(headingMatch[0].length);
      }
      // fix unordered list missing space: -text → - text (but does not match ---, --text etc. separators)
      const ulMatch = line.match(/^([-*+])([^\s\-*+])/);
      if (ulMatch) {
        return ulMatch[1] + ' ' + ulMatch[2] + line.slice(ulMatch[0].length);
      }
      // fix ordered list missing space: 1.text → 1. text
      const olMatch = line.match(/^(\d+\.)([^\s])/);
      if (olMatch) {
        return olMatch[1] + ' ' + olMatch[2] + line.slice(olMatch[0].length);
      }
      return line;
    })
    .join('\n');
}

// ── Markdown content renderer ──
export const MarkdownContent = memo(function MarkdownContent({
  content,
  isStreaming = false,
}: {
  content: string;
  isStreaming?: boolean;
}) {
  const displayContent = isStreaming
    ? fixStreamingMarkdown(content)
    : normalizeMarkdown(content);
  return (
    <div className="min-w-0 break-words [overflow-wrap:anywhere] [&_p]:break-words [&_p]:min-w-0 [&_li]:break-words [&_h1]:break-words [&_h2]:break-words [&_h3]:break-words [&_h4]:break-words [&_blockquote]:break-words [&_a]:break-words [&_strong]:break-words [&_em]:break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="text-[14.5px] leading-[1.65] my-1.5">{children}</p>,
          table: ({ children }) => (
            <div className="overflow-x-auto my-3 rounded-lg border border-(--color-border)">
              <table className="min-w-full border-collapse text-[13px]">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-(--color-border) px-3 py-1.5 bg-(--color-secondary) text-left text-[12px] font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-(--color-border) px-3 py-1.5 text-[13px]">{children}</td>
          ),
          pre: ({ children }) => {
            return <>{children}</>;
          },
          code: ({ className, children }) => {
            const codeText = extractText(children);
            // has language- prefix → code block with specified language
            if (className && className.includes("language-")) {
              const language = className.replace("language-", "").trim();
              const codeContent = codeText.replace(/\n$/, "");
              return <CodeBlock language={language} code={codeContent} />;
            }
            // contains newline → fenced code block without specified language (```\n...\n```), not inline code
            if (codeText.includes('\n')) {
              return <CodeBlock language="" code={codeText.replace(/\n$/, "")} />;
            }
            // inline code
            return (
              <code className="px-1.5 py-0.5 rounded bg-(--color-tint) text-(--color-foreground) text-[12.5px] font-mono border border-(--color-border) whitespace-nowrap">
                {children}
              </code>
            );
          },
          ul: ({ children, className }) => {
            const isTaskList = className?.includes?.("contains-task-list");
            return (
              <ul className={cn(
                "pl-5 my-2 text-[14.5px] space-y-0.5 break-words",
                isTaskList ? "list-none" : "list-disc"
              )}>
                {children}
              </ul>
            );
          },
          ol: ({ children }) => <ol className="list-decimal pl-5 my-2 text-[14.5px] space-y-0.5 break-words">{children}</ol>,
          li: ({ children, className }) => {
            const isTaskItem = className?.includes?.("task-list-item");
            return <li className={cn("break-words", isTaskItem && "list-none -ml-5")}>{children}</li>;
          },
          input: ({ type, checked, disabled }) => {
            if (type === "checkbox") {
              return (
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabled}
                  className="mr-1.5 align-middle accent-(--color-primary)"
                  readOnly
                />
              );
            }
            return <input type={type} />;
          },
          img: ({ src, alt }) => (
            <img
              src={src}
              alt={alt || ""}
              className="max-w-full h-auto rounded-lg my-2 border border-(--color-border)"
              loading="lazy"
            />
          ),
          a: ({ href, children }) => (
            <a href={href} className="text-(--color-primary) hover:opacity-80 break-words" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          h1: ({ children }) => <h1 className="text-[20px] font-semibold mt-4 mb-1.5 tracking-[-0.01em] break-words">{children}</h1>,
          h2: ({ children }) => <h2 className="text-[17px] font-semibold mt-3 mb-1.5 tracking-[-0.01em] break-words">{children}</h2>,
          h3: ({ children }) => <h3 className="text-[15px] font-semibold mt-3 mb-1 break-words">{children}</h3>,
          h4: ({ children }) => <h4 className="text-[14px] font-semibold mt-2 mb-1 break-words">{children}</h4>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-(--color-foreground) pl-3 my-2 text-[14px] text-(--color-ink-2) break-words">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-(--color-rule-soft)" />,
          del: ({ children }) => <del className="line-through text-(--color-ink-3)">{children}</del>,
        }}
      >
        {displayContent}
      </ReactMarkdown>
    </div>
  );
});
