/**
 * FilePreview Component
 *
 * Displays file previews with support for code syntax highlighting,
 * images, PDFs, and text files.
 */

import React, { useEffect, useState } from 'react';

interface FileMetadata {
  path: string;
  name: string;
  size: number;
  mime_type: string;
  created_at?: string;
  modified_at?: string;
  is_directory: boolean;
  is_readable: boolean;
  is_writable: boolean;
}

interface FilePreviewData {
  path: string;
  name: string;
  mime_type: string;
  size: number;
  preview_type: 'text' | 'code' | 'image' | 'pdf' | 'binary';
  content?: string;
  language?: string;
  lines?: number;
  truncated: boolean;
  max_lines: number;
}

interface FilePreviewProps {
  filePath: string;
  maxLines?: number;
  onDownload?: (path: string) => void;
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
};

const getLanguageFromExtension = (path: string): string => {
  const ext = path.split('.').pop()?.toLowerCase() || '';
  const languageMap: Record<string, string> = {
    py: 'python',
    js: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    jsx: 'javascript',
    java: 'java',
    c: 'c',
    cpp: 'cpp',
    cs: 'csharp',
    go: 'go',
    rs: 'rust',
    rb: 'ruby',
    php: 'php',
    swift: 'swift',
    kt: 'kotlin',
    sh: 'bash',
    html: 'html',
    css: 'css',
    json: 'json',
    xml: 'xml',
    yaml: 'yaml',
    yml: 'yaml',
    md: 'markdown',
    sql: 'sql',
  };
  return languageMap[ext] || ext;
};

export const FilePreview: React.FC<FilePreviewProps> = ({
  filePath,
  maxLines = 1000,
  onDownload,
}) => {
  const [preview, setPreview] = useState<FilePreviewData | null>(null);
  const [metadata, setMetadata] = useState<FileMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightLines, setHighlightLines] = useState<Set<number>>(new Set());

  useEffect(() => {
    const fetchPreview = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch metadata
        const metaResponse = await fetch(`/api/v1/files/metadata/${encodeURIComponent(filePath)}`);
        if (!metaResponse.ok) throw new Error('Failed to fetch metadata');
        const metaData = await metaResponse.json();
        setMetadata(metaData);

        // Fetch preview
        const previewResponse = await fetch(
          `/api/v1/files/preview/${encodeURIComponent(filePath)}?max_lines=${maxLines}`
        );
        if (!previewResponse.ok) throw new Error('Failed to fetch preview');
        const previewData = await previewResponse.json();
        setPreview(previewData);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchPreview();
  }, [filePath, maxLines]);

  const renderCodePreview = (content: string, language?: string) => {
    const lines = content.split('\n');
    const displayLines = lines.slice(0, maxLines);

    return (
      <div className="bg-gray-900 text-gray-100 p-4 rounded overflow-x-auto font-mono text-sm">
        <div className="flex">
          {/* Line numbers */}
          <div className="text-gray-600 pr-4 select-none">
            {displayLines.map((_, i) => (
              <div key={i} className="h-6">
                {i + 1}
              </div>
            ))}
          </div>

          {/* Code content */}
          <div className="flex-1">
            {displayLines.map((line, i) => (
              <div
                key={i}
                className={`h-6 ${
                  highlightLines.has(i + 1) ? 'bg-yellow-900 bg-opacity-30' : ''
                }`}
              >
                {line || ' '}
              </div>
            ))}
          </div>
        </div>

        {lines.length > maxLines && (
          <div className="text-gray-500 text-xs mt-2">
            ... {lines.length - maxLines} more lines
          </div>
        )}
      </div>
    );
  };

  const renderTextPreview = (content: string) => {
    const lines = content.split('\n').slice(0, maxLines);

    return (
      <div className="bg-white p-4 rounded border border-gray-200 whitespace-pre-wrap text-sm text-gray-800 max-h-96 overflow-y-auto">
        {lines.join('\n')}
        {content.split('\n').length > maxLines && (
          <div className="text-gray-500 text-xs mt-2">
            ... {content.split('\n').length - maxLines} more lines
          </div>
        )}
      </div>
    );
  };

  const renderImagePreview = () => {
    return (
      <div className="bg-gray-100 p-4 rounded flex items-center justify-center max-h-96">
        <img
          src={`/api/v1/files/download/${encodeURIComponent(filePath)}`}
          alt={metadata?.name}
          className="max-w-full max-h-full"
        />
      </div>
    );
  };

  const renderPdfPreview = () => {
    return (
      <div className="bg-gray-100 p-4 rounded text-center">
        <div className="text-gray-600 mb-4">📄 PDF File</div>
        <button
          onClick={() => onDownload?.(filePath)}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Download PDF
        </button>
      </div>
    );
  };

  const renderBinaryPreview = () => {
    return (
      <div className="bg-gray-100 p-4 rounded text-center">
        <div className="text-gray-600 mb-4">📦 Binary File</div>
        <button
          onClick={() => onDownload?.(filePath)}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Download File
        </button>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-600">Loading preview...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded text-red-700">
        {error}
      </div>
    );
  }

  if (!preview || !metadata) {
    return (
      <div className="p-4 text-gray-600">
        No preview available
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-bold text-gray-900">{metadata.name}</h3>
          <button
            onClick={() => onDownload?.(filePath)}
            className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
          >
            ⬇️ Download
          </button>
        </div>

        {/* Metadata */}
        <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
          <div>📦 {formatFileSize(metadata.size)}</div>
          <div>📝 {metadata.mime_type}</div>
          {metadata.modified_at && (
            <div>🕐 {new Date(metadata.modified_at).toLocaleString()}</div>
          )}
          {preview.lines && (
            <div>📄 {preview.lines} lines</div>
          )}
        </div>

        {preview.truncated && (
          <div className="mt-2 text-xs text-orange-600 bg-orange-50 p-2 rounded">
            ⚠️ Preview truncated to {preview.max_lines} lines
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {preview.preview_type === 'code' && renderCodePreview(preview.content || '', preview.language)}
        {preview.preview_type === 'text' && renderTextPreview(preview.content || '')}
        {preview.preview_type === 'image' && renderImagePreview()}
        {preview.preview_type === 'pdf' && renderPdfPreview()}
        {preview.preview_type === 'binary' && renderBinaryPreview()}
      </div>
    </div>
  );
};

interface FileListProps {
  directoryPath: string;
  onFileSelect?: (path: string) => void;
}

export const FileList: React.FC<FileListProps> = ({
  directoryPath,
  onFileSelect,
}) => {
  const [files, setFiles] = useState<FileMetadata[]>([]);
  const [directories, setDirectories] = useState<FileMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDirectory = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(
          `/api/v1/files/directory/${encodeURIComponent(directoryPath)}`
        );
        if (!response.ok) throw new Error('Failed to fetch directory');

        const data = await response.json();
        setFiles(data.files);
        setDirectories(data.directories);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchDirectory();
  }, [directoryPath]);

  if (loading) {
    return <div className="p-4 text-gray-600">Loading...</div>;
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Directories */}
      {directories.map((dir) => (
        <div
          key={dir.path}
          onClick={() => onFileSelect?.(dir.path)}
          className="p-2 bg-blue-50 rounded cursor-pointer hover:bg-blue-100 flex items-center gap-2"
        >
          <span>📁</span>
          <span className="font-medium text-blue-900">{dir.name}</span>
        </div>
      ))}

      {/* Files */}
      {files.map((file) => (
        <div
          key={file.path}
          onClick={() => onFileSelect?.(file.path)}
          className="p-2 bg-gray-50 rounded cursor-pointer hover:bg-gray-100 flex items-center justify-between"
        >
          <div className="flex items-center gap-2 flex-1">
            <span>📄</span>
            <div className="flex-1">
              <div className="font-medium text-gray-900">{file.name}</div>
              <div className="text-xs text-gray-600">{formatFileSize(file.size)}</div>
            </div>
          </div>
          <div className="text-xs text-gray-500">{file.mime_type}</div>
        </div>
      ))}

      {files.length === 0 && directories.length === 0 && (
        <div className="p-4 text-center text-gray-500">
          No files or directories found
        </div>
      )}
    </div>
  );
};

export default FilePreview;
