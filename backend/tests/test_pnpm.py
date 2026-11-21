import unittest

from app.analysis.pnpm import build_pnpm_dependency_graph, parse_pnpm_lockfile


class PnpmGraphTests(unittest.TestCase):
    def test_v9_importer_and_transitive_edges(self):
        lockfile = {
            "lockfileVersion": "9.0",
            "importers": {
                ".": {
                    "dependencies": {
                        "foo": {"specifier": "^1.2.0", "version": "1.2.0"},
                    }
                }
            },
            "packages": {
                "foo@1.2.0": {"resolution": {"integrity": "sha512-foo"}},
                "bar@2.0.0": {"resolution": {"integrity": "sha512-bar"}},
            },
            "snapshots": {
                "foo@1.2.0": {"dependencies": {"bar": "2.0.0"}},
                "bar@2.0.0": {},
            },
        }

        graph = build_pnpm_dependency_graph(lockfile)
        foo_path = "pnpm/foo@1.2.0"
        bar_path = "pnpm/bar@2.0.0"

        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(graph.importer_dependencies["."]["foo"], foo_path)
        self.assertEqual(
            [(edge.source, edge.target, edge.dependency_type.value) for edge in graph.edges],
            [(foo_path, bar_path, "normal")],
        )
        self.assertEqual(graph.nodes[foo_path].integrity, "sha512-foo")

    def test_v9_scoped_package_and_peer_context_identity(self):
        lockfile = {
            "lockfileVersion": "9.0",
            "importers": {".": {}},
            "packages": {
                "@scope/lib@1.0.0(peer@2.0.0)": {},
            },
            "snapshots": {
                "@scope/lib@1.0.0(peer@2.0.0)": {},
            },
        }
        graph = build_pnpm_dependency_graph(lockfile)
        node = next(iter(graph.nodes.values()))
        self.assertEqual(node.name, "@scope/lib")
        self.assertEqual(node.version, "1.0.0")
        self.assertIn("peer@2.0.0", node.path)

    def test_v6_package_dependencies(self):
        lockfile = {
            "lockfileVersion": "6.0",
            "importers": {
                ".": {"dependencies": {"foo": {"specifier": "^1.0.0", "version": "1.0.0"}}}
            },
            "packages": {
                "/foo/1.0.0": {"resolution": {"integrity": "sha512-foo"}, "dependencies": {"bar": "2.0.0"}},
                "/bar/2.0.0": {},
            },
        }
        graph = build_pnpm_dependency_graph(lockfile)
        self.assertEqual(graph.importer_dependencies["."]["foo"], "pnpm/foo/1.0.0")
        self.assertEqual(len(graph.edges), 1)

    def test_rejects_lockfile_versions_older_than_v5(self):
        with self.assertRaisesRegex(ValueError, "supported formats are v5, v6 and v7-v9"):
            build_pnpm_dependency_graph({"lockfileVersion": "4.0", "packages": {}})

    def test_newer_lockfile_versions_are_attempted_with_an_explicit_warning(self):
        # Refusing every future pnpm format would make the tool useless on the day pnpm bumps
        # the version; instead parse with the v9 rules, warn, and refuse only if the result is nonsense.
        graph = build_pnpm_dependency_graph({"lockfileVersion": "10.0", "packages": {}, "snapshots": {}})
        self.assertEqual([d.code for d in graph.diagnostics], ["LOCKFILE_VERSION_UNTESTED"])

    def test_yaml_parser(self):
        data = parse_pnpm_lockfile("lockfileVersion: '9.0'\nimporters:\n  .: {}\npackages: {}\nsnapshots: {}\n")
        self.assertEqual(data["lockfileVersion"], "9.0")

    def test_yaml_parser_merges_explicit_document_separator(self):
        raw = """lockfileVersion: '9.0'
importers:
  .:
    dependencies:
      foo:
        specifier: ^1.0.0
        version: 1.0.0
---
packages:
  foo@1.0.0: {}
snapshots:
  foo@1.0.0: {}
"""
        data = parse_pnpm_lockfile(raw)
        self.assertEqual(data["lockfileVersion"], "9.0")
        self.assertIn(".", data["importers"])
        self.assertIn("foo@1.0.0", data["packages"])
        self.assertIn("foo@1.0.0", data["snapshots"])
        graph = build_pnpm_dependency_graph(data)
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(graph.importer_dependencies["."]["foo"], "pnpm/foo@1.0.0")

    def test_yaml_parser_merges_realistic_pnpm_document_sections(self):
        # pnpm can emit a preliminary config/package-manager document followed
        # by the main workspace document. The root importer and package keys
        # can occur in both documents and must be merged recursively.
        raw = """lockfileVersion: '9.0'
importers:
  .:
    configDependencies:
      pnpm: 9.0.0
packages:
  pnpm@9.0.0:
    resolution:
      integrity: sha512-pnpm
snapshots:
  pnpm@9.0.0: {}
---
lockfileVersion: '9.0'
settings:
  autoInstallPeers: false
importers:
  .:
    dependencies:
      foo:
        specifier: ^1.0.0
        version: 1.0.0
packages:
  foo@1.0.0:
    resolution:
      integrity: sha512-foo
snapshots:
  foo@1.0.0:
    dependencies:
      pnpm: 9.0.0
"""
        data = parse_pnpm_lockfile(raw)
        self.assertEqual(data["lockfileVersion"], "9.0")
        self.assertEqual(data["importers"]["."]["configDependencies"]["pnpm"], "9.0.0")
        self.assertEqual(data["importers"]["."]["dependencies"]["foo"]["version"], "1.0.0")
        self.assertIn("pnpm@9.0.0", data["packages"])
        self.assertIn("foo@1.0.0", data["packages"])
        graph = build_pnpm_dependency_graph(data)
        self.assertEqual(graph.importer_dependencies["."]["foo"], "pnpm/foo@1.0.0")
        self.assertEqual(len(graph.edges), 1)

    def test_yaml_parser_rejects_conflicting_duplicate_leaf_values(self):
        raw = """lockfileVersion: '9.0'
settings:
  autoInstallPeers: true
---
lockfileVersion: '9.0'
settings:
  autoInstallPeers: false
"""
        with self.assertRaisesRegex(ValueError, "conflicting value.*settings.autoInstallPeers"):
            parse_pnpm_lockfile(raw)


if __name__ == "__main__":
    unittest.main()
