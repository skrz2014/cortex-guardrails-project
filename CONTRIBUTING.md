# Contributing

Thanks for your interest in contributing to this project!

## How to Contribute

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/my-feature`
3. **Commit** your changes: `git commit -m "feat: add new feature"`
4. **Push** to the branch: `git push origin feat/my-feature`
5. **Open** a Pull Request

## Guidelines

- Follow existing code style and patterns
- Add tests for new analytics functions
- Update README if adding new tabs or features
- Use conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`)

## Reporting Issues

Open a GitHub Issue with:
- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Snowflake account region (if relevant)

## Local Development

```bash
# Install test dependencies
pip install pandas numpy pytest

# Run tests
pytest tests/test_aisoc.py -v

# Run E2E scenarios
python tests/test_scenarios.py
```

## Code of Conduct

Be respectful, constructive, and inclusive.
