import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type {
  MinifigMatchOut,
  OwnedInstanceRefOut,
  RecognitionOut,
} from "../api/types";
import { Toast, type ToastMessage } from "../components/Toast";
import {
  minifigsKeys,
  useAddLooseMinifig,
  useIdentifyQueue,
  useMarkMinifigInstanceFound,
  type QueuedPhoto,
} from "../hooks/useMinifigs";

/** Below this the two catalogs barely agreed, so the candidate is a long shot worth flagging. */
const WEAK_MATCH_SCORE = 0.5;

/** Why a photo ended up needing another look. */
type ReviewReason =
  | "unrecognised"
  | "no-catalog-match"
  | "failed"
  | "no-good-match";

const REVIEW_REASON_LABEL: Record<ReviewReason, string> = {
  unrecognised: "Nothing recognised",
  "no-catalog-match": "Recognised, not found in the catalog",
  failed: "Identification failed",
  "no-good-match": "None of the candidates fitted",
};

interface ReviewEntry {
  photo: QueuedPhoto;
  reason: ReviewReason;
  /** What the recogniser thought it saw, which is the clue for finding the figure by hand. */
  recognitions: RecognitionOut[];
}

function percent(score: number): number {
  return Math.round(score * 100);
}

interface CandidateCardProps {
  match: MinifigMatchOut;
  onAddLoose: (match: MinifigMatchOut) => void;
  onClaim: (owned: OwnedInstanceRefOut) => void;
  isPending: boolean;
}

function CandidateCard({
  match,
  onAddLoose,
  onClaim,
  isPending,
}: CandidateCardProps) {
  const owned = match.owned_instances;
  // A set listing this fig but not yet holding it is where the figure in hand most likely belongs,
  // so claiming one of those leads and adding a loose copy steps back to being the fallback.
  const expecting = owned.filter(
    (instance) => !instance.is_complete && instance.source_set_num,
  );
  const accountedFor = owned.filter(
    (instance) => instance.is_complete || !instance.source_set_num,
  );
  // The catalogs word names differently; when they disagree that is the thing to eyeball.
  const namesDiffer =
    match.recognized_as.toLowerCase() !== match.name.toLowerCase();

  return (
    <li className="flex flex-col gap-2 rounded border border-gray-300 bg-white p-3">
      <div className="flex items-start gap-3">
        <div className="h-24 w-24 flex-shrink-0 overflow-hidden rounded bg-gray-100">
          {match.image_url && (
            <img
              src={match.image_url}
              alt={match.name}
              loading="lazy"
              className="h-full w-full object-contain"
            />
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="text-sm font-semibold">{match.name}</div>
          <div className="font-mono text-xs text-gray-500">{match.fig_num}</div>
          {match.num_parts !== null && (
            <div className="font-mono text-[11px] text-gray-400">
              {match.num_parts} parts
            </div>
          )}

          <div className="mt-0.5 flex items-center gap-2">
            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-gray-200">
              <div
                className={`h-full ${match.score >= WEAK_MATCH_SCORE ? "bg-green-600" : "bg-amber-500"}`}
                style={{ width: `${percent(match.score)}%` }}
              />
            </div>
            <span className="font-mono text-[11px] text-gray-500">
              {percent(match.score)}% match
            </span>
          </div>

          {namesDiffer && (
            <div className="text-[11px] text-gray-500">
              recognised as{" "}
              <span className="italic">{match.recognized_as}</span>
            </div>
          )}
        </div>
      </div>

      {expecting.length > 0 && (
        <div className="rounded border border-blue-200 bg-blue-50 p-2">
          <p className="text-xs font-semibold text-blue-900">
            {expecting.length === 1
              ? "A set of yours is still waiting for this one."
              : `${expecting.length} of your set's copies are still waiting for this one.`}
          </p>
          <p className="mt-0.5 text-[11px] text-blue-800">
            Assign it there and its pieces are all marked found.
          </p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {expecting.map((instance) => (
              <li
                key={instance.instance_id}
                className="flex flex-wrap items-center gap-2"
              >
                <button
                  type="button"
                  onClick={() => onClaim(instance)}
                  disabled={isPending}
                  className="ui-control border-blue-600 bg-white px-2.5 py-1 text-xs font-semibold text-blue-800 hover:border-blue-700 hover:bg-blue-100"
                >
                  It is this one - from set {instance.source_set_num}
                </button>
                {instance.source_set_name && (
                  <span className="min-w-0 truncate text-[11px] text-blue-800">
                    {instance.source_set_name}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {accountedFor.length > 0 && (
        <div className="rounded bg-gray-100 px-2 py-1.5 text-xs text-gray-600">
          <span className="font-semibold">Already accounted for:</span>{" "}
          {accountedFor.map((instance, i) => (
            <span key={instance.instance_id}>
              {i > 0 && ", "}
              <Link
                to={`/minifigs/${encodeURIComponent(instance.instance_id)}`}
                className="underline hover:no-underline"
              >
                {instance.source_set_num
                  ? `set ${instance.source_set_num}`
                  : "loose"}
              </Link>
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onAddLoose(match)}
          disabled={isPending}
          className={`ui-control px-2.5 py-1 text-xs font-semibold ${
            expecting.length > 0
              ? "ui-control-secondary text-gray-700"
              : "ui-control-success"
          }`}
        >
          {expecting.length > 0
            ? "It is a spare — add as loose"
            : owned.length > 0
              ? "Add another one"
              : "This is it - add it"}
        </button>
        {match.reference_url && (
          <a
            href={match.reference_url}
            target="_blank"
            rel="noreferrer"
            className="ui-control ui-control-secondary px-2.5 py-1 text-xs"
          >
            Check on BrickLink
          </a>
        )}
      </div>
    </li>
  );
}

/** What the recogniser saw, with a way to look the guess up by hand. */
function RecognitionList({ recognitions }: { recognitions: RecognitionOut[] }) {
  return (
    <ul className="flex flex-col gap-1">
      {recognitions.map((recognition) => (
        <li key={recognition.external_id} className="flex items-center gap-2">
          <span className="font-mono text-xs text-gray-500">
            {recognition.external_id}
          </span>
          <span className="min-w-0 flex-1 truncate text-xs">
            {recognition.name}
          </span>
          {recognition.reference_url && (
            <a
              href={recognition.reference_url}
              target="_blank"
              rel="noreferrer"
              className="shrink-0 text-xs underline hover:no-underline"
            >
              BrickLink
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

interface ReviewPanelProps {
  entries: ReviewEntry[];
  onLookAgain: (entry: ReviewEntry) => void;
  onDismiss: (id: string) => void;
  onClear: () => void;
}

/**
 * The photos that did not end in a minifigure being added, collected in one place.
 *
 * These are the ones worth reshooting, and the photo itself is what says why — too dark, too far
 * away, a busy background. Keeping them on screen means a pile can be worked through in one pass
 * and the failures dealt with afterwards, rather than each one interrupting the run.
 */
function ReviewPanel({
  entries,
  onLookAgain,
  onDismiss,
  onClear,
}: ReviewPanelProps) {
  return (
    <div className="border-t border-gray-200 bg-gray-50 p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-sm font-bold">
          Needs another look ({entries.length})
        </h2>
        <p className="text-xs text-gray-500">
          Nothing was added for these. Retake them against a plain background,
          or open the recogniser's guess on BrickLink to search by hand — then{" "}
          <Link to="/minifigs" className="underline hover:no-underline">
            add it manually
          </Link>{" "}
          by pasting its Rebrickable link.
        </p>
        <button
          type="button"
          onClick={onClear}
          className="ui-control ui-control-secondary ml-auto px-2.5 py-1 text-xs"
        >
          Clear list
        </button>
      </div>

      <ul className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {entries.map((entry) => (
          <li
            key={entry.photo.id}
            className="flex gap-3 rounded border border-gray-300 bg-white p-2.5"
          >
            <div className="h-24 w-24 flex-shrink-0 overflow-hidden rounded bg-gray-100">
              <img
                src={entry.photo.previewUrl}
                alt={entry.photo.file.name}
                className="h-full w-full object-contain"
              />
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="text-xs font-semibold text-amber-700">
                {REVIEW_REASON_LABEL[entry.reason]}
              </span>
              <span className="truncate font-mono text-[11px] text-gray-400">
                {entry.photo.file.name}
              </span>
              {entry.recognitions.length > 0 && (
                <RecognitionList recognitions={entry.recognitions} />
              )}
              <div className="mt-auto flex flex-wrap gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => onLookAgain(entry)}
                  className="ui-control ui-control-secondary px-2.5 py-1 text-xs"
                >
                  Look again
                </button>
                <button
                  type="button"
                  onClick={() => onDismiss(entry.photo.id)}
                  className="ui-control ui-control-secondary px-2.5 py-1 text-xs text-gray-500"
                >
                  Remove
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function IdentifyMinifigPage() {
  const [queue, setQueue] = useState<QueuedPhoto[]>([]);
  const [index, setIndex] = useState(0);
  const [review, setReview] = useState<ReviewEntry[]>([]);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const previewUrls = useRef(new Map<string, string>());

  const queryClient = useQueryClient();
  const results = useIdentifyQueue(queue, index);
  const addLoose = useAddLooseMinifig();
  const markFound = useMarkMinifigInstanceFound();

  const current = queue[index] ?? null;
  const currentResult = results[index];
  const nextResult = results[index + 1];

  // A preview outlives its queue, because a photo sent to the review list is still shown there.
  // Revoke once nothing points at it any more, and everything on the way out.
  useEffect(() => {
    const live = new Set([
      ...queue.map((p) => p.id),
      ...review.map((e) => e.photo.id),
    ]);
    for (const [id, url] of previewUrls.current) {
      if (!live.has(id)) {
        URL.revokeObjectURL(url);
        previewUrls.current.delete(id);
      }
    }
  }, [queue, review]);

  useEffect(() => {
    const urls = previewUrls.current;
    return () => {
      for (const url of urls.values()) URL.revokeObjectURL(url);
      urls.clear();
    };
  }, []);

  const showToast = useCallback((tone: ToastMessage["tone"], text: string) => {
    setToast({ tone, text, id: Date.now() });
  }, []);

  function clearInputs() {
    // Clearing lets the same file be picked again straight after finishing with it.
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (cameraInputRef.current) cameraInputRef.current.value = "";
  }

  function acceptFiles(files: FileList | null) {
    const chosen = Array.from(files ?? []);
    if (chosen.length === 0) return;
    const photos = chosen.map((file) => {
      const id = crypto.randomUUID();
      const previewUrl = URL.createObjectURL(file);
      previewUrls.current.set(id, previewUrl);
      return { id, file, previewUrl };
    });
    setQueue(photos);
    setIndex(0);
  }

  /** Why the photo on screen would go to the review list if it were left now. */
  function currentReason(): ReviewReason {
    if (currentResult?.isError) return "failed";
    const data = currentResult?.data;
    if (data && data.matches.length === 0) {
      return data.recognitions.length > 0 ? "no-catalog-match" : "unrecognised";
    }
    return "no-good-match";
  }

  function advance(options: { added: boolean }) {
    const photo = queue[index];
    if (photo) {
      const reason = currentReason();
      const recognitions = currentResult?.data?.recognitions ?? [];
      setReview((entries) => {
        const others = entries.filter((entry) => entry.photo.id !== photo.id);
        return options.added
          ? others
          : [...others, { photo, reason, recognitions }];
      });
    }

    if (index + 1 < queue.length) {
      setIndex(index + 1);
      return;
    }
    setQueue([]);
    setIndex(0);
    clearInputs();
  }

  function handleAddLoose(match: MinifigMatchOut) {
    addLoose.mutate(match.fig_num, {
      onSuccess: (instance) => {
        showToast(
          "success",
          `Added ${instance.fig_name} as a loose minifigure.`,
        );
        advance({ added: true });
      },
      onError: (error: Error) => showToast("error", error.message),
    });
  }

  /** Account for the figure as the copy an owned set was already expecting. */
  function handleClaim(owned: OwnedInstanceRefOut) {
    markFound.mutate(owned.instance_id, {
      onSuccess: (instance) => {
        showToast(
          "success",
          `${instance.fig_name} marked found in set ${instance.source_set_num}.`,
        );
        advance({ added: true });
      },
      onError: (error: Error) => showToast("error", error.message),
    });
  }

  /** Send a reviewed photo back through identification with a clean slate. */
  function handleLookAgain(entry: ReviewEntry) {
    queryClient.removeQueries({
      queryKey: [...minifigsKeys.identify, entry.photo.id],
    });
    setQueue([entry.photo]);
    setIndex(0);
    clearInputs();
  }

  const matches = currentResult?.data?.matches ?? [];
  const recognitions = currentResult?.data?.recognitions ?? [];
  const remaining = queue.length - index - 1;
  // Matches arrive ranked, so the leader is the first one.
  const bestScore = matches.length > 0 ? matches[0].score : 0;

  return (
    <div>
      <div className="border-b border-gray-200 bg-gray-50 p-4">
        <h1 className="text-lg font-bold">Identify a minifigure</h1>
        <p className="mt-0.5 text-sm text-gray-600">
          Photograph a minifigure to find out what it is.
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={(e) => acceptFiles(e.target.files)}
            className="hidden"
            id="minifig-photo-input"
          />
          <label
            htmlFor="minifig-photo-input"
            className="ui-control ui-control-primary ui-control-md cursor-pointer font-semibold"
          >
            Choose photos
          </label>

          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => acceptFiles(e.target.files)}
            className="hidden"
            id="minifig-camera-input"
          />
          {/* On a phone this opens the camera directly; on a desktop it is another file picker. */}
          <label
            htmlFor="minifig-camera-input"
            className="ui-control ui-control-secondary ui-control-md cursor-pointer"
          >
            Take a photo
          </label>

          {queue.length > 1 && (
            <span className="font-mono text-xs text-gray-500">
              photo {index + 1} of {queue.length}
            </span>
          )}
          {currentResult?.isLoading && (
            <span className="text-xs text-gray-400">Identifying...</span>
          )}
          {/* Says the wait for the next photo is already being paid, so moving on lands instantly. */}
          {nextResult?.isSuccess && (
            <span className="text-xs text-green-700">next photo ready</span>
          )}
          {nextResult?.isLoading && (
            <span className="text-xs text-gray-400">
              preparing the next one...
            </span>
          )}
        </div>
      </div>

      {!current ? (
        <div className="p-4 text-sm text-gray-500">
          <p>
            No photo yet. A plain background and the whole figure in frame give
            the best result.
          </p>
          <p className="mt-2">Pick several at once to work through a pile.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4 p-4 lg:flex-row">
          <div className="lg:w-64 lg:shrink-0">
            <div className="sticky top-3 flex flex-col gap-2">
              <div className="aspect-square w-full overflow-hidden rounded border border-gray-300 bg-white">
                <img
                  src={current.previewUrl}
                  alt="Minifigure to identify"
                  className="h-full w-full object-contain"
                />
              </div>
              <div className="truncate font-mono text-[11px] text-gray-400">
                {current.file.name}
              </div>
              <button
                type="button"
                onClick={() => advance({ added: false })}
                className="ui-control ui-control-secondary ui-control-md"
              >
                {remaining > 0
                  ? `Skip - ${remaining} photo${remaining === 1 ? "" : "s"} left`
                  : "Done with this photo"}
              </button>
              <p className="text-[11px] text-gray-400">
                Skipped photos are kept below, so you can come back and retake
                them.
              </p>
            </div>
          </div>

          <div className="min-w-0 flex-1">
            {currentResult?.isLoading ? (
              <p className="text-sm text-gray-500">Looking this one up...</p>
            ) : currentResult?.isError ? (
              <div className="rounded border border-red-300 bg-red-50 p-3 text-sm">
                <p className="font-semibold text-red-800">
                  Could not identify that photo.
                </p>
                <p className="mt-1 text-gray-700">
                  {currentResult.error.message}
                </p>
                <button
                  type="button"
                  onClick={() => currentResult.refetch()}
                  className="ui-control ui-control-secondary mt-2 px-2.5 py-1 text-xs"
                >
                  Try again
                </button>
              </div>
            ) : currentResult?.isSuccess && matches.length === 0 ? (
              recognitions.length > 0 ? (
                <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">
                  <p className="font-semibold">
                    Recognised, but not found in the catalog.
                  </p>
                  <p className="mt-1 text-gray-700">
                    The two databases name minifigures differently, and this one
                    did not line up. Opening it on BrickLink usually names the
                    figure well enough to find it by hand.
                  </p>
                  <div className="mt-2">
                    <RecognitionList recognitions={recognitions} />
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  Nothing recognised in that photo. A closer shot against a
                  plain background usually helps.
                </p>
              )
            ) : (
              <>
                <p className="mb-2 text-sm text-gray-600">
                  Compare each candidate against your photo and pick the one
                  that matches.
                  {bestScore < WEAK_MATCH_SCORE &&
                    " None of these scored well, so check them carefully."}
                </p>
                <ul className="flex flex-col gap-3">
                  {matches.map((match) => (
                    <CandidateCard
                      key={match.fig_num}
                      match={match}
                      onAddLoose={handleAddLoose}
                      onClaim={handleClaim}
                      isPending={addLoose.isPending || markFound.isPending}
                    />
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      )}

      {review.length > 0 && (
        <ReviewPanel
          entries={review}
          onLookAgain={handleLookAgain}
          onDismiss={(id) =>
            setReview((entries) => entries.filter((e) => e.photo.id !== id))
          }
          onClear={() => setReview([])}
        />
      )}

      {toast && <Toast toast={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
