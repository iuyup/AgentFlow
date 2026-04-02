# Contributing to AgentFlow

Thank you for your interest in contributing to AgentFlow! This project is a reference library of multi-agent collaboration patterns, and contributions from the community help make it better.

---

## How to Contribute

### Reporting Issues

Found a bug or have a feature request? Please check if an issue already exists first, then create a new one with:

- **Bug reports**: Steps to reproduce, expected behavior, actual behavior
- **Feature requests**: Clear use case and why it would benefit the community
- **Pattern proposals**: Include the pattern name, problem it solves, and basic topology

Use the issue templates when available.

---

### Submitting Changes

#### Process

1. **Fork** the repository
2. **Create a branch** for your changes:
   ```bash
   git checkout -b pattern/new-pattern-name
   git checkout -b fix/description-of-fix
   ```
3. **Make your changes** following the guidelines below
4. **Add tests** for new patterns or bug fixes
5. **Ensure tests pass**:
   ```bash
   pytest patterns/ -v
   ```
6. **Commit** with a clear message
7. **Push** and create a Pull Request

#### Commit Message Format

```
<type>: <short description>

<optional body>

<optional footer>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

Example:
```
feat: add Chain-of-Experts pattern

Implement sequential expert processing pipeline with final synthesizer.
Include example, tests, and architecture diagram.
```

---

### Pattern Contribution Guidelines

Each pattern must include:

| File | Required |
|------|----------|
| `pattern.py` | Core implementation |
| `example.py` | Runnable demo with `if __name__ == "__main__"` |
| `README.md` | English documentation |
| `README_zh.md` | Chinese documentation |
| `diagram.mmd` | Mermaid architecture diagram |
| `tests/` | Unit tests for core logic |

#### Pattern Requirements

- **3 lines to run**: User should be able to run the example with minimal setup
- **No external dependencies**: Beyond LangGraph, LangChain, and env-based API keys
- **Independent**: Pattern must work standalone, not depend on other patterns
- **Documented**: Architecture, use cases, and limitations must be clear

#### Code Style

- Follow PEP 8
- Use type hints for function signatures
- Keep functions focused (single responsibility)
- Add docstrings for public APIs

---

### Documentation

- English README required for international reach
- Chinese README required for Chinese community
- Include "When to Use" and "When NOT to Use" sections
- Provide at least one realistic example
- Architecture diagram in Mermaid format

---

## Questions?

- Open a GitHub Discussion for questions about using AgentFlow
- Check existing issues and discussions before posting
- Be respectful and constructive in all interactions

---

## License

By contributing to AgentFlow, you agree that your contributions will be licensed under the project's MIT License.
