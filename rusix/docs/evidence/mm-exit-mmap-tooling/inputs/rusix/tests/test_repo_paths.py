#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise path discovery in disposable repositories, including Git worktrees."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class RepoPathTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="rusix-path-tests-")
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name).resolve()
        self.repo = self.base / "arbitrary checkout"
        self.copy_helpers(self.repo)
        self.git(self.repo, "init", "-q")
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for key in ("RUSIX_SOURCE", "RUSIX_PROJECT", "RUSIX_OUTPUT_ROOT", "RUSIX_TOOLS_ROOT"):
            self.env.pop(key, None)

    def copy_helpers(self, repo):
        scripts = repo / "rusix/scripts"
        scripts.mkdir(parents=True)
        for name in ("rusix_paths.py", "repo-paths.sh"):
            shutil.copyfile(SCRIPTS / name, scripts / name)

    def git(self, repo, *args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
                              capture_output=True, text=True)

    def paths(self, repo=None, cwd=None):
        repo = repo or self.repo
        scripts = repo / "rusix/scripts"
        python = subprocess.check_output([
            "python3", "-c",
            "import sys,json;sys.path.insert(0,sys.argv[1]);"
            "from rusix_paths import resolve_paths;"
            "p=resolve_paths();print(json.dumps([str(p.source),str(p.project),"
            "str(p.output),str(p.tools)]))", str(scripts),
        ], cwd=cwd or self.base, env=self.env, text=True)
        shell = subprocess.check_output([
            "bash", "-c", 'source "$1" && printf "%s\\n" "$RUSIX_SOURCE" '
            '"$RUSIX_PROJECT" "$RUSIX_OUTPUT_ROOT" "$RUSIX_TOOLS_ROOT"',
            "path-test", str(scripts / "repo-paths.sh"),
        ], cwd=cwd or self.base, env=self.env, text=True)
        result = json.loads(python)
        self.assertEqual(result, shell.splitlines())
        return [Path(value) for value in result]

    def test_default_arbitrary_checkout_from_unrelated_directory(self):
        output = Path(f"{self.repo}-out")
        self.assertEqual(self.paths(), [self.repo, self.repo / "rusix", output,
                                       output / ".tools/root"])
        self.assertFalse(output.exists())

    def test_relative_overrides_are_caller_relative_literal_paths(self):
        self.env.update(RUSIX_OUTPUT_ROOT="outputs/../result $(not-a-command)",
                        RUSIX_TOOLS_ROOT="tools with spaces/root")
        self.assertEqual(self.paths()[2:], [self.base / "result $(not-a-command)",
                                           self.base / "tools with spaces/root"])

    def test_empty_overrides_use_defaults(self):
        self.env.update(RUSIX_OUTPUT_ROOT="", RUSIX_TOOLS_ROOT="")
        output = Path(f"{self.repo}-out")
        self.assertEqual(self.paths()[2:], [output, output / ".tools/root"])

    def test_symlinked_checkout_and_output_parent(self):
        alias = self.base / "source alias"
        alias.symlink_to(self.repo, target_is_directory=True)
        actual = self.base / "actual output parent"
        actual.mkdir()
        link = self.base / "output alias"
        link.symlink_to(actual, target_is_directory=True)
        self.env["RUSIX_OUTPUT_ROOT"] = str(link / "new output")
        self.assertEqual(self.paths(alias)[0], self.repo)
        self.assertEqual(self.paths(alias)[2], actual / "new output")

    def test_git_worktree_file(self):
        self.git(self.repo, "add", "rusix")
        self.git(self.repo, "-c", "user.name=Path Test", "-c", "user.email=test.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Path fixtures")
        worktree = self.base / "linked checkout"
        self.git(self.repo, "worktree", "add", "--detach", str(worktree))
        self.assertTrue((worktree / ".git").is_file())
        self.assertEqual(self.paths(worktree)[0], worktree)

    def test_nested_non_repository_is_rejected(self):
        nested = self.repo / "nested"
        self.copy_helpers(nested)
        with self.assertRaises(subprocess.CalledProcessError):
            self.paths(nested)


if __name__ == "__main__":
    unittest.main()
