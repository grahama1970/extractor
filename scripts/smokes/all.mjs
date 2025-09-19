import { spawn } from 'node:child_process';

const stepsBase = [
  { cmd: ['node', 'scripts/smokes/llm_health.mjs'], name: 'llm_health' },
  { cmd: ['node', 'scripts/smokes/console_errors.mjs'], name: 'console_errors' },
    { cmd: ['node', 'scripts/smokes/api_tabbed_basic.mjs'], name: 'api_tabbed_basic' },
  { cmd: ['node', 'scripts/smokes/api_coco_export.mjs'], name: 'api_coco_export' },
  { cmd: ['node', 'scripts/smokes/api_suggest_tables.mjs'], name: 'api_suggest_tables' },
  { cmd: ['node', 'scripts/smokes/api_pipeline_job.mjs'], name: 'api_pipeline_job' },
  { cmd: ['node', 'scripts/ux_check_cdp_auto.mjs'], name: 'ux_check_cdp_auto' },
  { cmd: ['node', 'scripts/smokes/tabbed_preload.mjs'], name: 'tabbed_preload' },
  { cmd: ['node', 'scripts/smokes/tabbed_suggest_tables_ui.mjs'], name: 'tabbed_suggest_tables_ui' },
  { cmd: ['node', 'scripts/smokes/tabbed_autoload_bht.mjs'], name: 'tabbed_autoload_bht' },
  { cmd: ['node', 'scripts/smokes/tabbed_crisp_toolbar.mjs'], name: 'tabbed_crisp_toolbar' },
  { cmd: ['node', 'scripts/smokes/tabbed_zoom_tooltip.mjs'], name: 'tabbed_zoom_tooltip' },
  { cmd: ['node', 'scripts/smokes/tabbed_thumbnails_left.mjs'], name: 'tabbed_thumbnails_left' },
  { cmd: ['node', 'scripts/smokes/tabbed_thumbnails_bottom.mjs'], name: 'tabbed_thumbnails_bottom' },
  { cmd: ['node', 'scripts/smokes/tooltips_text.mjs'], name: 'tooltips_text' },
  { cmd: ['node', 'scripts/smokes/tooltips_controls.mjs'], name: 'tooltips_controls' },
  { cmd: ['node', 'scripts/smokes/tooltips_hud_actions.mjs'], name: 'tooltips_hud_actions' },
  { cmd: ['node', 'scripts/smokes/tooltips_types.mjs'], name: 'tooltips_types' },
  { cmd: ['node', 'scripts/smokes/delete_keypress.mjs'], name: 'delete_keypress' },
  { cmd: ['node', 'scripts/smokes/add_annotation_button.mjs'], name: 'add_annotation_button' },
  { cmd: ['node', 'scripts/smokes/add_annotation_top_menu.mjs'], name: 'add_annotation_top_menu' },
  { cmd: ['node', 'scripts/smokes/tabbed_bottom_single_row.mjs'], name: 'tabbed_bottom_single_row' },
  { cmd: ['node', 'scripts/smokes/tabbed_generate_json_mock.mjs'], name: 'tabbed_generate_json_mock' },
  { cmd: ['node', 'scripts/smokes/toolbar_hierarchy.mjs'], name: 'toolbar_hierarchy' },
  { cmd: ['node', 'scripts/smokes/left_export_controls.mjs'], name: 'left_export_controls' },
  { cmd: ['node', 'scripts/smokes/resizable_panes.mjs'], name: 'resizable_panes' },
  { cmd: ['node', 'scripts/smokes/resize_keyboard.mjs'], name: 'resize_keyboard' },
  { cmd: ['node', 'scripts/smokes/resize_keyboard_right_persist.mjs'], name: 'resize_keyboard_right_persist' },
  { cmd: ['node', 'scripts/smokes/a11y_focus_basic.mjs'], name: 'a11y_focus_basic' },
  { cmd: ['node', 'scripts/smokes/anno_list_virtualized.mjs'], name: 'anno_list_virtualized' },
  // New UI smokes (Happy-Path minimal)
  { cmd: ['node', 'scripts/smokes/ui_grouping_export_json.mjs'], name: 'ui_grouping_export_json' },
  { cmd: ['node', 'scripts/smokes/ui_export_json_fields.mjs'], name: 'ui_export_json_fields' },
  { cmd: ['node', 'scripts/smokes/ui_progress_pipeline_run.mjs'], name: 'ui_progress_pipeline_run' },
  { cmd: ['node', 'scripts/smokes/ui_load_pipeline_annos_from_latest.mjs'], name: 'ui_load_pipeline_annos_from_latest' },
  { cmd: ['node', 'scripts/smokes/ui_keyboard_core.mjs'], name: 'ui_keyboard_core' },
  { cmd: ['node', 'scripts/smokes/ui_search_highlight_thumb.mjs'], name: 'ui_search_highlight_thumb' },
  { cmd: ['node', 'scripts/smokes/ui_conflicts_load_and_resolve.mjs'], name: 'ui_conflicts_load_and_resolve' },
  // New UX slices (kept at end; safe to run; comments panel skips if missing)
  { cmd: ['node', 'scripts/smokes/ui_zoom_fit_pan.mjs'], name: 'ui_zoom_fit_pan' },
  { cmd: ['node', 'scripts/smokes/ui_selection_handles_resize.mjs'], name: 'ui_selection_handles_resize' },
  { cmd: ['node', 'scripts/smokes/ui_thumbnails_virtualized.mjs'], name: 'ui_thumbnails_virtualized' },
  { cmd: ['node', 'scripts/smokes/ui_a11y_focus_escape.mjs'], name: 'ui_a11y_focus_escape' },
  { cmd: ['node', 'scripts/smokes/ui_comments_threads_panel.mjs'], name: 'ui_comments_threads_panel' },
  { cmd: ['node', 'scripts/smokes/issue_013.mjs'], name: 'issue_013' },
  { cmd: ['node', 'scripts/smokes/issue_014.mjs'], name: 'issue_014' },
  { cmd: ['node', 'scripts/smokes/issue_018.mjs'], name: 'issue_018' },
  { cmd: ['node', 'scripts/smokes/issue_019.mjs'], name: 'issue_019' },
  { cmd: ['node', 'scripts/smokes/issue_020.mjs'], name: 'issue_020' },
];

// Optional: real backend generate-json flow (opt-in)
const GENERATE_REAL = (process.env.GENERATE_REAL || '').toLowerCase();
if (GENERATE_REAL === '1' || GENERATE_REAL === 'true' || GENERATE_REAL === 'yes') {
  stepsBase.push({ cmd: ['node', 'scripts/smokes/generate_json_flow.mjs'], name: 'generate_json_flow' });
}
// Optional: direct Gemini 256x256 acompletion smoke (Python)
if (GENERATE_REAL === '1' || GENERATE_REAL === 'true' || GENERATE_REAL === 'yes') {
  stepsBase.push({ cmd: ['python', 'scripts/smokes/gemini_256_acompletion.py'], name: 'gemini_256_acompletion' });
}



// Optional: button-like litellm_call smoke (crop + schema)
if (GENERATE_REAL === '1' || GENERATE_REAL === 'true' || GENERATE_REAL === 'yes') {
  stepsBase.push({ cmd: ['python', 'scripts/smokes/generate_json_button_like.py'], name: 'generate_json_button_like' });
}

// Optional: Camelot vs LLM (PDF-backed crop + schema)
if (GENERATE_REAL === '1' || GENERATE_REAL === 'true' || GENERATE_REAL === 'yes') {
  stepsBase.push({ cmd: ['python', 'scripts/smokes/generate_json_vs_camelot.py'], name: 'generate_json_vs_camelot' });
}


const FAST = (process.env.SMOKES_FAST || '').toLowerCase() === '1' || (process.env.SMOKES_FAST || '').toLowerCase() === 'true';
const steps = FAST
  ? stepsBase.filter(s => !['llm_health'].includes(s.name))
  : stepsBase;

function runStep(i) {
  if (i >= steps.length) return Promise.resolve(0);
  const { cmd, name } = steps[i];
  return new Promise((resolve) => {
    console.log(`\n--- SMOKE ${i+1}/${steps.length}: ${name} ---`);
    const cp = spawn(cmd[0], cmd.slice(1), { stdio: 'inherit', env: process.env });
    cp.on('exit', (code) => {
      if (code) {
        console.error(`Smoke failed: ${name} (code ${code})`);
        resolve(code);
      } else {
        runStep(i + 1).then(resolve);
      }
    });
  });
}

runStep(0).then((code) => process.exit(code ?? 0));
