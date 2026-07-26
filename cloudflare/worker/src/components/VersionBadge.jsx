import { GitCommitHorizontal } from 'lucide-react';

const shortSha = (sha) => sha?.slice(0, 7) || 'unavailable';

export default function VersionBadge({ label, sha, repositoryUrl }) {
  const className = "flex items-center gap-1.5 bg-blue-50 dark:bg-blue-950/30 px-2.5 py-1 rounded-md border border-blue-100 dark:border-blue-900/50 shadow-sm text-[9px] font-black uppercase tracking-widest text-blue-600 dark:text-blue-400 transition-colors";
  const content = (
    <>
      <GitCommitHorizontal className="size-3" />
      <span>{label}</span>
      <code className="font-mono normal-case tracking-normal" title={sha || undefined}>
        {shortSha(sha)}
      </code>
    </>
  );

  if (!sha) {
    return <span className={className}>{content}</span>;
  }

  return (
    <a
      href={`${repositoryUrl}/commit/${sha}`}
      target="_blank"
      rel="noopener noreferrer"
      className={`${className} hover:border-primary/40 hover:text-primary`}
      title={`${label}: ${sha}`}
    >
      {content}
    </a>
  );
}
