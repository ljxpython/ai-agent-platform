// FIXME  MC80OmFIVnBZMlhtblk3a3ZiUG1yS002TlU1T1dnPT06OWE1MjJkYTI=

"use client";

import "./markdown-styles.css";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import { FC, memo, useState } from "react";
import { CheckIcon, CopyIcon } from "lucide-react";
import { SyntaxHighlighter } from "@/components/thread/syntax-highlighter";
// TODO  MS80OmFIVnBZMlhtblk3a3ZiUG1yS002TlU1T1dnPT06OWE1MjJkYTI=

import { TooltipIconButton } from "@/components/thread/tooltip-icon-button";
import { cn } from "@/lib/utils";

import "katex/dist/katex.min.css";

interface CodeHeaderProps {
  language?: string;
  code: string;
}
// FIXME  Mi80OmFIVnBZMlhtblk3a3ZiUG1yS002TlU1T1dnPT06OWE1MjJkYTI=

const useCopyToClipboard = ({
  copiedDuration = 3000,
}: {
  copiedDuration?: number;
} = {}) => {
  const [isCopied, setIsCopied] = useState<boolean>(false);

  const copyToClipboard = (value: string) => {
    if (!value) return;

    navigator.clipboard.writeText(value).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), copiedDuration);
    });
  };

  return { isCopied, copyToClipboard };
};

const CodeHeader: FC<CodeHeaderProps> = ({ language, code }) => {
  const { isCopied, copyToClipboard } = useCopyToClipboard();
  const onCopy = () => {
    if (!code || isCopied) return;
    copyToClipboard(code);
  };

  return (
    <div className="flex items-center justify-between gap-4 rounded-t-lg bg-slate-800 px-4 py-3 text-sm font-medium text-slate-200">
      <span className="lowercase [&>span]:text-xs text-slate-300">{language}</span>
      <TooltipIconButton
        tooltip="复制代码"
        onClick={onCopy}
        className="hover:bg-slate-700 rounded-md transition-colors"
      >
        {!isCopied && <CopyIcon className="w-4 h-4" />}
        {isCopied && <CheckIcon className="w-4 h-4 text-green-400" />}
      </TooltipIconButton>
    </div>
  );
};

const defaultComponents: any = {
  h1: ({ className, ...props }: { className?: string }) => (
    <h1
      className={cn(
        "mb-6 scroll-m-20 text-2xl font-bold tracking-tight last:mb-0 text-slate-900",
        className,
      )}
      {...props}
    />
  ),
  h2: ({ className, ...props }: { className?: string }) => (
    <h2
      className={cn(
        "mt-6 mb-3 scroll-m-20 text-xl font-semibold tracking-tight first:mt-0 last:mb-0 text-slate-800",
        className,
      )}
      {...props}
    />
  ),
  h3: ({ className, ...props }: { className?: string }) => (
    <h3
      className={cn(
        "mt-5 mb-3 scroll-m-20 text-lg font-semibold tracking-tight first:mt-0 last:mb-0 text-slate-700",
        className,
      )}
      {...props}
    />
  ),
  h4: ({ className, ...props }: { className?: string }) => (
    <h4
      className={cn(
        "mt-4 mb-2 scroll-m-20 text-base font-semibold tracking-tight first:mt-0 last:mb-0 text-slate-700",
        className,
      )}
      {...props}
    />
  ),
  h5: ({ className, ...props }: { className?: string }) => (
    <h5
      className={cn(
        "mt-3 mb-2 text-sm font-semibold first:mt-0 last:mb-0 text-slate-600",
        className,
      )}
      {...props}
    />
  ),
  h6: ({ className, ...props }: { className?: string }) => (
    <h6
      className={cn("mt-2 mb-2 text-sm font-semibold first:mt-0 last:mb-0 text-slate-600", className)}
      {...props}
    />
  ),
  p: ({ className, ...props }: { className?: string }) => (
    <p
      className={cn("mt-5 mb-5 leading-7 first:mt-0 last:mb-0 text-base", className)}
      {...props}
    />
  ),
  a: ({ className, href, ...props }: { className?: string; href?: string }) => (
    <a
      className={cn(
        "text-blue-600 font-medium underline underline-offset-2 cursor-pointer hover:text-blue-700 transition-colors",
        className,
      )}
      href={href}
      target={href?.startsWith('http') ? '_blank' : undefined}
      rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
      {...props}
    />
  ),
  blockquote: ({ className, ...props }: { className?: string }) => (
    <blockquote
      className={cn("border-l-2 pl-6 italic text-slate-600 bg-slate-50/50 py-2 my-4 rounded-r-lg", className)}
      {...props}
    />
  ),
  ul: ({ className, ...props }: { className?: string }) => (
    <ul
      className={cn("my-4 ml-6 list-disc [&>li]:mt-1.5 text-base leading-relaxed", className)}
      {...props}
    />
  ),
  ol: ({ className, ...props }: { className?: string }) => (
    <ol
      className={cn("my-4 ml-6 list-decimal [&>li]:mt-1.5 text-base leading-relaxed", className)}
      {...props}
    />
  ),
  hr: ({ className, ...props }: { className?: string }) => (
    <hr
      className={cn("my-6 border-slate-200", className)}
      {...props}
    />
  ),
  table: ({ className, ...props }: { className?: string }) => (
    <table
      className={cn(
        "my-6 w-full border-separate border-spacing-0 overflow-y-auto border border-slate-200 rounded-lg",
        className,
      )}
      {...props}
    />
  ),
  th: ({ className, ...props }: { className?: string }) => (
    <th
      className={cn(
        "bg-slate-50 px-4 py-3 text-left font-semibold text-slate-700 first:rounded-tl-lg last:rounded-tr-lg [&[align=center]]:text-center [&[align=right]]:text-right border-b border-slate-200",
        className,
      )}
      {...props}
    />
  ),
  td: ({ className, ...props }: { className?: string }) => (
    <td
      className={cn(
        "border-b border-slate-200 px-4 py-3 text-left last:border-r [&[align=center]]:text-center [&[align=right]]:text-right",
        className,
      )}
      {...props}
    />
  ),
  tr: ({ className, ...props }: { className?: string }) => (
    <tr
      className={cn(
        "m-0 border-b border-slate-200 p-0 first:border-t [&:last-child>td:first-child]:rounded-bl-lg [&:last-child>td:last-child]:rounded-br-lg hover:bg-slate-50/50 transition-colors",
        className,
      )}
      {...props}
    />
  ),
  sup: ({ className, ...props }: { className?: string }) => (
    <sup
      className={cn("[&>a]:text-xs [&>a]:no-underline", className)}
      {...props}
    />
  ),
  pre: ({ className, ...props }: { className?: string }) => (
    <pre
      className={cn(
        "max-w-4xl overflow-x-auto rounded-lg bg-slate-900 text-slate-100 border border-slate-700",
        className,
      )}
      {...props}
    />
  ),
  code: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => {
    const match = /language-(\w+)/.exec(className || "");

    if (match) {
      const language = match[1];
      const code = String(children).replace(/\n$/, "");

      return (
        <>
          <CodeHeader
            language={language}
            code={code}
          />
          <SyntaxHighlighter
            language={language}
            className={className}
          >
            {code}
          </SyntaxHighlighter>
        </>
      );
    }

    return (
      <code
        className={cn("rounded-md bg-slate-100 px-1.5 py-0.5 text-sm font-medium text-slate-800 border border-slate-200", className)}
        {...props}
      >
        {children}
      </code>
    );
  },
  img: ({ className, src, alt, ...props }: { className?: string; src?: string; alt?: string }) => (
    <img
      className={cn(
        "max-w-full h-auto rounded-xl border border-slate-200 shadow-sm hover:shadow-lg transition-all duration-300 cursor-pointer my-6",
        className,
      )}
      src={src}
      alt={alt || "图片"}
      style={{ maxHeight: '400px', objectFit: 'contain' }}
      onClick={() => src && window.open(src, '_blank')}
      {...props}
    />
  ),
};

const MarkdownTextImpl: FC<{ children: string }> = ({ children }) => {
  return (
    <div className="markdown-content text-base leading-relaxed text-slate-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={defaultComponents}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
};

export const MarkdownText = memo(MarkdownTextImpl);
// NOTE  My80OmFIVnBZMlhtblk3a3ZiUG1yS002TlU1T1dnPT06OWE1MjJkYTI=
