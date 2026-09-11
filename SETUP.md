# Publish AB ReaLayer through GitHub and ReaPack

This folder is a repository starter, not a live GitHub repository. It includes a bootstrap index.xml. The first successful GitHub Actions run populates it with the actual package and commit-specific download URL.

## 1. Prepare your repository

1. Create a GitHub account if needed.
2. Create a new public repository named **AB-ReaLayer**, with default branch **main**. Leave GitHub's README, .gitignore and licence initialisation unchecked because this folder supplies the project files.
3. Extract the starter ZIP and open its AB-ReaLayer folder. Include the .github directory and the dot-prefixed configuration files; Finder may hide them until you press Command+Shift+Period.
4. Replace YOUR_GITHUB_USERNAME in README.md with your GitHub username. If you chose another repository name, update the example URL too.
5. Review release.json. The publishing author is **Alec Bathman**; keep this credit for the official AB ReaLayer release. Run python3 src/build.py after changing it.
6. Choose your distribution licence and add LICENSE. No licence has been assigned on your behalf.

## 2. Upload with Git

In Terminal or Git Bash, change to the extracted AB-ReaLayer folder. Replace the example username before running the remote command:

```sh
git init -b main
git add .
git commit -m "Prepare AB ReaLayer for ReaPack"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/AB-ReaLayer.git
git push -u origin main
```

Git may first ask you to configure your commit name/email and sign into GitHub. Use your own identity. Do not paste an access token into files or a repository URL.

After the first upload, you can use GitHub Desktop: File → Add local repository, select this folder, then use its Commit, Push and Pull controls. Do not upload the ZIP itself as the repository contents.

## 3. Let Actions build the catalogue

Open the repository's **Actions** tab and select the **ReaPack** workflow. Its check job verifies the generated plugin and runs the official reapack-index header checker. Its publish job updates index.xml and commits it back to main.

The workflow requests contents:write only for publication and uses GitHub's built-in token. You do not need to create a personal token for it. Repository/organisation policy or branch protection can still prevent bot pushes. If you see a 403/push rejection, inspect Settings → Actions → General → Workflow permissions and your main-branch rules. Do not disable organisation rules blindly; use an allowed workflow policy or ask the repository administrator.

If someone pushes while the index is being built, a non-fast-forward push can fail safely. Rerun the workflow against current main; do not force-push.

Wait for BOTH jobs to pass. Open index.xml and check that it contains a reapack entry for VariationSampler-M11.jsfx, a version and a source URL containing a 40-character commit hash. An empty index means publication has not completed. GitHub Pages is not required.

## 4. Install and share

Your subscription URL will be:

```text
https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/AB-ReaLayer/main/index.xml
```

In REAPER with ReaPack installed:

1. Extensions → ReaPack → Import repositories: paste the URL.
2. Extensions → ReaPack → Browse packages: search AB ReaLayer.
3. Mark it for installation and Apply.
4. Find JS: AB_ReaLayer in the FX browser and test loading/playing a WAV.

Share the raw index.xml URL. A GitHub repository URL or a GitHub release ZIP is not a ReaPack subscription URL. A custom repository does not automatically appear in everyone's default repository list.

Existing manually installed copies remain separate. Keep them for saved projects until you deliberately migrate those instances; do not delete them assuming ReaPack has rewritten project references.

## 5. Publish later changes

Before editing, pull the bot's catalogue commit:

```sh
git pull --ff-only
```

Edit source files under src/. Update version and changelog in release.json, for example 0.11.1 to 0.11.2. Run:

```sh
python3 src/build.py
python3 tools/check_package.py
git add .
git commit -m "Release AB ReaLayer 0.11.2"
git push
```

Check Actions again. Users can then use ReaPack → Synchronize packages. Do not reuse a published version for changed plugin bytes, rename the package path, delete historical index entries, or regenerate old release downloads from a moving branch. The workflow uses commit URLs and does not amend published versions.

You can optionally create matching Git tags/releases after publication; these are not required for ReaPack delivery.

## What's included

| File or folder | Purpose |
|---|---|
| Instruments/VariationSampler-M11.jsfx | The single installable package |
| src/ | Editable generator and DSP/GUI sources |
| release.json | Version, author, package name and changelog |
| .github/workflows/reapack.yml | Build check and catalogue publication |
| .reapack-index.conf | Repository name and indexing exclusions |
| index.xml | Bootstrap catalogue, then maintained by Actions |
| .gitignore / .gitattributes | Ignore local assets and standardise text line endings |
| tools/check_package.py | Detect stale generated files |
| tools/check_index.py | Check package identity and immutable URLs |
| tests/ | Existing REAPER test runners; REAPER is supplied separately |
| docs/ | User guide, architecture and prior verification reports |

The root VariationSampler-M11.jsfx is generated for local test compatibility and is ignored by Git; Instruments/ contains the tracked distributable. Only Instruments is intended to become a ReaPack category. Test fixtures and generator files are explicitly excluded from indexing.

## Verification limits

Local deterministic build and package checks are included. The indexer/GitHub publication needs a successful first Actions run, and the remote installation must then be checked in REAPER. Historical audio and GUI reports in docs/previous-test-results belong to the hashes recorded in those reports; they are not evidence that remote publication has already occurred.

## Official references

- [ReaPack packaging documentation](https://github.com/cfillion/reapack-index/wiki/Packaging-Documentation)
- [Indexer setup and configuration](https://github.com/cfillion/reapack-index/wiki)
- [Index format](https://github.com/cfillion/reapack/wiki/Index-Format)
- [GitHub checkout action](https://github.com/actions/checkout)
