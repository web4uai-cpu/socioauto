import { useRef, useState } from "react";
import { apiUpload, API_ORIGIN } from "../api/client";

export interface MediaRef {
  id: string;
  url: string;
  content_type: string;
  kind: "image" | "audio" | "video";
}

interface MediaUploaderProps {
  media: MediaRef[];
  onChange: (media: MediaRef[]) => void;
}

/** Drag-and-drop uploader for a post's images/audio/video, backed by POST /media/upload. */
export function MediaUploader({ media, onChange }: MediaUploaderProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        const ref = await apiUpload<MediaRef>("/media/upload", file);
        onChange([...media, ref]);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  function removeAt(index: number) {
    onChange(media.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center text-sm transition-colors ${
          dragOver ? "border-brand-500 bg-brand-50" : "border-gray-300 text-gray-500 hover:bg-gray-50"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*,audio/*,video/*"
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
        {uploading ? "Uploading…" : "Drag & drop photo, audio, or video — or click to browse"}
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {media.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {media.map((item, i) => (
            <div key={item.id} className="relative rounded-lg border border-gray-200 p-2">
              <button
                type="button"
                onClick={() => removeAt(i)}
                aria-label="Remove media"
                className="absolute right-1 top-1 z-10 rounded-full bg-white/90 px-1.5 text-xs text-gray-600 shadow"
              >
                ✕
              </button>
              <MediaPreview item={item} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MediaPreview({ item }: { item: MediaRef }) {
  const src = `${API_ORIGIN}${item.url}`;
  if (item.kind === "image") return <img src={src} alt="" className="h-24 w-full rounded object-cover" />;
  if (item.kind === "audio") return <audio src={src} controls className="w-full" />;
  return <video src={src} controls className="h-24 w-full rounded object-cover" />;
}
