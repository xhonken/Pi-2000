# Versions and releases

The first numbered release is **0.1.0-alpha.1**. Earlier work is preserved in [Git history](https://github.com/xhonken/Pi-2000/commits/main). We start release numbering here rather than assigning release numbers retroactively to untested historical commits.

## Find and compare versions

- [GitHub Releases](https://github.com/xhonken/Pi-2000/releases) contains release notes and source ZIP/tar downloads.
- [CHANGELOG.md](../CHANGELOG.md) summarizes changes for each release.
- [VERSION](../VERSION) identifies the source release line.
- Run `./scripts/version.sh` from a checkout to see the version, exact commit and local-change status. Source archives include VERSION but have no Git history.

The source version does not prove which code is currently deployed. `git pull` changes the checkout; the updater deploys it. After updating, run `sudo ./scripts/doctor.sh` from that same checkout to compare deployed application files against the checkout. The session worker can still be running older code until its next planned restart, as explained in the installation guide.

GitHub releases are based on tags pointing to specific commits and include source archive downloads. Anyone with repository read access can view and compare them. While this repository is private, its releases are private too. See [GitHub's release documentation](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

## Numbering policy

We use the [Semantic Versioning format](https://semver.org/): `MAJOR.MINOR.PATCH`, with an Alpha/Beta suffix for prereleases. During initial development, compatibility is not guaranteed.

| Version example | Meaning |
| --- | --- |
| `0.1.0-alpha.1` | First numbered Alpha snapshot. |
| `0.1.0-alpha.2` | Next Alpha iteration toward 0.1.0. |
| `0.1.0-beta.1` | A later testing stage when the planned scope is ready. |
| `0.1.0` | Release without a prerelease suffix; still in the 0.x development series. |
| `1.0.0` | Future stable compatibility baseline, when ready. |

Every published version is immutable: do not move its tag or replace its contents. Fixes get a new version. `main` is ongoing development; commits after a tag are not that exact release even if VERSION still names its release line. The version command prints Git revision information to distinguish them.

## Install a specific release

For a new installation, check out the tag before following the [installation guide](INSTALLATION.md):

```sh
git clone --branch v0.1.0-alpha.1 --depth 1 https://github.com/xhonken/Pi-2000.git
cd Pi-2000
./scripts/version.sh
cp config/config.example.toml pi2000.toml
nano pi2000.toml
./scripts/install.sh --config pi2000.toml --check
sudo ./scripts/install.sh --config pi2000.toml
```

A tag checkout is detached from a branch. For a later release, fetch that tag explicitly and switch to it, then follow that release's upgrade notes. Do not use `git pull` to update a detached tag checkout. A regular main-branch checkout can continue using the existing `git pull --ff-only` workflow.

To inspect an old version without changing your current checkout, use GitHub's tag selector or extract its source archive into a separate directory.

Checking out an old tag does not roll back SQLite, user files, browser profiles or system configuration. Do not run an older installer against newer live data as a downgrade procedure. Use the [recovery instructions](INSTALLATION.md) and a compatible backup/application version.

## Maintainer release checklist

1. Choose the next version, update VERSION, and move the relevant Unreleased changelog entries into a dated release section. Document migration requirements and known limitations.
2. Run checks appropriate to the changes and the release's validation requirements. Record what was actually tested, including any fresh-install gaps.
3. Commit the complete release contents. Ensure `git status --short` is empty and push the commit to main.
4. Create an annotated tag at that exact commit, for example `git tag -a v0.1.0-alpha.2 -m 'Pi-2000Web 0.1.0-alpha.2'`, then push that tag explicitly.
5. Create the GitHub release from the existing tag with release notes. Mark Alpha/Beta/RC releases as prereleases. With GitHub CLI, use `gh release create TAG --verify-tag --prerelease --title TITLE --notes-file NOTES.md` (replace the uppercase arguments).
6. Verify the published release, tag and VERSION all agree. Add future changes under Unreleased; never retag a published release.

Release notes should state changes, supported installation target, validation performed, remaining limitations and any required backup or migration steps. Never include private configuration, credentials, databases or user files in release assets.
