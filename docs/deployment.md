# Deployment Process — Arsh Studio

## Overview

The site is a static HTML/CSS/JS project deployed to Hostinger shared hosting via FTP on every push. There are two active deployment branches:

| Branch    | Purpose                        | Deploys to           |
|-----------|--------------------------------|----------------------|
| `main`    | Production — stable releases   | Hostinger (live)     |
| `develop` | Active development / staging   | Hostinger (live)*    |

> \* Both branches push to the same FTP target defined by `FTP_REMOTE_DIR`. When a separate staging environment is available, update `FTP_REMOTE_DIR` in the `develop` workflow step to point to a different path.

---

## Branch Strategy

```
main          ←── production, always stable
  └── develop ←── all feature work lands here first
        └── feature/<name>  (optional short-lived branches for large changes)
```

- **Never push directly to `main`** unless you are doing an emergency hotfix.
- All work is done on `develop` (or a `feature/*` branch cut from `develop`).
- When `develop` is stable and tested, open a PR → `main` to promote to production.

---

## Cutting a Release Branch

When you are ready to promote `develop` to `main`:

```bash
# 1. Make sure develop is up to date and green
git checkout develop
git pull origin develop

# 2. Open a PR on GitHub: develop → main
gh pr create \
  --base main \
  --head develop \
  --title "Release: <version or date>" \
  --body "Describe what changed in this release."

# 3. Review the PR diff, check GitHub Actions are green, then merge via GitHub UI
```

Do **not** fast-forward merge; use a merge commit so the release boundary is visible in `git log`.

---

## Rollout Steps

### Standard release (develop → main)

1. Confirm the `develop` branch CI run is green (GitHub Actions tab).
2. Visually review the live site on the staging path (if configured) or preview locally: `npx serve .`
3. Open and merge the PR `develop → main` on GitHub.
4. GitHub Actions automatically FTPs the build to Hostinger within ~60 seconds.
5. Hard-refresh the live domain and smoke-test: nav, contact form, mobile layout.
6. If anything is broken, revert immediately (see **Rollback** below).

### Emergency hotfix (straight to main)

```bash
git checkout main
git pull origin main
git checkout -b hotfix/<short-description>
# ... make the fix ...
git add <files>
git commit -m "fix: <description>"
git push origin hotfix/<short-description>
# Open PR → main, merge after review
# Then back-merge into develop so it stays up to date:
git checkout develop && git merge main && git push origin develop
```

---

## Rollback

The FTP deploy is a full mirror — there is no atomic swap. To roll back:

1. Identify the last good commit on `main`:
   ```bash
   git log --oneline main
   ```
2. Create a revert commit (preferred — keeps history clean):
   ```bash
   git revert <bad-commit-sha>
   git push origin main
   ```
3. GitHub Actions will re-deploy the reverted state automatically.

Avoid `git reset --hard` on `main` unless absolutely necessary — it rewrites shared history.

---

## GitHub Secrets Required

| Secret            | Description                          |
|-------------------|--------------------------------------|
| `FTP_SERVER`      | Hostinger FTP hostname               |
| `FTP_USERNAME`    | FTP account username                 |
| `FTP_PASSWORD`    | FTP account password                 |
| `FTP_REMOTE_DIR`  | Remote path on server (e.g. `public_html/`) |

Add or rotate secrets at: **GitHub → Settings → Secrets and variables → Actions**

---

## Local Development

```bash
# No build step — open directly or use a local server
npx serve .
# or
python -m http.server 8080
```

---

## CI/CD Workflow File

`.github/workflows/deploy.yml` — triggers on push to `main` **and** `develop`.  
Both branches share the same FTP credentials. Update `FTP_REMOTE_DIR` per-branch if separate environments are needed.
