You are the sole worker for one scientific single-panel curve-reconstruction task.

Perform axis anchoring and curve extraction in this single Codex session. The
input PNG is already exactly one target panel, so panel routing and panel
selection are outside this benchmark. The same PNG is attached to the prompt
and available at `image_path`.

Evidence boundary:

- Inspect only the supplied PNG and task context.
- Do not search the repository, other benchmark cases, prior responses, answer
  keys, raw curve tables, benchmark HTML, or evaluation outputs.
- Do not infer scientific values or hidden curve segments that are not visible.
- You may use Python and only the two deterministic utilities supplied below.
- Do not read or modify the utility source unless a direct command fails.

Required workflow:

1. Inspect the entire supplied panel before placing anchors or points.
2. Locate the main plotting rectangle.
3. Read reliable visible x- and y-axis ticks and determine whether each axis is
   linear or log10.
4. Run the axis-fit utility on the draft anchors. If it rejects a mapping,
   recheck concrete anchor mistakes once; otherwise report the ambiguity.
5. Identify every target data curve in the main plot and map identities from
   the legend, color, line style, markers, conditions, and local ordering.
6. Build a structured x-column tracing grid and sample each visible curve in
   cropped-panel pixel coordinates.
7. Run the overlap QA utility. Keep the draft deliberately or revise failed
   curves once, then rerun the utility at most once.
8. Return one schema-compliant combined JSON object.

Axis anchoring rules:

- The supplied image is already the complete target panel. Set
  `crop_box_original` to `[0, 0, image_width, image_height]` and copy the image
  to `saved_panel_image_path`.
- Define `plot_area_box_cropped` around the actual data plotting rectangle,
  excluding tick labels and legends but preserving the image itself unchanged.
- Distinguish axis labels and tick labels from panel labels, legends, and plot
  annotations.
- Record anchors at visible tick positions in `cropped_panel` coordinates.
- Do not infer absent tick values or fabricate precision. Put uncertainty in
  the anchor note and lower its confidence.
- Use at least two reliable anchors per axis and more when visible.
- Test linear and log10 only when visually plausible. If neither is supported
  after one recheck, choose `unknown`, mark the axis unusable or ambiguous, and
  require manual review.
- Treat the axis-fit utility as a validator, not as a source of anchors.

Axis-fit check:

1. Write `axis_fit_input_path` as a JSON object containing `panel_id` and one
   combined `anchor_points` array.
2. Run exactly:
   `python_executable fit_axis_script_path --input axis_fit_input_path --output axis_fit_output_path`
3. Read the report and use it to finalize both axis records.
4. Prefer one fit pass. Rerun once only after finding a concrete anchor error.

Curve identity and tracing rules:

- Trace only target data curves in the main plot. Do not trace axes, frame
  lines, grid lines, legend glyphs, annotations, arrows, or inset curves.
- Keep every sampled point within `plot_area_box_cropped`, normally about 2 px
  inside the frame rather than on the spine itself.
- Preserve curve identity strictly. Never move points to a clearer neighboring
  curve merely to improve overlap.
- Use visible legend labels where available. If labels describe conditions,
  retain the condition labels. Describe color, style, and markers simply.
- Use color plus local ordering across the plot. A real crossover may change
  ordering; an unsupported jump to a neighboring parallel curve is an error.
- In layered overlap, trace the top/front-most visible stroke first. Resume a
  lower curve only where it is visibly separable again, and record the gap.
- If a curve becomes inseparable, retain its visible segment and mark it
  `partial`, `ambiguous`, or unusable rather than inventing continuity.

Point-placement rules:

- Build ordered x-columns across the plot area, normally spaced about 10 to 25
  px apart. Sample more densely at knees, peaks, shoulders, crossings, sharp
  bends, and crowded regions.
- At each useful column, place the point on the visible stroke centerline.
- For marker-bearing curves, use marker centers or the connector centerline,
  not the marker rim. For hollow markers, infer centers from ring symmetry and
  repeated marker centroids.
- If a marker touches a border, estimate its center from the visible portion;
  do not collapse the curve onto the frame.
- Keep points ordered by increasing pixel x. For most ordinary traces, about
  30 to 60 points per curve is appropriate, but visible shape and image width
  determine the final count.
- Do not leave large unsupported gaps when the stroke is visible. Prefer blank
  columns and a documented partial segment when it is not visible.
- For LSV or polarization curves, continue through the steep knee into the
  long near-horizontal tail near zero current whenever it remains visibly
  separable. Do not stop at the knee simply because the tail is crowded.
- If a complete curve has a visibly separable tail, its points should span that
  visible extent. If not, mark the curve partial.

Overlap QA check:

1. Write `curve_candidate_path` using the same final curve objects that will
   appear in the combined response.
2. Run exactly:
   `python_executable overlap_scorer_path --panel-image saved_panel_image_path --response curve_candidate_path --output overlap_report_path --overlay-output overlap_overlay_path`
3. Read the panel summary, per-curve point hit rate, median and p95 distances,
   border-lock or marker-center warnings, and pairwise ambiguity results.
4. Target `point_hit_rate >= 0.85`, `median_distance_px <= 2.5`, and
   `p95_distance_px <= 5` while preserving the correct identities.
5. If an important curve fails, a marker curve rides a rim/frame, or a pair is
   ambiguously duplicated, correct only the concrete failed segments once and
   rerun the scorer once.
6. If genuine crowding remains, prefer a conservative partial extraction over
   two mislabeled full-length traces. Keep the stronger visible curve and
   truncate or disable only the weaker one when appropriate.

Quality priority:

1. Correct axis mapping.
2. Correct curve count and identity.
3. Points centered on visible evidence.
4. Adequate visible-extent coverage.

Task:

- paper_id: [PAPER_ID]
- figure_id: [FIGURE_ID]
- panel_id: [PANEL_ID]
- panel_label: [PANEL_LABEL]
- image_path: [IMAGE_PATH]
- figure_caption: [FIGURE_CAPTION]
- caption_snippet: [CAPTION_SNIPPET]
- candidate_catalysts: [CANDIDATE_CATALYSTS]
- special_notes: [SPECIAL_NOTES]

Output paths:

- saved_panel_image_path: [SAVED_PANEL_IMAGE_PATH]
- saved_curve_overlay_path: [SAVED_CURVE_OVERLAY_PATH]
- axis_fit_input_path: [AXIS_FIT_INPUT_PATH]
- axis_fit_output_path: [AXIS_FIT_OUTPUT_PATH]
- curve_candidate_path: [CURVE_CANDIDATE_PATH]
- overlap_report_path: [OVERLAP_REPORT_PATH]
- overlap_overlay_path: [OVERLAP_OVERLAY_PATH]

Utilities:

- python_executable: [PYTHON_EXECUTABLE]
- fit_axis_script_path: [FIT_AXIS_SCRIPT_PATH]
- overlap_scorer_path: [OVERLAP_SCORER_PATH]

The candidate JSON for overlap QA must contain:

- paper_id, figure_id, panel_id, and panel_label;
- saved_panel_image_path and saved_curve_overlay_path;
- plot_area_box_cropped, x_axis_type, and y_axis_type;
- legend_entries and panel_type;
- overlap_recovery_recommended and overlap_recovery_reason;
- the same final `curves` objects returned in the combined result;
- interpretation_notes, qc, and unresolved_ambiguities.

Return only the final combined JSON object. Do not add prose outside the JSON.
