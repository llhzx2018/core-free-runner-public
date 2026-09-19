#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ephemeral_lane_spec.py"


class EphemeralLaneSpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.spec = {
            "schema": "vf-ephemeral-lane-spec/v1",
            "lane_id": "p02-v2539-candidate-20260919",
            "project_id": "P02",
            "repository": "llhzx2018/vf-library",
            "target_version": "2.5.39",
            "target_sha": "65a988761b9f398b7031ea889c51a8a054844099",
            "target_tree": "ebb9cbd935157860efbee41601d737dd965a70ba",
            "source_versions": ["2.5.35", "2.5.36", "2.5.37", "2.5.38"],
            "schema_version": "2401",
            "candidate_run": "35440232231",
            "previous_lane": {
                "target_version": "2.5.38",
                "target_sha": "8bf8471bc3e33613f26d0eddc0dfe11ab1ba9895",
                "target_tree": "ea2f9a563cddc333ca3cfbcebc32313adfbdbf8c",
            },
            "extra": {"TARGET_PORT": "18339"},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def write_spec(self, payload=None):
        path = self.dir / "lane.json"
        path.write_text(json.dumps(payload or self.spec), encoding="utf-8")
        return path

    def run_cmd(self, *args):
        return subprocess.run(
            ["python3", str(SCRIPT), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_validate_and_github_output(self):
        spec = self.write_spec()
        result = self.run_cmd("validate", "--spec", spec)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["variables"]["TARGET_VERSION_COMPACT"], "2539")
        self.assertEqual(payload["variables"]["SOURCE_VERSIONS_CSV"], "2.5.35,2.5.36,2.5.37,2.5.38")

        result = self.run_cmd("github-output", "--spec", spec)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("repository=llhzx2018/vf-library\n", result.stdout)
        self.assertIn("target_version=2.5.39\n", result.stdout)
        self.assertIn("target_sha=65a988761b9f398b7031ea889c51a8a054844099\n", result.stdout)
        self.assertIn('source_versions_json=["2.5.35","2.5.36","2.5.37","2.5.38"]\n', result.stdout)
        self.assertIn("target_port=18339\n", result.stdout)

    def test_render_uses_single_source_identity(self):
        spec = self.write_spec()
        template = self.dir / "workflow.yml.tmpl"
        output = self.dir / "workflow.yml"
        template.write_text(
            "env:\n"
            "  TARGET_REPO: {{REPOSITORY}}\n"
            "  TARGET_VERSION: {{TARGET_VERSION}}\n"
            "  TARGET_SHA: {{TARGET_SHA}}\n"
            "  TARGET_TREE: {{TARGET_TREE}}\n"
            "  TARGET_TAG: {{TARGET_TAG}}\n"
            "  TARGET_VERSION_COMPACT: {{TARGET_VERSION_COMPACT}}\n"
            "  SOURCE_VERSIONS_JSON: '{{SOURCE_VERSIONS_JSON}}'\n"
            "  TARGET_PORT: {{TARGET_PORT}}\n",
            encoding="utf-8",
        )
        first = self.run_cmd("render", "--spec", spec, "--template", template, "--output", output)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        content = output.read_text(encoding="utf-8")
        self.assertIn("TARGET_VERSION: 2.5.39", content)
        self.assertIn("TARGET_VERSION_COMPACT: 2539", content)
        self.assertIn("TARGET_PORT: 18339", content)
        sha1 = json.loads(first.stdout)["sha256"]

        second_output = self.dir / "workflow-2.yml"
        second = self.run_cmd("render", "--spec", spec, "--template", template, "--output", second_output)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(sha1, json.loads(second.stdout)["sha256"])
        self.assertEqual(output.read_bytes(), second_output.read_bytes())

    def test_rejects_copied_target_identity_literal(self):
        spec = self.write_spec()
        template = self.dir / "bad.yml.tmpl"
        output = self.dir / "bad.yml"
        template.write_text(
            "env:\n"
            "  TARGET_REPO: {{REPOSITORY}}\n"
            "  TARGET_VERSION: 2.5.39\n"
            "  TARGET_SHA: {{TARGET_SHA}}\n",
            encoding="utf-8",
        )
        result = self.run_cmd("render", "--spec", spec, "--template", template, "--output", output)
        self.assertEqual(result.returncode, 2)
        self.assertIn("IDENTITY_LITERAL_IN_TEMPLATE:2.5.39", result.stdout)

    def test_rejects_previous_lane_literal_even_when_previous_is_source(self):
        spec = self.write_spec()
        template = self.dir / "bad-prev.yml.tmpl"
        output = self.dir / "bad-prev.yml"
        template.write_text(
            "env:\n"
            "  TARGET_REPO: {{REPOSITORY}}\n"
            "  TARGET_VERSION: {{TARGET_VERSION}}\n"
            "  TARGET_SHA: {{TARGET_SHA}}\n"
            "  OLD_VERSION: 2.5.38\n",
            encoding="utf-8",
        )
        result = self.run_cmd("render", "--spec", spec, "--template", template, "--output", output)
        self.assertEqual(result.returncode, 2)
        self.assertIn("IDENTITY_LITERAL_IN_TEMPLATE:2.5.38", result.stdout)

    def test_rejects_target_inside_source_versions(self):
        bad = dict(self.spec)
        bad["source_versions"] = ["2.5.38", "2.5.39"]
        spec = self.write_spec(bad)
        result = self.run_cmd("validate", "--spec", spec)
        self.assertEqual(result.returncode, 2)
        self.assertIn("target version must not be a source", result.stdout)


if __name__ == "__main__":
    unittest.main()
