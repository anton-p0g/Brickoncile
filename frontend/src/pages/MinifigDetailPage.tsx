import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ChangeFigNumDialog } from "../components/ChangeFigNumDialog";
import { CompletionBar } from "../components/CompletionBar";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { HistoryLog } from "../components/HistoryLog";
import { ImageLightbox } from "../components/ImageLightbox";
import { PartsGrid } from "../components/PartsGrid";
import { ResyncButton } from "../components/ResyncButton";
import { SortingStateButton } from "../components/SortingStateButton";
import { StatusBadge } from "../components/StatusBadge";
import { Toast, type ToastMessage } from "../components/Toast";
import {
  useAdjustMinifigPartFound,
  useChangeMinifigFigNum,
  useDeleteMinifigInstance,
  useMinifigInstance,
  useMinifigInstanceHistory,
  useMinifigInstancePartsFound,
  useResyncMinifigInstance,
  useUpdateMinifigSorting,
  useUpdateMinifigPartCondition,
} from "../hooks/useMinifigs";
import { completionPercent } from "../lib/completion";

/** Handed to whichever minifig page a fig-ID correction lands on, since correcting one usually
 *  moves the figure to a different record than the page it was requested from. */
interface MinifigPageNotice {
  notice?: { tone: ToastMessage["tone"]; text: string };
}

export function MinifigDetailPage() {
  const { instanceId = "" } = useParams<{ instanceId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { data: instance, isLoading, error } = useMinifigInstance(instanceId);
  const deleteInstance = useDeleteMinifigInstance();
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [changingFigNum, setChangingFigNum] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const [imageOpen, setImageOpen] = useState(false);
  const changeFigNum = useChangeMinifigFigNum();
  const adjustFound = useAdjustMinifigPartFound(instanceId);
  const setPartsFound = useMinifigInstancePartsFound(instanceId);
  const updateCondition = useUpdateMinifigPartCondition(instanceId);
  const updateSorting = useUpdateMinifigSorting(instanceId);
  const resync = useResyncMinifigInstance(instanceId);
  const [historyOpen, setHistoryOpen] = useState(false);
  const history = useMinifigInstanceHistory(instanceId, {
    enabled: historyOpen,
  });

  // A correction that moved the figure elsewhere says so on the page it arrived at. Cleared from
  // history straight away, so a reload or a step back does not announce it a second time.
  const notice = (location.state as MinifigPageNotice | null)?.notice;
  useEffect(() => {
    if (!notice) return;
    setToast({ ...notice, id: Date.now() });
    navigate(location.pathname, { replace: true, state: null });
  }, [notice, navigate, location.pathname]);

  if (isLoading) return <p className="p-4 text-sm text-gray-500">Loading...</p>;
  if (error || !instance)
    return <p className="p-4 text-sm text-red-600">Minifig not found.</p>;

  const unaccounted =
    instance.quantity_required_total - instance.quantity_found_total;

  function applyFigNumChange(figNum: string) {
    changeFigNum.mutate(
      { instanceId, figNum },
      {
        onSuccess: (response) => {
          setChangingFigNum(false);
          const target = response.instance;
          if (response.outcome === "unchanged") {
            setToast({ tone: "info", text: `Already filed as ${target.fig_num}; nothing changed.`, id: Date.now() });
            return;
          }
          const text =
            response.outcome === "claimed_by_set"
              ? `${target.fig_name} belongs to set ${response.claimed_set_num}` +
                `${response.claimed_set_name ? ` — ${response.claimed_set_name}` : ""}, and is now checked off there.`
              : `Refiled as ${target.fig_name} (${target.fig_num}). Its parts list was refetched, so sorting starts over.`;
          // The edited record no longer exists; replace it in history so Back does not 404.
          navigate(`/minifigs/${encodeURIComponent(target.instance_id)}`, {
            replace: true,
            state: { notice: { tone: "success", text } } satisfies MinifigPageNotice,
          });
        },
      },
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-start gap-4 p-4 pb-2">
        <div className="h-32 w-24 flex-shrink-0 overflow-hidden rounded bg-gray-100">
          {instance.image_url && (
            <button
              type="button"
              onClick={() => setImageOpen(true)}
              title="Show larger image"
              className="h-full w-full cursor-zoom-in"
            >
              <img
                src={instance.image_url}
                alt={instance.fig_name}
                className="h-full w-full object-contain"
              />
            </button>
          )}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <h1 className="truncate text-lg font-bold">{instance.fig_name}</h1>
          <span className="flex items-center gap-2">
            <span className="font-mono text-sm text-gray-500">
              fig_num {instance.fig_num}
            </span>
            {/* Loose only: a set's roster states which fig its copy is, and a resync would undo
                anything changed here. */}
            {instance.source_set_num === null && (
              <button
                type="button"
                onClick={() => setChangingFigNum(true)}
                title="Refile this minifigure under a different Rebrickable fig ID"
                className="ui-control ui-control-secondary px-1.5 py-0.5 text-xs text-gray-600 hover:text-gray-900"
              >
                Change ID
              </button>
            )}
          </span>
          {instance.source_set_num ? (
            <Link
              to={`/sets/${encodeURIComponent(instance.source_set_num)}`}
              className="ui-control ui-control-secondary ui-control-sm w-fit"
            >
              source: set {instance.source_set_num}
              {instance.source_set_name ? ` — ${instance.source_set_name}` : ""}
            </Link>
          ) : (
            <span className="w-fit rounded-full border border-gray-300 px-2 py-0.5 text-xs text-gray-500">
              loose - no source set
            </span>
          )}
          <span className="flex items-center gap-2">
            <StatusBadge
              status={instance.status}
              missingCount={instance.quantity_missing_total}
            />
            <span className="font-mono text-[11px] text-gray-500">
              {instance.quantity_found_total} of{" "}
              {instance.quantity_required_total} found &middot;{" "}
              {completionPercent(instance)}%
            </span>
          </span>
          <CompletionBar
            entity={instance}
            status={instance.status}
            className="max-w-[12rem]"
          />
        </div>
        <SortingStateButton
          status={instance.status}
          isSorted={instance.sorting_finished_at !== null}
          unaccountedCount={unaccounted}
          isPending={updateSorting.isPending}
          onChange={(finished) => updateSorting.mutate(finished)}
        />
        <ResyncButton
          onClick={() => resync.mutate()}
          isPending={resync.isPending}
        />
      </div>

      <PartsGrid
        parts={instance.parts}
        status={instance.status}
        onMark={(partNum, colorId, foundDelta) =>
          adjustFound.mutate({ partNum, colorId, foundDelta })
        }
        onSetCondition={(partNum, colorId, quantityFound, quantityBroken) =>
          updateCondition.mutate({ partNum, colorId, quantityFound, quantityBroken })
        }
        onSetPartsFound={(targets) => setPartsFound.mutateAsync(targets)}
        isBulkPending={setPartsFound.isPending}
      />

      <HistoryLog
        entries={history.data}
        parts={instance.parts}
        isLoading={history.isLoading}
        isOpen={historyOpen}
        onToggle={() => setHistoryOpen((v) => !v)}
      />

      <div className="flex items-center gap-3 border-t border-gray-200 p-4">
        <Link
          to="/minifigs"
          className="ui-control ui-control-secondary ui-control-md"
        >
          Back to minifigures
        </Link>
        {instance.source_set_num ? (
          <Link
            to={`/sets/${encodeURIComponent(instance.source_set_num)}`}
            className="ui-control ui-control-secondary ui-control-md ml-auto"
          >
            View source set ({instance.source_set_num})
          </Link>
        ) : (
          // Only loose minifigures can go: one from a set would be recreated by the set's resync.
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className="ui-control ui-control-danger ui-control-md ml-auto"
          >
            Delete this minifigure
          </button>
        )}
      </div>

      {changingFigNum && (
        <ChangeFigNumDialog
          currentFigNum={instance.fig_num}
          currentFigName={instance.fig_name}
          error={changeFigNum.error ? changeFigNum.error.message : null}
          isPending={changeFigNum.isPending}
          onSubmit={applyFigNumChange}
          onCancel={() => {
            setChangingFigNum(false);
            changeFigNum.reset();
          }}
        />
      )}

      {imageOpen && instance.image_url && (
        <ImageLightbox
          src={instance.image_url}
          alt={instance.fig_name}
          onClose={() => setImageOpen(false)}
        />
      )}

      {toast && <Toast toast={toast} onDismiss={() => setToast(null)} />}

      {confirmingDelete && (
        <ConfirmDialog
          title="Delete this minifigure?"
          confirmLabel="Delete minifigure"
          isPending={deleteInstance.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() =>
            deleteInstance.mutate(instanceId, {
              onSuccess: () => navigate("/minifigs"),
            })
          }
          body={
            <>
              <p>
                <span className="font-semibold">{instance.fig_name}</span>{" "}
                <span className="font-mono">({instance.fig_num})</span> will be
                removed from your collection, along with its parts list, the
                history of pieces you checked off, and every cached image only
                this minifigure used.
              </p>
              <p className="mt-1.5">
                Identifying it again will refetch from Rebrickable. Your
                progress cannot be recovered.
              </p>
            </>
          }
        />
      )}
    </div>
  );
}
