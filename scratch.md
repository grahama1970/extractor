prototypes/tabbed/html/src/pages/ClassicLayout.tsx (your current copy after you patch)

prototypes/tabbed/html/src/index.css (full file)

prototypes/tabbed/html/src/App.css (if it still exists; confirm whether it’s imported anywhere)

prototypes/tabbed/html/src/components/ui/sidebar.tsx (we rely on its layout helpers; want to confirm no extra overflow or width rules)

prototypes/tabbed/html/index.html (to confirm no external stylesheet is pulled)

Any project-level CSS that might affect layout (e.g., a global :root or .container wrapper)