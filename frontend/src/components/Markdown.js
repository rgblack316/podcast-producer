import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function Markdown({ text, testId }) {
  return (
    <div className="prose-bb" data-testid={testId}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text || ""}</ReactMarkdown>
    </div>
  );
}
