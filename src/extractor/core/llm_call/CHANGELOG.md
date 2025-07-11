# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-05-19

### Added
- Initial release of LLM Validation Loop package
- Core validation framework with plugin architecture
- Retry mechanism with incremental feedback
- Redis caching integration
- CLI interface with typer and rich
- 20+ built-in validators for various content types
- Support for custom validators
- Debug tracing and performance metrics
- Full backward compatibility with existing LiteLLM usage
- Comprehensive documentation and examples

### Validators Included
- Base validators: field presence, length, format, type, range
- Table validators: structure and consistency
- Image validators: descriptions and alt text
- Math validators: LaTeX syntax and consistency
- Code validators: syntax, language detection, completeness
- Citation validators: fuzzy matching, format, relevance
- General validators: content quality, tone, JSON structure

### Dependencies
- Uses RapidFuzz for citation matching (better performance than FuzzyWuzzy)
- Integrates with existing Redis cache infrastructure
- Compatible with all LiteLLM-supported models

[0.1.0]: https://github.com/VikParuchuri/marker/releases/tag/v0.1.0