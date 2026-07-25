import { useRef, useState } from "react";
import { apiUpload, API_ORIGIN } from "../api/client";
import { UploadIcon } from "./ui/Icon";

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
      let next = media;
      for (const file of Array.from(files)) {
        const ref = await apiUpload<MediaRef>("/media/upload", file);
        next = [...next, ref];
        onChange(next);
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
        className={`group cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center
          transition-all duration-200 ${
            dragOver
              ? "scale-[1.01] border-brand-500 bg-brand-50"
              : "border-slate-300 hover:border-brand-400 hover:bg-brand-50/40"
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
        <span
          className={`mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl
            bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-glow
            transition-transform duration-300 group-hover:scale-110 ${uploading ? "animate-pulse" : ""}`}
        >
          <UploadIcon className="h-5 w-5" />
        </span>
        <p className="text-sm font-semibold text-slate-700">
          {uploading ? "Uploading…" : "Drop a photo, audio, or video here"}
        </p>
        <p className="mt-1 text-xs text-slate-400">or click to browse — up to 50MB per file</p>
      </div>

      {error && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {media.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {media.map((item, i) => (
            <div
              key={item.id}
              className="group relative overflow-hidden rounded-xl bg-white p-2 shadow-card
                ring-1 ring-slate-900/[0.06] transition-all duration-200 hover:shadow-lift"
            >
              <button
                type="button"
                onClick={() => removeAt(i)}
                aria-label="Remove media"
                className="absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-full
                  bg-slate-900/70 text-xs text-white opacity-0 backdrop-blur transition-opacity
                  duration-200 hover:bg-status-critical group-hover:opacity-100"
              >
                ✕
              </button>
              <MediaPreview item={item} />
              <p className="mt-1.5 truncate text-[11px] font-medium uppercase tracking-wide text-slate-400">
                {item.kind}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MediaPreview({ item }: { item: MediaRef }) {
  const src = `${API_ORIGIN}${item.url}`;
  if (item.kind === "image")
    return <img src={src} alt="" className="h-28 w-full rounded-lg object-cover" />;
  if (item.kind === "audio")
    return (
      <div className="flex h-28 items-center rounded-lg bg-slate-50 px-2">
        <audio src={src} controls className="w-full" />
      </div>
    );
  return <video src={src} controls className="h-28 w-full rounded-lg bg-slate-900 object-cover" />;
}
