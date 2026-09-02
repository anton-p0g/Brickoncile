/**
 * Where an inventory sits in the sorting workflow.
 * - not_started: nothing confirmed present yet
 * - sorting: part-way through checking the pile
 * - sorted: sorting declared finished, so unfound pieces are confirmed missing
 * - complete: every required piece is confirmed present
 */
export type SortingStatus = "not_started" | "sorting" | "sorted" | "complete";

export interface CollectionOut {
  id: string;
  name: string;
  created_at: string;
  is_default: boolean;
}

export interface PartOut {
  part_num: string;
  color_id: number;
  color_name: string;
  part_name: string;
  element_id: string | null;
  image_url: string | null;
  quantity_required: number;
  /** Pieces confirmed physically present. The tracked value; missing is derived from it. */
  quantity_found: number;
  /** required - found. Reads as "missing" only once the owner finished sorting. */
  quantity_unaccounted: number;
  is_fully_found: boolean;
  is_spare: boolean;
}

export interface SetSummary {
  set_num: string;
  name: string;
  year: number | null;
  image_url: string | null;
  num_parts: number;
  /** Sum of quantity_required over non-spare parts. The denominator for % complete — unlike
   *  num_parts, which is upstream metadata that can disagree with the cached parts list. */
  quantity_required_total: number;
  quantity_found_total: number;
  /** Confirmed missing: zero until sorting is finished, since unfound pieces may still be in the pile. */
  quantity_missing_total: number;
  is_complete: boolean;
  status: SortingStatus;
  sorting_finished_at: string | null;
  /** When the set entered the collection, ISO 8601. Preserved across resyncs. */
  added_at: string;
  /** The set's own theme, often a sub-theme such as "Constraction". */
  theme_id: number | null;
  theme_name: string | null;
  /** The top of that theme's tree ("Legends of Chima"), which is how a collection is grouped.
   *  Null when the theme tree has not been cached yet, or the set has no theme upstream. */
  root_theme_id: number | null;
  root_theme_name: string | null;
}

export interface SetDetail extends SetSummary {
  last_synced_at: string;
  parts: PartOut[];
}

export interface EntityTotals {
  quantity_required_total: number;
  quantity_found_total: number;
  quantity_missing_total: number;
  is_complete: boolean;
  status: SortingStatus;
}

export interface MarkSetPartResponse {
  part: PartOut;
  set_summary: EntityTotals;
}

/** One part's target found count for a bulk write. Absolute, not a delta, so the same shape both
 *  confirms a screenful of parts and restores the previous counts to undo it. */
export interface PartFoundTarget {
  part_num: string;
  color_id: number;
  quantity_found: number;
}

export interface SetPartsFoundResponse {
  /** Only the parts that actually changed. */
  parts: PartOut[];
  summary: EntityTotals;
}

export interface PartSourceOut {
  source_type: "set" | "minifig_instance";
  source_id: string;
  label: string;
  quantity_required: number;
  quantity_found: number;
  quantity_unaccounted: number;
  status: SortingStatus;
}

export interface PartSearchResultOut {
  part_num: string;
  color_id: number;
  color_name: string;
  part_name: string;
  element_id: string | null;
  image_url: string | null;
  /** Summed across sources. Zero means every inventory holding this part is already satisfied. */
  total_needed: number;
  sources: PartSourceOut[];
}

export interface BulkAddResultItem {
  /** The resolved set number actually stored: a bare "70202" comes back as "70202-1". */
  set_num: string;
  /** What was typed, so a failure can be traced back to the line that caused it. */
  input_set_num: string;
  /** "partial": the set and its parts landed but its minifigures did not, so it IS in the
   *  collection — reporting it as a failure would send you looking for a set that is already there. */
  status: "ok" | "exists" | "partial" | "error";
  /** Null for a set that failed, since nothing was fetched to name it. */
  name: string | null;
  error: string | null;
}

export interface BulkAddSetsResponse {
  results: BulkAddResultItem[];
}

export interface AddSetResponse {
  /** "exists" when the set was already owned, so a re-add reads as such instead of a silent no-op. */
  status: "ok" | "exists";
  set: SetDetail;
  /** Set when the add succeeded with something missing (currently only its minifigures). Not an
   *  error: the set is in the collection either way. */
  warning: string | null;
}

export interface HistoryEntryOut {
  part_num: string;
  color_id: number;
  action: string;
  quantity_before: number;
  quantity_after: number;
  timestamp: string;
}

export interface MinifigInstanceSummary {
  instance_id: string;
  fig_num: string;
  fig_name: string;
  image_url: string | null;
  /** Null for a loose minifig — identified from a photo, with no owned set to attribute it to. */
  source_set_num: string | null;
  source_set_name: string | null;
  quantity_required_total: number;
  quantity_found_total: number;
  quantity_missing_total: number;
  is_complete: boolean;
  status: SortingStatus;
  sorting_finished_at: string | null;
  /** When this instance entered the collection, ISO 8601, inherited from its source set. */
  added_at: string;
}

export interface MinifigInstanceDetail extends MinifigInstanceSummary {
  parts: PartOut[];
}

export interface AddMinifigByReferenceResponse {
  instance: MinifigInstanceDetail;
  /** Copies owned before this one — non-zero means a deliberate duplicate, or a list pasted twice. */
  already_owned_count: number;
}

export interface BulkAddMinifigResultItem {
  /** Echoed verbatim, so a failed line can be matched back and put in the box to correct. */
  input_reference: string;
  status: "ok" | "error";
  fig_num: string | null;
  fig_name: string | null;
  instance_id: string | null;
  already_owned_count: number;
  error: string | null;
}

export interface BulkAddMinifigsResponse {
  results: BulkAddMinifigResultItem[];
}

/**
 * How a fig-num correction resolved.
 * - `unchanged`: the id was already right and nothing was waiting for it; the record is untouched.
 * - `replaced`: refiled under the new entry, as a new instance with the new parts list.
 * - `claimed_by_set`: an owned set was still expecting this figure, so its copy was confirmed
 *   found and the loose one removed.
 */
export type ChangeMinifigFigNumOutcome = "unchanged" | "replaced" | "claimed_by_set";

export interface ChangeMinifigFigNumResponse {
  outcome: ChangeMinifigFigNumOutcome;
  /** Where the figure lives now — a different instance than the one edited unless "unchanged". */
  instance: MinifigInstanceDetail;
  previous_instance_id: string;
  claimed_set_num: string | null;
  claimed_set_name: string | null;
}

export interface MarkMinifigPartResponse {
  part: PartOut;
  instance_summary: EntityTotals;
}

export interface ContributorOut {
  source_type: "set" | "minifig_instance";
  source_id: string;
  /** Single line, for the CSV and clipboard exports. The UI lays out name and reference instead. */
  label: string;
  /** The set's or figure's own name. */
  name: string;
  /** The catalog id worth showing: a set number, or a fig number. Not source_id, which for a
   *  minifig is an internal instance id. */
  reference: string;
  image_url: string | null;
  quantity: number;
}

export interface PartAggregateOut {
  part_num: string;
  color_id: number;
  part_name: string;
  color_name: string;
  image_url: string | null;
  total_missing: number;
  contributors: ContributorOut[];
}

export interface SourceItemOut {
  part_num: string;
  color_id: number;
  part_name: string;
  color_name: string;
  image_url: string | null;
  quantity_missing: number;
}

export interface SourceAggregateOut {
  source_type: "set" | "minifig_instance";
  source_id: string;
  label: string;
  name: string;
  /** See ContributorOut.reference. */
  reference: string;
  image_url: string | null;
  items: SourceItemOut[];
  total_missing: number;
}

export type GroupBy = "part" | "set";

/** An instance of an identified minifig that is already tracked. */
export interface OwnedInstanceRefOut {
  instance_id: string;
  source_set_num: string | null;
  source_set_name: string | null;
  /** Whether this copy is already accounted for. Sets can list the same fig more than once, so
   *  this is what says which copy a photographed figure should be matched to. */
  is_complete: boolean;
  quantity_found_total: number;
  quantity_required_total: number;
}

/**
 * A catalog entry that might be the photographed minifig.
 *
 * The recogniser and the catalog are two different databases that name the same figure
 * differently, so a match is a suggestion to confirm by eye, never an identity. `name` is what
 * Rebrickable calls it and `recognized_as` is what the recogniser did — when those disagree,
 * that disagreement is the thing worth looking at.
 */
export interface MinifigMatchOut {
  fig_num: string;
  name: string;
  num_parts: number | null;
  /** Remote catalog image; nothing is cached locally until the match is confirmed. */
  image_url: string | null;
  /** Blended recogniser confidence and name similarity, 0-1. Ordering only — not a probability. */
  score: number;
  recognized_as: string;
  recognition_image_url: string | null;
  /** BrickLink page for the recogniser's guess, for settling an uncertain match by hand. */
  reference_url: string | null;
  /** Non-empty when this minifig is already in the collection. */
  owned_instances: OwnedInstanceRefOut[];
}

export interface RecognitionOut {
  external_id: string;
  name: string;
  score: number;
  image_url: string | null;
  reference_url: string | null;
}

export interface IdentifyMinifigResponse {
  /** Everything the recogniser saw, kept even when nothing resolved to a catalog entry. */
  recognitions: RecognitionOut[];
  matches: MinifigMatchOut[];
}

// ---- Dashboard statistics ----

export interface StatsTotals {
  sets: number;
  minifig_instances: number;
  quantity_required: number;
  quantity_found: number;
  /** Confirmed missing across finished inventories only. */
  quantity_missing: number;
  distinct_parts: number;
  distinct_colors: number;
}

export interface StatusCount {
  status: SortingStatus;
  sets: number;
  minifig_instances: number;
}

export interface SetProgress {
  set_num: string;
  name: string;
  year: number | null;
  image_url: string | null;
  num_parts: number;
  quantity_required: number;
  quantity_found: number;
  quantity_missing: number;
  status: SortingStatus;
  root_theme_name: string | null;
}

export interface ThemeStats {
  /** Null for sets with no theme upstream, or whose theme is not cached yet. */
  theme_name: string | null;
  sets: number;
  quantity_required: number;
  quantity_found: number;
  quantity_missing: number;
}

export interface ColorStats {
  color_id: number;
  color_name: string;
  quantity_required: number;
  quantity_found: number;
  distinct_parts: number;
}

export interface CommonPartOut {
  part_num: string;
  color_id: number;
  part_name: string;
  color_name: string;
  image_url: string | null;
  /** How many owned sets call for this part/colour. */
  set_count: number;
  quantity_required: number;
}

export interface MissingPartStatOut {
  part_num: string;
  color_id: number;
  part_name: string;
  color_name: string;
  image_url: string | null;
  total_missing: number;
  /** How many sets and minifigs are short of it. */
  source_count: number;
}

export interface BurnUpPoint {
  timestamp: string;
  quantity_found: number;
}

export interface BurnUp {
  /** Bucket width the curve was sampled at; the axis labels follow it. */
  granularity: "hour" | "day";
  points: BurnUpPoint[];
}

export interface HourBucket {
  hour: number;
  events: number;
  pieces: number;
}

export interface DayBucket {
  day: string;
  events: number;
  pieces: number;
}

export interface SessionStats {
  count: number;
  total_minutes: number;
  longest_minutes: number;
  pieces_per_session: number;
  pieces_per_hour: number;
}

export interface YearBucket {
  year: number | null;
  sets: number;
  quantity_required: number;
}

export interface DuplicatedFigOut {
  fig_num: string;
  fig_name: string;
  image_url: string | null;
  count: number;
}

export interface MinifigStatsOut {
  total: number;
  loose: number;
  from_set: number;
  distinct_figs: number;
  complete: number;
  most_duplicated: DuplicatedFigOut[];
}

export interface CollectionStatsOut {
  totals: StatsTotals;
  status_breakdown: StatusCount[];
  sets: SetProgress[];
  themes: ThemeStats[];
  colors: ColorStats[];
  common_parts: CommonPartOut[];
  top_missing: MissingPartStatOut[];
  burn_up: BurnUp;
  activity_by_hour: HourBucket[];
  activity_by_day: DayBucket[];
  sessions: SessionStats;
  years: YearBucket[];
  minifigs: MinifigStatsOut;
}
