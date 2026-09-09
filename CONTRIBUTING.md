# Contributing to Live School-Bus ETA Service

Thank you for your interest in contributing! This project is designed as an educational, clean, and reliable prototype for smart school bus fleet tracking and dynamic arrival prediction.

## Development Workflow

### 1. Create a Branch
Always create a descriptive topic branch from `main`:
```bash
git checkout -b feature/your-feature-name
# or for bug fixes:
git checkout -b fix/issue-description
```

### 2. Make Changes
- Keep changes simple, modular, and adhering to PEP 8 standards.
- Follow the existing folder architecture:
  - Database logic in `database/`
  - Prediction algorithms in `eta_engine/`
  - Simulation & telemetry in `simulator/`
  - Routes and API controllers in `app.py`
  - Front-end views and templates in `templates/` and `static/`
- Avoid introducing unnecessary heavy external dependencies or cloud frameworks.

### 3. Run Tests
Verify all unit and integration tests pass before committing your work:
```bash
python -m pytest
```
Ensure all tests execute with zero failures. If introducing a new feature, add corresponding unit tests under `tests/`.

### 4. Submit Changes
1. Ensure no runtime artifacts (`.db`, `__pycache__`, `.env`) are staged:
   ```bash
   git status
   ```
2. Commit your modifications with a concise, meaningful message:
   ```bash
   git add .
   git commit -m "feat: add descriptive feature summary"
   ```
3. Push your branch to GitHub:
   ```bash
   git push origin feature/your-feature-name
   ```
4. Open a **Pull Request (PR)** against the `main` branch with a summary of the implemented changes and testing verification.
