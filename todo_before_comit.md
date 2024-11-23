Checklist for Finishing a New Update
1. Update the Version
Use bump-my-version to update the version based on the type of update:
# Bugfix (PATCH)
bump-my-version patch

# New features (MINOR)
bump-my-version minor

# Breaking changes (MAJOR)
bump-my-version major

# Pre-releases (e.g., alpha, beta)
bump-my-version prerelease
2. Stage and Commit the Changes
Add all changes to the staging area:

git add .
Commit the changes with a clear message:

git commit -m "Bump version to <new-version> and update features"
3. Tag the Version
Create an annotated tag for the new version:
git tag -a v<new-version> -m "Version <new-version>: <brief description>"
Example:
git tag -a v1.2.0 -m "Version 1.2.0: Added logging improvements and fixed X bug"
4. Push Changes to GitHub
Push your branch with the new commit:

git push origin main
Push the tag to GitHub:

git push origin v<new-version>
5. Create a Release on GitHub
Manually (via GitHub UI):

Go to your repository > Releases > Draft a new release.
Select the tag (e.g., v1.2.0), add a title, and write release notes.
Automatically (via CLI): Use the GitHub CLI to create a release:

gh release create v<new-version> --title "Version <new-version>" --notes "Bug fixes and new features."
6. Update the Changelog (Optional)
Update your CHANGELOG.md with the changes made in this version. Example format:
## [1.2.0] - YYYY-MM-DD
### Added
- Improved logging system.
- New feature X.

### Fixed
- Bug with Y.

### Changed
- Refactored Z module.
7. Merge Changes into Production (if applicable)
If you’re working on a development branch, merge the updates into main or production:
git checkout main
git merge <your-branch>
git push origin main
8. Deploy (Optional)
If you’re deploying the code, trigger your deployment pipeline or follow your standard deployment procedure.
Summary Checklist
Update Version: Use bump-my-version.
Stage and Commit: git add . and git commit.
Tag the Version: git tag -a v<new-version>.
Push:
Code: git push origin main
Tag: git push origin v<new-version>
Create a Release: Draft on GitHub or use gh release create.
Update the Changelog (if applicable).
Merge into Production (if necessary).
Deploy (if applicable).
