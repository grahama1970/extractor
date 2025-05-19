# Task Guidelines Quick Reference for Marker

## Essential Rules

### 1. File Structure
```
docs/tasks/XXX_task_name.md          → Task definition
docs/reports/XXX_task_name_report.md → Implementation report
```

### 2. Never Create Duplicates
❌ `024_task_revised.md`
❌ `024_task_v2.md`
✅ Update original `024_task.md`

### 3. Report Must Include
- **Real command outputs** (not examples)
- **Actual performance metrics** (measured)
- **Working code** (tested)
- **Issues found** (honest assessment)

### 4. Task Workflow
1. Create task file
2. Create report file
3. Implement feature
4. Run actual commands
5. Update task checkboxes
6. **EVALUATE** (most important!)
7. Fix gaps
8. Repeat until done

### 5. Final Evaluation
```markdown
## Final Task Evaluation
**Last Evaluated**: [date]

### Feature: [Name]
- [ ] Core implementation complete ❌
- [ ] CLI commands working ✅
- [ ] Performance verified ❌ (5.2s, needs optimization)

**Notes**: Missing batch processing support, performance too slow
```

### 6. Status Symbols
- ✅ COMPLETE
- ⚠️ PARTIAL (XX%)
- ❌ NOT STARTED
- 🔄 IN PROGRESS

### 7. Common Mistakes
1. Multiple task files
2. Mocked results
3. Missing performance metrics
4. Skipping evaluation
5. Incomplete CLI testing

### 8. Definition of Done
- All checkboxes ✅
- Report has real evidence
- Performance meets criteria
- CLI commands tested
- No gaps in evaluation

### 9. CLI Testing Requirements
- Execute actual commands
- Test all parameters
- Document outputs
- Verify error handling
- End-to-end testing

### 10. Research Requirements
- Use perplexity_ask
- Search GitHub examples
- Document all sources
- No theoretical code
- Real implementations only

**Remember**: Real commands, real results, real evaluation!