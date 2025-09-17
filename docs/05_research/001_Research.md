Here is a comprehensive, detailed answer addressing all 5 queries you listed about Tailwind + React scrolling, sticky interplay, overlays, scroll clipping, sticky footers, and PDF.js canvas scroll issues — all combined into one view with examples and guidance.

***

## 1. Flex Scroll + Sticky Interplay (Tailwind/React)

In a 3-column flex layout with sticky header and sticky footer/pager, to make the middle column scroll independently and prevent page-level scroll, use this canonical pattern:

- Parent uses `flex flex-col h-screen` for full viewport height stacking.
- Header uses `sticky top-0`, footer uses `sticky bottom-0`, both with appropriate z-index.
- The middle content area: `flex-1 min-h-0 overflow-auto` inside a flex row to enable independent scrolling.
- Columns are structured with fixed widths for side columns and `flex-1` on middle column.
- `min-h-0` is essential on the scrollable flex child to allow shrinking and enable scrolling.
- Avoid `overflow-hidden` on ancestors wrapping the scrollable container as it blocks scroll height determination.
- Use `overscroll-contain` on the scrolling container to prevent scroll chaining to parent.

Example JSX + Tailwind:

```jsx
<div className="flex flex-col h-screen">
  <header className="sticky top-0 bg-gray-800 text-white h-16 z-50 flex items-center px-4">
    Sticky Header
  </header>
  <main className="flex flex-1 min-h-0 overflow-hidden">
    <div className="w-1/4 bg-gray-200 p-4">
      Left panel
    </div>
    <div className="flex-1 min-h-0 overflow-auto overscroll-contain p-4">
      {/* Scrollable content */}
      <div style={{minHeight: "150vh"}}>
        Tall content here for vertical scrolling
      </div>
    </div>
    <div className="w-1/4 bg-gray-300 p-4">
      Right panel
    </div>
  </main>
  <footer className="sticky bottom-0 bg-gray-800 text-white h-12 z-50 flex items-center px-4">
    Sticky Footer / Pager
  </footer>
</div>
```

***

## 2. Overlay + Wheel Events Over Scrollable Container

When a full-size overlay sits on top of a scrollable container (e.g., a canvas inside a scroll wrapper):

- By default, overlay intercepts pointer events blocking wheel scroll on the content below.
- Use CSS `pointer-events: none` on the overlay for allowing pointer events to pass through to the scroll container.
- Alternatively, in React, attach `onWheelCapture` to the scroll container to intercept the wheel event before overlay handlers.
- Avoid calling `preventDefault()` on wheel events in capture/bubble phases unless necessary as it blocks scroll.
- Passive event listeners (default in modern browsers) improve scroll performance by disallowing preventDefault on wheel.
- Use event capture (`onWheelCapture`) in React to handle wheel events before overlays that may stop propagation.
- Optionally, disable/remove wheel event handlers on the overlay when scroll should be allowed.

Example React snippet:

```jsx
<div
  onWheelCapture={(e) => {
    // Optionally monitor or handle scroll at container with capture phase
  }}
  className="overflow-auto h-96"
>
  <canvas>...</canvas>
  <div style={{pointerEvents: 'none', position: 'absolute', top: 0, left: 0, right: 0, bottom: 0}}>
    Overlay content (transparent to pointer/wheel events)
  </div>
</div>
```

***

## 3. Prevent Scroll Clipping by Inner Wrappers (overflow-hidden)

When an inner wrapper uses `overflow-hidden` above a scrollable container, it can:

- Prevent the scrollable parent container from computing `scrollHeight > clientHeight`.
- This blocks scrolling because parent thinks no overflow exists.
- Removing `overflow-hidden` or moving it to a different ancestor fixes scroll height calculation and enables scroll.
- To preserve visual clipping *without* breaking scroll, apply `overflow-hidden` on a sibling or outer container that does not clip the scroll container directly.
- Use padding or a spacer div to create visible clipping zones instead of wrapping scroll container in `overflow-hidden`.
- Keep the scrollable container itself free of `overflow-hidden` so scroll height and scrolling works properly.

***

## 4. Sticky Inside Scrollable Container (Footer Filmstrip)

To keep a sticky bottom toolbar or filmstrip inside a scrollable column that does not occlude content or block wheel scroll:

- Use `sticky bottom-0` on the footer toolbar inside the scrollable container.
- Apply `overscroll-contain` on the scroll container to prevent scroll chaining to ancestors.
- Add a padding-bottom or spacer div equal to the height of the sticky footer so content is not occluded behind it.
- IntersectionObserver checks or event listeners can detect footer visibility if dynamic interaction is desired.
- Tailwind CSS example:

```jsx
<div className="flex flex-col h-96 overflow-auto overscroll-contain relative">
  <div className="flex-1">
    Scrollable content that extends vertically
    <div style={{height: "150%"}}></div>
  </div>
  <div className="sticky bottom-0 bg-gray-900 text-white p-2 z-40">
    Sticky footer filmstrip toolbar
  </div>
</div>
```

Add padding-bottom to scroll container if needed, e.g.:

```html
<div className="pb-12">...</div>
```

***

## 5. PDF.js Canvas Sizing and Scroll

When using pdf.js canvases inside flex containers:

- Avoid setting fixed heights on containers wrapping the canvas; instead allow natural height based on PDF page size.
- Ensure the content height exceeds `clientHeight` so parent scroll can occur.
- Avoid `overflow-hidden` on containers that would clip tall canvases improperly.
- To diagnose, check that `scrollHeight > clientHeight` on the scroll container.
- Use CSS `min-height: auto` or no height restrictions on container parents.
- Tailwind class `min-h-0` on flex containers with overflow-auto is important to allow canvas height to control scroll.
- Example setup:

```jsx
<div className="flex flex-col h-screen">
  <div className="flex-1 overflow-auto min-h-0 p-4">
    <canvas style={{width: "100%", height: "auto"}} />
    {/* Multiple page canvases stack vertically */}
  </div>
</div>
```

***

This detailed guidance, including React and Tailwind CSS code snippets, and explanations for common pitfalls and best practices, should enable robust, maintainable scroll and sticky UI behaviors for complex layouts with overlays and canvas content.

If you want, I can provide tailored MiniPatch code or Puppeteer verification scripts for any pattern above.

***

References are derived from Tailwind CSS official docs and multiple relevant Stack Overflow and GitHub discussions as summarized here. Let me know if you want full URL citations or deeper dive into any point.

[1](https://www.youtube.com/watch?v=yHF68UXQUI0)
[2](https://kombai.com/tailwind/overflow/)
[3](https://stackoverflow.com/questions/69400560/how-to-change-scrollbar-when-using-tailwind-next-js-react)
[4](https://tailwindcss.com/docs/overflow)
[5](https://tailwindcss.com/docs/overscroll-behavior)
[6](https://tailwindcss.com/docs/scroll-behavior)
[7](https://tailwindcss.com/docs/scroll-margin)
[8](https://preline.co/docs/custom-scrollbar.html)
[9](https://tailwindcss.com/docs/scroll-snap-type)