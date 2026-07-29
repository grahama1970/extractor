#!/usr/bin/env python3
"""
Seed a D3 gallery with one sample HTML visualization per chart type.

Generates 23 self-contained HTML files (dark theme, 5ft canvas friendly)
and accompanying metadata JSON files. Uses the figure-lab chart_generators
where available, falls back to inline D3 code for types without dedicated
generators.

Usage:
    python scripts/seed_d3_gallery.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

# ---------------------------------------------------------------------------
# Output directories
# ---------------------------------------------------------------------------
GALLERY_ROOT = Path("/mnt/storage12tb/artifacts/d3_gallery")
WORKING_DIR = GALLERY_ROOT / "working"
METADATA_DIR = GALLERY_ROOT / "metadata"

D3_CDN = "https://cdn.jsdelivr.net/npm/d3@7/+esm"
CANVAS_BG = "#111"
CANVAS_FG = "#e2e8f0"
FONT_SIZE = 18
STROKE_WIDTH = 2
ANIMATION_MS = 800

# ---------------------------------------------------------------------------
# Try to import figure-lab generators for the types that have them.
# If unavailable, we generate everything inline (no hard dependency).
# ---------------------------------------------------------------------------
_FIGURE_LAB_GENERATORS: dict = {}

try:
    sys.path.insert(
        0,
        str(
            Path(
                os.environ.get(
                    "FIGURE_LAB_ROOT",
                    Path.home() / "workspace/experiments/pi-mono/.pi/skills/figure-lab",
                )
            )
        ),
    )
    from figure_lab.chart_generators import (
        gen_area,
        gen_bar_fallback,
        gen_beeswarm,
        gen_box_plot,
        gen_bubble,
        gen_funnel,
        gen_gauge,
        gen_grouped_bar,
        gen_hbar,
        gen_heatmap,
        gen_histogram,
        gen_radar,
        gen_ridgeline,
        gen_stacked_area,
        gen_stacked_bar,
        gen_waterfall,
    )

    _FIGURE_LAB_GENERATORS = {
        "bar": gen_bar_fallback,
        "hbar": gen_hbar,
        "stacked_bar": gen_stacked_bar,
        "grouped_bar": gen_grouped_bar,
        "area": gen_area,
        "stacked_area": gen_stacked_area,
        "radar": gen_radar,
        "bubble": gen_bubble,
        "heatmap": gen_heatmap,
        "histogram": gen_histogram,
        "box_plot": gen_box_plot,
        "waterfall": gen_waterfall,
        "funnel": gen_funnel,
        "ridgeline": gen_ridgeline,
        "beeswarm": gen_beeswarm,
        "gauge": gen_gauge,
    }
    print(f"[OK] Imported {len(_FIGURE_LAB_GENERATORS)} figure-lab generators")
except ImportError as exc:
    print(f"[WARN] Could not import figure-lab generators: {exc}")
    print("       All charts will be generated with inline D3 code.")

# ---------------------------------------------------------------------------
# Sample data for each chart type
# ---------------------------------------------------------------------------
SAMPLE_DATA: dict[str, list[dict]] = {
    "bar": [
        {"label": "Category A", "value": 42},
        {"label": "Category B", "value": 28},
        {"label": "Category C", "value": 65},
        {"label": "Category D", "value": 18},
        {"label": "Category E", "value": 51},
    ],
    "hbar": [
        {"label": "Requirement", "value": 85},
        {"label": "Design", "value": 62},
        {"label": "Implementation", "value": 95},
        {"label": "Verification", "value": 73},
        {"label": "Validation", "value": 48},
    ],
    "stacked_bar": [
        {"label": "Q1", "hardware": 30, "software": 45, "services": 20},
        {"label": "Q2", "hardware": 25, "software": 55, "services": 30},
        {"label": "Q3", "hardware": 35, "software": 50, "services": 25},
        {"label": "Q4", "hardware": 40, "software": 60, "services": 35},
    ],
    "grouped_bar": [
        {"label": "Jan", "actual": 42, "target": 50, "forecast": 48},
        {"label": "Feb", "actual": 55, "target": 50, "forecast": 52},
        {"label": "Mar", "actual": 48, "target": 55, "forecast": 53},
        {"label": "Apr", "actual": 62, "target": 55, "forecast": 58},
    ],
    "diverging_bar": [
        {"label": "Feature A", "value": 35},
        {"label": "Feature B", "value": -12},
        {"label": "Feature C", "value": 22},
        {"label": "Feature D", "value": -28},
        {"label": "Feature E", "value": 45},
        {"label": "Feature F", "value": -8},
    ],
    "line": [
        {"label": "Jan", "value": 10},
        {"label": "Feb", "value": 25},
        {"label": "Mar", "value": 18},
        {"label": "Apr", "value": 32},
        {"label": "May", "value": 28},
        {"label": "Jun", "value": 45},
    ],
    "multi_line": [
        {"label": "Jan", "series_a": 10, "series_b": 30, "series_c": 20},
        {"label": "Feb", "series_a": 25, "series_b": 28, "series_c": 22},
        {"label": "Mar", "series_a": 18, "series_b": 35, "series_c": 30},
        {"label": "Apr", "series_a": 32, "series_b": 22, "series_c": 38},
        {"label": "May", "series_a": 28, "series_b": 40, "series_c": 35},
        {"label": "Jun", "series_a": 45, "series_b": 38, "series_c": 42},
    ],
    "slope": [
        {"label": "Metric A", "start": 30, "end": 55},
        {"label": "Metric B", "start": 60, "end": 45},
        {"label": "Metric C", "start": 25, "end": 70},
        {"label": "Metric D", "start": 50, "end": 35},
    ],
    "area": [
        {"label": "Jan", "value": 10},
        {"label": "Feb", "value": 25},
        {"label": "Mar", "value": 18},
        {"label": "Apr", "value": 32},
        {"label": "May", "value": 28},
        {"label": "Jun", "value": 45},
    ],
    "stacked_area": [
        {"label": "Jan", "desktop": 40, "mobile": 20, "tablet": 10},
        {"label": "Feb", "desktop": 38, "mobile": 25, "tablet": 12},
        {"label": "Mar", "desktop": 42, "mobile": 30, "tablet": 15},
        {"label": "Apr", "desktop": 35, "mobile": 35, "tablet": 18},
        {"label": "May", "desktop": 33, "mobile": 40, "tablet": 20},
        {"label": "Jun", "desktop": 30, "mobile": 45, "tablet": 22},
    ],
    "waterfall": [
        {"label": "Revenue", "value": 120},
        {"label": "COGS", "value": -45},
        {"label": "Gross Profit", "value": 0},
        {"label": "OpEx", "value": -30},
        {"label": "Tax", "value": -12},
        {"label": "Net Income", "value": 0},
    ],
    "pie": [
        {"label": "Section A", "value": 30},
        {"label": "Section B", "value": 20},
        {"label": "Section C", "value": 25},
        {"label": "Section D", "value": 15},
        {"label": "Section E", "value": 10},
    ],
    "donut": [
        {"label": "Passed", "value": 340},
        {"label": "Warned", "value": 14},
        {"label": "Failed", "value": 2},
    ],
    "scatter": [
        {"label": "Point 1", "x": 5.2, "value": 8.1},
        {"label": "Point 2", "x": 12.4, "value": 3.7},
        {"label": "Point 3", "x": 8.8, "value": 11.2},
        {"label": "Point 4", "x": 3.1, "value": 6.9},
        {"label": "Point 5", "x": 15.6, "value": 9.5},
        {"label": "Point 6", "x": 7.3, "value": 14.0},
        {"label": "Point 7", "x": 10.1, "value": 5.3},
    ],
    "bubble": [
        {"label": "Alpha", "x": 10, "y": 20, "size": 30},
        {"label": "Beta", "x": 25, "y": 35, "size": 50},
        {"label": "Gamma", "x": 40, "y": 15, "size": 20},
        {"label": "Delta", "x": 55, "y": 45, "size": 70},
        {"label": "Epsilon", "x": 30, "y": 60, "size": 40},
    ],
    "histogram": [
        {"value": v}
        for v in [
            12, 15, 18, 20, 22, 22, 25, 25, 25, 28, 28, 30, 30, 30, 30,
            32, 32, 35, 35, 38, 40, 42, 45, 48, 50, 55, 60, 62, 65, 70,
            72, 75, 78, 80, 82, 85, 88, 90, 92, 95,
        ]
    ],
    "box_plot": [
        *[{"label": "Group A", "value": v} for v in [12, 18, 22, 25, 28, 30, 35, 40, 45, 50]],
        *[{"label": "Group B", "value": v} for v in [20, 25, 30, 32, 35, 38, 42, 48, 55, 60]],
        *[{"label": "Group C", "value": v} for v in [5, 10, 15, 18, 22, 28, 32, 38, 42, 48]],
    ],
    "gauge": [
        {"label": "Pipeline Quality", "value": 94.5, "max": 100},
    ],
    "funnel": [
        {"label": "Corpus", "value": 12117},
        {"label": "Extracted", "value": 9800},
        {"label": "Scored", "value": 8200},
        {"label": "Passed", "value": 7400},
        {"label": "Ingested", "value": 6900},
    ],
    "dot_plot": [
        {"label": "DO-178C", "value": 0.92},
        {"label": "MIL-STD", "value": 0.88},
        {"label": "NASA", "value": 0.95},
        {"label": "FAA", "value": 0.85},
        {"label": "RTCA", "value": 0.90},
    ],
    "sparkline": [
        {"value": v}
        for v in [10, 15, 12, 18, 22, 20, 25, 30, 28, 35, 32, 40]
    ],
    "table": [
        {"label": "Content Coverage", "value": "0.94", "grade": "A"},
        {"label": "Table Fidelity", "value": "0.88", "grade": "B+"},
        {"label": "Section Alignment", "value": "0.96", "grade": "A+"},
        {"label": "Data Quality", "value": "0.91", "grade": "A"},
    ],
    "text": [
        {"label": "Pipeline Status", "value": "Operational"},
        {"label": "Total Documents", "value": "12,117"},
        {"label": "Pass Rate", "value": "95.4%"},
    ],
}

# Map each chart type to a viz_family and sample query for metadata
CHART_META: dict[str, dict] = {
    "bar":           {"viz_family": "bar",         "sample_query": "Show category totals as a bar chart"},
    "hbar":          {"viz_family": "bar",         "sample_query": "Show horizontal comparison of metrics"},
    "stacked_bar":   {"viz_family": "bar",         "sample_query": "Show quarterly revenue by segment"},
    "grouped_bar":   {"viz_family": "bar",         "sample_query": "Compare actual vs target by month"},
    "diverging_bar": {"viz_family": "bar",         "sample_query": "Show positive and negative feature scores"},
    "line":          {"viz_family": "line",        "sample_query": "Show monthly trend over time"},
    "multi_line":    {"viz_family": "line",        "sample_query": "Compare three series over time"},
    "slope":         {"viz_family": "line",        "sample_query": "Show before-and-after comparison"},
    "area":          {"viz_family": "area",        "sample_query": "Show cumulative trend with area fill"},
    "stacked_area":  {"viz_family": "area",        "sample_query": "Show device traffic breakdown over time"},
    "waterfall":     {"viz_family": "bar",         "sample_query": "Show income statement waterfall"},
    "pie":           {"viz_family": "proportion",  "sample_query": "Show distribution of sections"},
    "donut":         {"viz_family": "proportion",  "sample_query": "Show pass/warn/fail distribution"},
    "scatter":       {"viz_family": "correlation", "sample_query": "Show relationship between two variables"},
    "bubble":        {"viz_family": "correlation", "sample_query": "Show three-dimensional data comparison"},
    "histogram":     {"viz_family": "distribution","sample_query": "Show score frequency distribution"},
    "box_plot":      {"viz_family": "distribution","sample_query": "Show quartile comparison across groups"},
    "gauge":         {"viz_family": "kpi",         "sample_query": "Show pipeline quality score"},
    "funnel":        {"viz_family": "flow",        "sample_query": "Show document processing funnel"},
    "dot_plot":      {"viz_family": "distribution","sample_query": "Show compliance scores by standard"},
    "sparkline":     {"viz_family": "line",        "sample_query": "Show compact inline trend"},
    "table":         {"viz_family": "tabular",     "sample_query": "Show quality metrics summary table"},
    "text":          {"viz_family": "text",        "sample_query": "Show key pipeline statistics"},
}

# Friendly titles
CHART_TITLES: dict[str, str] = {
    "bar":           "Category Comparison",
    "hbar":          "Horizontal Metrics",
    "stacked_bar":   "Revenue by Segment",
    "grouped_bar":   "Actual vs Target",
    "diverging_bar": "Feature Score Divergence",
    "line":          "Monthly Trend",
    "multi_line":    "Multi-Series Trend",
    "slope":         "Before and After",
    "area":          "Cumulative Growth",
    "stacked_area":  "Device Traffic Breakdown",
    "waterfall":     "Income Statement",
    "pie":           "Section Distribution",
    "donut":         "Extraction Verdicts",
    "scatter":       "Variable Correlation",
    "bubble":        "Multi-Dimension Comparison",
    "histogram":     "Score Distribution",
    "box_plot":      "Quartile Comparison",
    "gauge":         "Pipeline Quality",
    "funnel":        "Processing Funnel",
    "dot_plot":      "Compliance Scores",
    "sparkline":     "Inline Trend",
    "table":         "Quality Metrics",
    "text":          "Pipeline Status",
}


# ---------------------------------------------------------------------------
# Inline D3 generators for chart types WITHOUT figure-lab generators
# ---------------------------------------------------------------------------

def _gen_line(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate a JavaScript line for rendering a chart with D3.js."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const width = rect.width || 800;
const height = rect.height || 500;
const margin = {{top: 40, right: 24, bottom: 60, left: 64}};

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{width}} ${{height}}`);

const x = d3.scalePoint()
  .domain(data.map(d => d.label || d.name || String(d.x)))
  .range([margin.left, width - margin.right])
  .padding(0.5);

const y = d3.scaleLinear()
  .domain([0, d3.max(data, d => d.value || d.y || 0)])
  .nice()
  .range([height - margin.bottom, margin.top]);

const line = d3.line()
  .x(d => x(d.label || d.name || String(d.x)))
  .y(d => y(d.value || d.y || 0))
  .curve(d3.curveMonotoneX);

const path = svg.append('path').datum(data)
  .attr('fill', 'none').attr('stroke', '#60a5fa')
  .attr('stroke-width', {sw + 1}).attr('d', line);

const totalLength = path.node()?.getTotalLength() || 0;
path.attr('stroke-dasharray', `${{totalLength}} ${{totalLength}}`)
  .attr('stroke-dashoffset', totalLength)
  .transition().duration({anim}).ease(d3.easeCubicOut)
  .attr('stroke-dashoffset', 0);

svg.selectAll('circle').data(data).join('circle')
  .attr('cx', d => x(d.label || d.name || String(d.x)))
  .attr('cy', d => y(d.value || d.y || 0))
  .attr('r', 5).attr('fill', '#60a5fa');

svg.append('g').attr('transform', `translate(0,${{height - margin.bottom}})`)
  .call(d3.axisBottom(x).tickSizeOuter(0))
  .selectAll('text').attr('font-size', '{fs}px');

svg.append('g').attr('transform', `translate(${{margin.left}},0)`)
  .call(d3.axisLeft(y).ticks(5))
  .selectAll('text').attr('font-size', '{fs}px');

svg.selectAll('.domain, .tick line')
  .attr('stroke', 'currentColor').attr('stroke-opacity', 0.3);
"""


def _gen_multi_line(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate multi-line JavaScript code for a D3 chart configuration."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const width = rect.width || 800;
const height = rect.height || 500;
const margin = {{top: 40, right: 120, bottom: 60, left: 64}};

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{width}} ${{height}}`);

const keys = Object.keys(data[0]).filter(k => k !== 'label' && k !== 'name' && k !== 'x');
const x = d3.scalePoint()
  .domain(data.map(d => d.label || d.name || String(d.x)))
  .range([margin.left, width - margin.right])
  .padding(0.5);

const y = d3.scaleLinear()
  .domain([0, d3.max(data, d => d3.max(keys, k => d[k]))])
  .nice()
  .range([height - margin.bottom, margin.top]);

const color = d3.scaleOrdinal(d3.schemeTableau10).domain(keys);

keys.forEach(key => {{
  const line = d3.line()
    .x(d => x(d.label || d.name || String(d.x)))
    .y(d => y(d[key]))
    .curve(d3.curveMonotoneX);

  const path = svg.append('path').datum(data)
    .attr('fill', 'none').attr('stroke', color(key))
    .attr('stroke-width', {sw + 1}).attr('d', line);

  const totalLength = path.node()?.getTotalLength() || 0;
  path.attr('stroke-dasharray', `${{totalLength}} ${{totalLength}}`)
    .attr('stroke-dashoffset', totalLength)
    .transition().duration({anim}).ease(d3.easeCubicOut)
    .attr('stroke-dashoffset', 0);
}});

// Legend
const legend = svg.append('g').attr('transform', `translate(${{width - margin.right + 12}}, ${{margin.top}})`);
keys.forEach((k, i) => {{
  const g = legend.append('g').attr('transform', `translate(0,${{i * 28}})`);
  g.append('line').attr('x1', 0).attr('x2', 20).attr('y1', 8).attr('y2', 8)
    .attr('stroke', color(k)).attr('stroke-width', {sw + 1});
  g.append('text').attr('x', 26).attr('y', 13).text(k)
    .attr('font-size', '14px').attr('fill', '{CANVAS_FG}');
}});

svg.append('g').attr('transform', `translate(0,${{height - margin.bottom}})`)
  .call(d3.axisBottom(x).tickSizeOuter(0))
  .selectAll('text').attr('font-size', '{fs}px');

svg.append('g').attr('transform', `translate(${{margin.left}},0)`)
  .call(d3.axisLeft(y).ticks(5))
  .selectAll('text').attr('font-size', '{fs}px');

svg.selectAll('.domain, .tick line')
  .attr('stroke', 'currentColor').attr('stroke-opacity', 0.3);
"""


def _gen_slope(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate D3.js slope chart JavaScript code."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const width = rect.width || 800;
const height = rect.height || 500;
const margin = {{top: 40, right: 140, bottom: 40, left: 140}};

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{width}} ${{height}}`);

const allVals = data.flatMap(d => [d.start, d.end]);
const y = d3.scaleLinear()
  .domain([d3.min(allVals) * 0.8, d3.max(allVals) * 1.1])
  .range([height - margin.bottom, margin.top]);

const xLeft = margin.left;
const xRight = width - margin.right;
const colors = d3.scaleOrdinal(d3.schemeTableau10);

// Column headers
svg.append('text').attr('x', xLeft).attr('y', margin.top - 12)
  .attr('text-anchor', 'middle').attr('font-size', '{fs}px')
  .attr('fill', '#94a3b8').attr('font-weight', '600').text('Before');
svg.append('text').attr('x', xRight).attr('y', margin.top - 12)
  .attr('text-anchor', 'middle').attr('font-size', '{fs}px')
  .attr('fill', '#94a3b8').attr('font-weight', '600').text('After');

data.forEach((d, i) => {{
  // Slope line
  svg.append('line')
    .attr('x1', xLeft).attr('y1', y(d.start))
    .attr('x2', xLeft).attr('y2', y(d.start))
    .attr('stroke', colors(i)).attr('stroke-width', {sw + 1})
    .transition().duration({anim}).ease(d3.easeCubicOut)
    .attr('x2', xRight).attr('y2', y(d.end));

  // Left dot + label
  svg.append('circle').attr('cx', xLeft).attr('cy', y(d.start))
    .attr('r', 5).attr('fill', colors(i));
  svg.append('text').attr('x', xLeft - 10).attr('y', y(d.start) + 5)
    .attr('text-anchor', 'end').attr('font-size', '14px').attr('fill', '{CANVAS_FG}')
    .text(`${{d.label}} (${{d.start}})`);

  // Right dot + label
  svg.append('circle').attr('cx', xRight).attr('cy', y(d.end))
    .attr('r', 5).attr('fill', colors(i));
  svg.append('text').attr('x', xRight + 10).attr('y', y(d.end) + 5)
    .attr('text-anchor', 'start').attr('font-size', '14px').attr('fill', '{CANVAS_FG}')
    .text(`${{d.label}} (${{d.end}})`);
}});
"""


def _gen_diverging_bar(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate a diverging bar chart as an SVG string."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const width = rect.width || 800;
const height = rect.height || 500;
const margin = {{top: 40, right: 24, bottom: 60, left: 100}};

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{width}} ${{height}}`);

const y = d3.scaleBand()
  .domain(data.map(d => d.label || d.name))
  .range([margin.top, height - margin.bottom])
  .padding(0.3);

const maxAbs = d3.max(data, d => Math.abs(d.value || 0));
const x = d3.scaleLinear()
  .domain([-maxAbs, maxAbs]).nice()
  .range([margin.left, width - margin.right]);

svg.selectAll('rect').data(data).join('rect')
  .attr('y', d => y(d.label || d.name))
  .attr('height', y.bandwidth())
  .attr('x', d => d.value >= 0 ? x(0) : x(d.value))
  .attr('width', 0)
  .attr('rx', 4)
  .attr('fill', d => d.value >= 0 ? '#22c55e' : '#ef4444')
  .attr('opacity', 0.85)
  .transition().duration({anim}).ease(d3.easeCubicOut)
  .attr('width', d => Math.abs(x(d.value) - x(0)));

// Center line
svg.append('line')
  .attr('x1', x(0)).attr('x2', x(0))
  .attr('y1', margin.top).attr('y2', height - margin.bottom)
  .attr('stroke', '#94a3b8').attr('stroke-width', 1);

svg.append('g').attr('transform', `translate(${{margin.left}},0)`)
  .call(d3.axisLeft(y).tickSizeOuter(0))
  .selectAll('text').attr('font-size', '{fs}px');

svg.append('g').attr('transform', `translate(0,${{height - margin.bottom}})`)
  .call(d3.axisBottom(x).ticks(7))
  .selectAll('text').attr('font-size', '{fs}px');

svg.selectAll('.domain, .tick line')
  .attr('stroke', 'currentColor').attr('stroke-opacity', 0.3);
"""


def _gen_pie(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate a pie chart SVG from JSON data with specified dimensions and animation."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const size = Math.min(rect.width || 600, rect.height || 600);

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{size}} ${{size}}`);

const g = svg.append('g').attr('transform', `translate(${{size/2}},${{size/2}})`);
const radius = size * 0.4;

const pie = d3.pie().value(d => d.value || d.y || 0).sort(null);
const arc = d3.arc().innerRadius(0).outerRadius(radius);
const colors = d3.scaleOrdinal(d3.schemeTableau10);

const arcs = g.selectAll('path').data(pie(data)).join('path')
  .attr('fill', (d, i) => colors(i))
  .attr('stroke', '{CANVAS_BG}').attr('stroke-width', 2)
  .each(function(d) {{ this._current = {{startAngle: d.startAngle, endAngle: d.startAngle}}; }});

arcs.transition().duration({anim}).ease(d3.easeCubicOut)
  .attrTween('d', function(d) {{
    const interp = d3.interpolate(this._current, d);
    this._current = interp(1);
    return t => arc(interp(t));
  }});

// Labels
const labelArc = d3.arc().innerRadius(radius * 0.65).outerRadius(radius * 0.65);
g.selectAll('text').data(pie(data)).join('text')
  .attr('transform', d => `translate(${{labelArc.centroid(d)}})`)
  .attr('text-anchor', 'middle')
  .attr('font-size', '{fs}px')
  .attr('fill', 'white')
  .attr('font-weight', '600')
  .text(d => d.data.label);
"""


def _gen_donut(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate JavaScript for a D3 donut chart."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const size = Math.min(rect.width || 600, rect.height || 600);

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{size}} ${{size}}`);

const g = svg.append('g').attr('transform', `translate(${{size/2}},${{size/2}})`);
const radius = size * 0.4;

const pie = d3.pie().value(d => d.value || d.y || 0).sort(null);
const arc = d3.arc().innerRadius(radius * 0.55).outerRadius(radius);
const colors = d3.scaleOrdinal(['#22c55e', '#eab308', '#ef4444', '#60a5fa', '#a78bfa']);

const arcs = g.selectAll('path').data(pie(data)).join('path')
  .attr('fill', (d, i) => colors(i))
  .attr('stroke', '{CANVAS_BG}').attr('stroke-width', 2)
  .each(function(d) {{ this._current = {{startAngle: d.startAngle, endAngle: d.startAngle}}; }});

arcs.transition().duration({anim}).ease(d3.easeCubicOut)
  .attrTween('d', function(d) {{
    const interp = d3.interpolate(this._current, d);
    this._current = interp(1);
    return t => arc(interp(t));
  }});

// Center total
const total = data.reduce((s, d) => s + (d.value || 0), 0);
g.append('text').attr('text-anchor', 'middle').attr('y', -8)
  .attr('font-size', `${{size * 0.08}}px`).attr('font-weight', '700')
  .attr('fill', '{CANVAS_FG}').text(total);
g.append('text').attr('text-anchor', 'middle').attr('y', size * 0.04)
  .attr('font-size', '{fs}px').attr('fill', '#94a3b8').text('Total');

// Legend below
const legend = svg.append('g').attr('transform', `translate(${{size * 0.15}}, ${{size * 0.88}})`);
data.forEach((d, i) => {{
  const lg = legend.append('g').attr('transform', `translate(${{i * (size * 0.22)}}, 0)`);
  lg.append('rect').attr('width', 14).attr('height', 14).attr('fill', colors(i)).attr('rx', 3);
  lg.append('text').attr('x', 20).attr('y', 12).text(`${{d.label}} (${{d.value}})`)
    .attr('font-size', '14px').attr('fill', '{CANVAS_FG}');
}});
"""


def _gen_scatter(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate D3.js scatter plot JavaScript code."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const width = rect.width || 800;
const height = rect.height || 500;
const margin = {{top: 40, right: 24, bottom: 60, left: 64}};

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{width}} ${{height}}`);

const x = d3.scaleLinear()
  .domain(d3.extent(data, d => d.x || 0)).nice()
  .range([margin.left, width - margin.right]);

const y = d3.scaleLinear()
  .domain(d3.extent(data, d => d.value || d.y || 0)).nice()
  .range([height - margin.bottom, margin.top]);

const colors = d3.scaleOrdinal(d3.schemeTableau10);

svg.selectAll('circle').data(data).join('circle')
  .attr('cx', d => x(d.x || 0))
  .attr('cy', d => y(d.value || d.y || 0))
  .attr('r', 0)
  .attr('fill', (d, i) => colors(i))
  .attr('fill-opacity', 0.8)
  .attr('stroke', (d, i) => colors(i))
  .attr('stroke-width', 1.5)
  .transition().duration({anim}).ease(d3.easeCubicOut)
  .attr('r', 8);

// Labels
svg.selectAll('text.label').data(data).join('text')
  .attr('class', 'label')
  .attr('x', d => x(d.x || 0) + 12)
  .attr('y', d => y(d.value || d.y || 0) + 4)
  .attr('font-size', '13px').attr('fill', '#94a3b8')
  .text(d => d.label);

svg.append('g').attr('transform', `translate(0,${{height - margin.bottom}})`)
  .call(d3.axisBottom(x).ticks(6))
  .selectAll('text').attr('font-size', '{fs}px');

svg.append('g').attr('transform', `translate(${{margin.left}},0)`)
  .call(d3.axisLeft(y).ticks(5))
  .selectAll('text').attr('font-size', '{fs}px');

svg.selectAll('.domain, .tick line')
  .attr('stroke', 'currentColor').attr('stroke-opacity', 0.3);
"""


def _gen_dot_plot(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate a dot plot visualization using provided data and dimensions."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const width = rect.width || 800;
const height = rect.height || 500;
const margin = {{top: 40, right: 60, bottom: 60, left: 120}};

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{width}} ${{height}}`);

const y = d3.scaleBand()
  .domain(data.map(d => d.label || d.name))
  .range([margin.top, height - margin.bottom])
  .padding(0.5);

const x = d3.scaleLinear()
  .domain([0, d3.max(data, d => d.value || d.y || 0) * 1.1])
  .range([margin.left, width - margin.right]);

const colors = d3.scaleOrdinal(d3.schemeTableau10);

// Horizontal reference lines
svg.selectAll('line.ref').data(data).join('line')
  .attr('class', 'ref')
  .attr('x1', margin.left).attr('x2', width - margin.right)
  .attr('y1', d => y(d.label || d.name) + y.bandwidth() / 2)
  .attr('y2', d => y(d.label || d.name) + y.bandwidth() / 2)
  .attr('stroke', '#334155').attr('stroke-width', 1).attr('stroke-dasharray', '4,4');

// Dots
svg.selectAll('circle').data(data).join('circle')
  .attr('cx', margin.left)
  .attr('cy', d => y(d.label || d.name) + y.bandwidth() / 2)
  .attr('r', 0)
  .attr('fill', (d, i) => colors(i))
  .transition().duration({anim}).ease(d3.easeCubicOut)
  .attr('cx', d => x(d.value || d.y || 0))
  .attr('r', 10);

// Value labels
svg.selectAll('text.val').data(data).join('text')
  .attr('class', 'val')
  .attr('x', d => x(d.value || d.y || 0) + 16)
  .attr('y', d => y(d.label || d.name) + y.bandwidth() / 2 + 5)
  .attr('font-size', '14px').attr('fill', '{CANVAS_FG}')
  .text(d => (d.value || d.y || 0).toFixed(2));

svg.append('g').attr('transform', `translate(${{margin.left}},0)`)
  .call(d3.axisLeft(y).tickSizeOuter(0))
  .selectAll('text').attr('font-size', '{fs}px');

svg.append('g').attr('transform', `translate(0,${{height - margin.bottom}})`)
  .call(d3.axisBottom(x).ticks(5))
  .selectAll('text').attr('font-size', '{fs}px');

svg.selectAll('.domain, .tick line')
  .attr('stroke', 'currentColor').attr('stroke-opacity', 0.3);
"""


def _gen_sparkline(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate an SVG sparkline chart from provided JSON data."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
const rect = container.getBoundingClientRect();
const width = rect.width || 800;
const height = rect.height || 200;

const svg = d3.select('#chart').append('svg')
  .attr('viewBox', `0 0 ${{width}} ${{height}}`);

const margin = {{top: 20, right: 40, bottom: 20, left: 40}};

const x = d3.scaleLinear()
  .domain([0, data.length - 1])
  .range([margin.left, width - margin.right]);

const y = d3.scaleLinear()
  .domain(d3.extent(data, d => d.value || d.y || 0))
  .range([height - margin.bottom, margin.top]);

const line = d3.line()
  .x((d, i) => x(i))
  .y(d => y(d.value || d.y || 0))
  .curve(d3.curveMonotoneX);

const area = d3.area()
  .x((d, i) => x(i))
  .y0(height - margin.bottom)
  .y1(d => y(d.value || d.y || 0))
  .curve(d3.curveMonotoneX);

svg.append('path').datum(data)
  .attr('fill', '#60a5fa').attr('fill-opacity', 0.15)
  .attr('d', area);

const path = svg.append('path').datum(data)
  .attr('fill', 'none').attr('stroke', '#60a5fa')
  .attr('stroke-width', {sw + 1}).attr('d', line);

const totalLength = path.node()?.getTotalLength() || 0;
path.attr('stroke-dasharray', `${{totalLength}} ${{totalLength}}`)
  .attr('stroke-dashoffset', totalLength)
  .transition().duration({anim}).ease(d3.easeCubicOut)
  .attr('stroke-dashoffset', 0);

// End dot
const last = data[data.length - 1];
svg.append('circle')
  .attr('cx', x(data.length - 1))
  .attr('cy', y(last.value || last.y || 0))
  .attr('r', 6).attr('fill', '#60a5fa');

// End value label
svg.append('text')
  .attr('x', x(data.length - 1) + 12)
  .attr('y', y(last.value || last.y || 0) + 5)
  .attr('font-size', '{fs}px').attr('fill', '{CANVAS_FG}')
  .attr('font-weight', '700')
  .text(last.value || last.y || 0);
"""


def _gen_table(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate an HTML table from JSON data with specified font size and styling."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');

const table = document.createElement('table');
table.style.cssText = 'width:80%;margin:40px auto;border-collapse:collapse;font-size:{fs}px;color:{CANVAS_FG}';

// Header
const keys = Object.keys(data[0]);
const thead = table.createTHead();
const hrow = thead.insertRow();
keys.forEach(k => {{
  const th = document.createElement('th');
  th.textContent = k.charAt(0).toUpperCase() + k.slice(1);
  th.style.cssText = 'padding:12px 20px;text-align:left;border-bottom:2px solid #334155;font-weight:700;text-transform:uppercase;letter-spacing:1px;font-size:14px;color:#94a3b8';
  hrow.appendChild(th);
}});

// Rows
const tbody = table.createTBody();
data.forEach((d, i) => {{
  const row = tbody.insertRow();
  row.style.cssText = `opacity:0;animation:fadeRow 400ms ${{i * 100}}ms ease forwards`;
  keys.forEach(k => {{
    const td = row.insertCell();
    td.textContent = d[k];
    td.style.cssText = 'padding:12px 20px;border-bottom:1px solid #1e293b';
  }});
}});

// Animation keyframes
const style = document.createElement('style');
style.textContent = '@keyframes fadeRow {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:translateY(0); }} }}';
document.head.appendChild(style);

container.appendChild(table);
"""


def _gen_text(data_json: str, fs: int, sw: int, anim: int) -> str:
    """Generate JavaScript code for rendering a chart with provided data and styles."""
    return f"""
const data = {data_json};
const container = document.getElementById('chart');
container.style.cssText = 'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:32px;height:100%';

data.forEach((d, i) => {{
  const card = document.createElement('div');
  card.style.cssText = `text-align:center;opacity:0;animation:fadeIn 500ms ${{i * 200}}ms ease forwards`;

  const label = document.createElement('div');
  label.textContent = d.label || d.name || '';
  label.style.cssText = 'font-size:16px;color:#94a3b8;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px';

  const value = document.createElement('div');
  value.textContent = d.value || '';
  value.style.cssText = 'font-size:48px;font-weight:800;color:{CANVAS_FG}';

  card.appendChild(label);
  card.appendChild(value);
  container.appendChild(card);
}});

const style = document.createElement('style');
style.textContent = '@keyframes fadeIn {{ from {{ opacity:0; transform:scale(0.9); }} to {{ opacity:1; transform:scale(1); }} }}';
document.head.appendChild(style);
"""


# Inline-only generators (types without figure-lab support)
_INLINE_GENERATORS: dict[str, callable] = {
    "line": _gen_line,
    "multi_line": _gen_multi_line,
    "slope": _gen_slope,
    "diverging_bar": _gen_diverging_bar,
    "pie": _gen_pie,
    "donut": _gen_donut,
    "scatter": _gen_scatter,
    "dot_plot": _gen_dot_plot,
    "sparkline": _gen_sparkline,
    "table": _gen_table,
    "text": _gen_text,
}


# ---------------------------------------------------------------------------
# HTML wrapper (dark theme, 5ft canvas)
# ---------------------------------------------------------------------------

def _wrap_html(d3_code: str, title: str) -> str:
    """Wrap D3 code in a complete HTML document with optional title."""
    safe_title = escape(title) if title else "D3 Gallery"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
  body {{
    background: {CANVAS_BG};
    color: {CANVAS_FG};
    font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
    margin: 0;
    padding: 0;
    height: 100vh;
    width: 100vw;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }}
  .canvas-header {{
    padding: 24px 32px 12px;
    flex-shrink: 0;
  }}
  .canvas-title {{
    font-size: 28px;
    font-weight: 700;
  }}
  .canvas-body {{
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px 32px 32px;
    overflow: hidden;
    animation: fade-in {ANIMATION_MS}ms cubic-bezier(0.4, 0, 0.2, 1) both;
  }}
  @keyframes fade-in {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  #chart {{ width: 100%; height: 100%; }}
  /* Override D3 axis/tick colors for dark theme */
  .domain, .tick line {{ stroke: #475569 !important; }}
  .tick text {{ fill: {CANVAS_FG} !important; }}
  text {{ fill: {CANVAS_FG}; }}
</style>
</head>
<body>
<div class="canvas-header"><div class="canvas-title">{safe_title}</div></div>
<div class="canvas-body">
<div id="chart"></div>
</div>
<script type="module">
import * as d3 from "{D3_CDN}";
{d3_code}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ALL_CHART_TYPES = [
    "bar", "hbar", "stacked_bar", "grouped_bar", "diverging_bar",
    "line", "multi_line", "slope",
    "area", "stacked_area", "waterfall",
    "pie", "donut",
    "scatter", "bubble",
    "histogram", "box_plot",
    "gauge", "funnel",
    "dot_plot", "sparkline",
    "table", "text",
]


def generate_chart(chart_type: str) -> tuple[str, str]:
    """
    Generate an HTML visualization and metadata JSON for a chart type.
    Returns (d3_code, data_json).
    """
    data = SAMPLE_DATA.get(chart_type, [{"label": "N/A", "value": 0}])
    data_json = json.dumps(data)

    # Prefer figure-lab generator, fall back to inline
    gen_fn = _FIGURE_LAB_GENERATORS.get(chart_type)
    if gen_fn is None:
        gen_fn = _INLINE_GENERATORS.get(chart_type)

    if gen_fn is None:
        # Absolute fallback: use bar
        if "bar" in _FIGURE_LAB_GENERATORS:
            gen_fn = _FIGURE_LAB_GENERATORS["bar"]
        else:
            raise ValueError(f"No generator for chart type: {chart_type}")

    d3_code = gen_fn(data_json, FONT_SIZE, STROKE_WIDTH, ANIMATION_MS)
    return d3_code, data_json


def main() -> None:
    """Create necessary directories and generate charts with metadata."""
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    ts = int(time.time())
    ts_iso = datetime.now(timezone.utc).isoformat()
    generated = []
    errors = []

    for chart_type in ALL_CHART_TYPES:
        try:
            d3_code, data_json = generate_chart(chart_type)
            title = CHART_TITLES.get(chart_type, chart_type.replace("_", " ").title())
            html = _wrap_html(d3_code, title)

            filename = f"{chart_type}_{ts}"
            html_path = WORKING_DIR / f"{filename}.html"
            meta_path = METADATA_DIR / f"{filename}.json"

            html_path.write_text(html, encoding="utf-8")

            meta = CHART_META.get(chart_type, {})
            data = SAMPLE_DATA.get(chart_type, [])
            metadata = {
                "chart_type": chart_type,
                "viz_family": meta.get("viz_family", "unknown"),
                "sample_query": meta.get("sample_query", ""),
                "title": title,
                "data_shape": {
                    "rows": len(data),
                    "fields": list(data[0].keys()) if data else [],
                },
                "source": "seed_d3_gallery.py",
                "timestamp": ts_iso,
                "html_path": str(html_path),
            }
            meta_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            generated.append(chart_type)
            print(f"  [OK] {chart_type:20s} -> {html_path.name}")

        except Exception as exc:
            errors.append((chart_type, str(exc)))
            print(f"  [ERR] {chart_type:20s} -> {exc}")

    print(f"\n--- Summary ---")
    print(f"Generated: {len(generated)}/{len(ALL_CHART_TYPES)}")
    print(f"HTML dir:  {WORKING_DIR}")
    print(f"Meta dir:  {METADATA_DIR}")
    if errors:
        print(f"Errors:    {len(errors)}")
        for ctype, err in errors:
            print(f"  - {ctype}: {err}")


if __name__ == "__main__":
    main()
