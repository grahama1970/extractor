# Mermaid Chart Fixes in HOW_IT_WORKS.md

## Summary

Fixed Mermaid chart syntax errors in HOW_IT_WORKS.md by properly quoting node labels that contain special characters.

## Issues Fixed

### 1. First Chart - Pipeline Overview (Lines 15-28)
**Problem**: Node labels with `<br/>` tags weren't properly quoted
**Solution**: Wrapped all node labels containing special characters in double quotes

Example:
```diff
- Anno[1. Annotation<br/>Extraction]
+ Anno["1. Annotation<br/>Extraction"]
```

### 2. Second Chart - Complete Architecture (Lines 167-225)
**Problem**: Multiple node labels with special characters and line breaks
**Solution**: Quoted all problematic labels:
- Node labels with `<br/>` tags
- Node labels with special characters like `+`
- Database node syntax fixed: `ArangoDB[(` → `ArangoDB[(`

Example fixes:
```diff
- Annotation[Annotation Extraction<br/>& Storage]
+ Annotation["Annotation Extraction<br/>& Storage"]

- Text[Text + Positions]
+ Text["Text + Positions"]
```

## Why These Fixes Were Needed

Mermaid's parser has strict rules about node labels:
1. Labels containing special characters (`<br/>`, `+`, `&`, parentheses) must be quoted
2. Without quotes, the parser fails with errors like "Expecting 'SQE', got 'PS'"
3. The error occurs because the parser interprets unquoted special characters as syntax elements

## Verification

Both charts should now render correctly in any Mermaid-compatible viewer (GitHub, VS Code, etc.).

## Key Takeaway

When creating Mermaid diagrams, always quote node labels if they contain:
- HTML tags (`<br/>`)
- Special characters (`+`, `&`, `/`, `(`, `)`)
- Multi-line content
- Any non-alphanumeric characters except spaces and basic punctuation