"""P3-001: multi-repo Graphify mesh (bin/graphify-mesh.py, graphify-build.py --out)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESH = os.path.join(REPO_DIR, "bin", "graphify-mesh.py")
BUILD = os.path.join(REPO_DIR, "bin", "graphify-build.py")


def java(root, fqn, imports=()):
    pkg, cls = fqn.rsplit(".", 1)
    path = os.path.join(root, "src", "main", "java", *pkg.split("."), cls + ".java")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = "package %s;\n\n%s\npublic class %s {}\n" % (
        pkg, "".join("import %s;\n" % i for i in imports), cls)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


class GraphMeshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.hub = os.path.join(self.tmp, "hub")
        os.makedirs(self.hub)
        r = lambda name: os.path.join(self.tmp, name)  # noqa: E731
        java(r("lib"), "com.acme.lib.Strings")
        java(r("lib"), "com.acme.lib.Dates", ["com.acme.lib.Strings"])
        java(r("svc"), "com.acme.svc.App", ["com.acme.lib.Strings", "java.util.List", "org.slf4j.Logger"])
        java(r("web"), "com.acme.web.Page", ["com.acme.svc.App", "util.Strings"])
        java(r("other"), "util.Strings")  # same simple name, unrelated package
        java(r("other"), "com.other.Use", ["lib.Strings"])  # a path suffix of lib's file, not an FQN
        java(r("other"), "com.other.java.inner.Deep")  # a package segment named java
        self.repos = {n: r(n) for n in ("lib", "svc", "web", "other")}

    def mesh(self, *args):
        p = subprocess.run([sys.executable, MESH, *args], cwd=self.hub, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        return p.stdout

    def add_all(self, names=("lib", "svc", "web", "other")):
        for n in names:
            self.mesh("add", self.repos[n])

    def test_add_writes_manifest_and_member_graph_without_touching_the_member(self):
        self.mesh("add", self.repos["lib"])
        with open(os.path.join(self.hub, ".agent-spec", "mesh.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        entry = manifest["repos"][0]
        self.assertEqual(entry["repo_id"], "lib")
        self.assertEqual(entry["path"], self.repos["lib"])
        self.assertEqual(len(entry["graph_sha"]), 40)
        self.assertTrue(entry["updated"].endswith("Z"))
        graph = os.path.join(self.hub, ".agent-spec", "mesh", "lib", "knowledge-graph.json")
        self.assertTrue(os.path.isfile(graph))
        self.assertFalse(os.path.exists(os.path.join(self.repos["lib"], ".agent-spec")))

    def test_build_links_repos_by_exact_fqn_only(self):
        self.add_all()
        self.mesh("build")
        with open(os.path.join(self.hub, ".agent-spec", "graph", "mesh-graph.json"), encoding="utf-8") as fh:
            g = json.load(fh)
        cross = sorted((e["source"], e["target"]) for e in g["edges"] if e.get("cross_repo"))
        self.assertEqual(cross, [
            ("svc:src/main/java/com/acme/svc/App.java", "lib:src/main/java/com/acme/lib/Strings.java"),
            ("web:src/main/java/com/acme/web/Page.java", "other:src/main/java/util/Strings.java"),
            ("web:src/main/java/com/acme/web/Page.java", "svc:src/main/java/com/acme/svc/App.java"),
        ])
        # util.Strings is a real FQN in `other`, so it links. `java.util.List` and
        # `org.slf4j.Logger` never link, and no path suffix such as `lib.Strings` is a name.
        self.assertFalse(any("slf4j" in e.get("detail", "") or "java.util" in e.get("detail", "")
                             for e in g["edges"]))
        intra = [e for e in g["edges"] if not e.get("cross_repo")]
        self.assertIn({"source": "lib:src/main/java/com/acme/lib/Dates.java",
                       "target": "lib:src/main/java/com/acme/lib/Strings.java", "type": "imports"},
                      [{k: e[k] for k in ("source", "target", "type")} for e in intra])
        self.assertTrue(all(n["id"].startswith(n["repo"] + ":") for n in g["nodes"]))

    def test_qualified_names_use_the_first_source_root(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mesh", MESH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        q = mod.qualified_names
        self.assertEqual(q("src/main/java/com/z/java/bridge/X.java", set()), ["com.z.java.bridge.X"])
        self.assertEqual(q("src/java/com/z/A.java", set()), ["com.z.A"])
        self.assertEqual(q("pkg/sub/mod.py", {"pkg", "pkg/sub"}), ["pkg.sub.mod"])
        self.assertEqual(q("tools/pkg/__init__.py", {"tools/pkg"}), [])  # single segment
        self.assertEqual(q("web/app.ts", set()), [])

    def test_stats_reports_three_repos_in_one_component(self):
        self.add_all(("lib", "svc", "web"))
        self.mesh("build")
        out = json.loads(self.mesh("stats", "--json"))
        self.assertEqual(out["repos"], 3)
        self.assertEqual(out["largest_component"], ["lib", "svc", "web"])
        self.assertEqual(out["pairs"], {"svc->lib": 1, "web->svc": 1})

    def test_same_fqn_in_two_repos_is_ambiguous(self):
        java(os.path.join(self.tmp, "fork"), "com.acme.lib.Strings")
        self.repos["fork"] = os.path.join(self.tmp, "fork")
        self.add_all(("lib", "svc", "fork"))
        self.mesh("build")
        with open(os.path.join(self.hub, ".agent-spec", "graph", "mesh-graph.json"), encoding="utf-8") as fh:
            g = json.load(fh)
        amb = [e for e in g["edges"] if e["type"] == "imports_ambiguous" and e.get("cross_repo")]
        self.assertEqual(sorted(e["target"].split(":")[0] for e in amb), ["fork", "lib"])
        self.assertFalse(any(e["type"] == "imports" and e.get("cross_repo") for e in g["edges"]))

    def test_duplicate_id_is_refused_and_remove_drops_the_member(self):
        self.mesh("add", self.repos["lib"])
        p = subprocess.run([sys.executable, MESH, "add", self.repos["svc"], "--id", "lib"], cwd=self.hub,
                           capture_output=True, text=True, timeout=60)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("already in the mesh", p.stdout + p.stderr)
        self.mesh("remove", "lib")
        with open(os.path.join(self.hub, ".agent-spec", "mesh.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["repos"], [])

    def test_build_out_leaves_project_index_alone(self):
        out = os.path.join(self.tmp, "outdir")
        subprocess.run([sys.executable, BUILD, "--quiet", "--out", out], cwd=self.repos["svc"], check=True,
                       timeout=60)
        with open(os.path.join(out, "knowledge-graph.json"), encoding="utf-8") as fh:
            g = json.load(fh)
        self.assertIn("com.acme.lib.Strings", g["unresolved_imports"])
        self.assertNotIn("java.util.List", g["unresolved_imports"])
        for bad in ("AtlBase.h", "Ext.slider.*"):
            self.assertFalse(self.build_mod().mesh_candidate(bad), bad)
        self.assertFalse(os.path.exists(os.path.join(self.repos["svc"], ".agent-spec")))

    def build_mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gbuild", BUILD)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def write(root, rel, body):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


def mesh_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gmesh", MESH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


J = "src/main/java/com/acme/%s/%s.java"


class MeshHttpMessageTest(unittest.TestCase):
    """P3-002 step 3: cross-repo http and message edges, and graphify-mesh.py query."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.hub = os.path.join(self.tmp, "hub")
        os.makedirs(os.path.join(self.hub, ".agent-spec"))
        r = lambda name: os.path.join(self.tmp, name)  # noqa: E731
        write(r("billing"), J % ("billing", "InvoiceController"),
              "package com.acme.billing;\nimport org.springframework.web.bind.annotation.*;\n"
              "@RestController\n@RequestMapping(\"/api/invoices\")\npublic class InvoiceController {\n"
              "  @GetMapping(\"/{id}\")\n  public String get(String id) { return id; }\n"
              "  @PostMapping\n  public void create() {}\n}\n")
        write(r("billing"), J % ("billing", "OrderListener"),
              "package com.acme.billing;\npublic class OrderListener {\n"
              "  @KafkaListener(topics = \"order.placed\")\n  public void on(String m) {}\n}\n")
        write(r("orders"), J % ("orders", "BillingClient"),
              "package com.acme.orders;\n@FeignClient(name = \"billing\")\npublic interface BillingClient {\n"
              "  @GetMapping(\"/api/invoices/{id}\")\n  String invoice(String id);\n"
              "  @GetMapping(\"/unknown/thing\")\n  String other();\n}\n")
        write(r("orders"), J % ("orders", "OrderService"),
              "package com.acme.orders;\nimport com.acme.orders.BillingClient;\npublic class OrderService {\n"
              "  void place() { kafkaTemplate.send(\"order.placed\", \"x\"); }\n}\n")
        write(r("orders"), J % ("orders", "Calls"),
              "package com.acme.orders;\npublic class Calls {\n  void go() {\n"
              "    restTemplate.getForObject(\"http://localhost:8080/api/invoices/1\", String.class);\n"
              "    restTemplate.getForObject(\"https://api.stripe.com/v1/charges\", String.class);\n"
              "    restTemplate.getForObject(\"http://billing-gw/api/invoices/2\", String.class);\n"
              "    restTemplate.getForObject(\"http://billing.prod.svc.cluster.local/api/invoices/3\", String.class);\n"
              "    restTemplate.getForObject(\"http://billing/edge/v2/api/invoices/4\", String.class);\n"
              "  }\n}\n")
        write(r("web"), "src/app.js",
              "export const a = () => fetch('/api/invoices/42');\nexport const b = () => fetch('/health');\n")
        with open(os.path.join(self.hub, ".agent-spec", "mesh-aliases.json"), "w", encoding="utf-8") as fh:
            json.dump({"billing-gw": "billing", "typo-gw": "no-such-repo"}, fh)
        for n in ("billing", "orders", "web"):
            self.mesh("add", r(n))
        self.mesh("build")
        with open(os.path.join(self.hub, ".agent-spec", "graph", "mesh-graph.json"), encoding="utf-8") as fh:
            self.edges = [e for e in json.load(fh)["edges"] if e.get("cross_repo")]

    def mesh(self, *args):
        p = subprocess.run([sys.executable, MESH, *args], cwd=self.hub, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        return p.stdout

    def find(self, **kw):
        return [e for e in self.edges if all(e.get(k) == v for k, v in kw.items())]

    def test_feign_client_matches_the_route_by_service_name(self):
        hit = self.find(source="orders:" + J % ("orders", "BillingClient"), detail="GET /api/invoices/{id}")
        self.assertEqual([(e["type"], e["target"]) for e in hit],
                         [("http", "billing:" + J % ("billing", "InvoiceController"))])

    def test_known_service_without_a_matching_route_is_a_repo_level_edge(self):
        hit = self.find(detail="GET /unknown/thing")
        self.assertEqual([(e["target"], e.get("resolution")) for e in hit], [("billing", "service")])

    def test_alias_k8s_host_and_gateway_prefix_resolve_while_loopback_and_third_party_do_not(self):
        calls = "orders:" + J % ("orders", "Calls")
        ctrl = "billing:" + J % ("billing", "InvoiceController")
        got = {e["detail"]: (e["type"], e["target"]) for e in self.find(source=calls)}
        self.assertEqual(got, {"GET /api/invoices/2": ("http", ctrl), "GET /api/invoices/3": ("http", ctrl),
                               "GET /edge/v2/api/invoices/4": ("http", ctrl)})

    def test_topic_joins_producer_and_consumer_across_repos(self):
        hit = self.find(type="message", detail="order.placed")
        self.assertEqual([(e["source"], e["target"]) for e in hit],
                         [("orders:" + J % ("orders", "OrderService"), "billing:" + J % ("billing", "OrderListener"))])

    def test_relative_fetch_is_only_ever_ambiguous_and_needs_two_literal_segments(self):
        hit = self.find(source="web:src/app.js")
        self.assertEqual([(e["type"], e["confidence"], e["detail"]) for e in hit],
                         [("http_ambiguous", "low", "GET /api/invoices/42")])

    def test_stats_counts_http_and_message_and_connects_three_repos(self):
        s = json.loads(self.mesh("stats", "--json"))
        self.assertEqual(s["largest_component"], ["billing", "orders"])  # web's edge is ambiguous
        self.assertEqual(s["by_type"]["message"], 1)
        self.assertEqual(s["by_type"]["http_ambiguous"], 1)
        self.assertEqual(s["cross_repo_edges"], s["by_type"]["http"] + 1)

    def test_query_walks_the_blast_radius_across_repos(self):
        ctrl = "billing:" + J % ("billing", "InvoiceController")
        q = json.loads(self.mesh("query", "--file", ctrl, "--json"))
        radius = {b["file"]: b["depth"] for b in q["blast_radius"]}
        self.assertEqual(radius["orders:" + J % ("orders", "BillingClient")], 1)
        self.assertEqual(radius["orders:" + J % ("orders", "OrderService")], 2)  # imports the client
        self.assertNotIn("web:src/app.js", radius)  # ambiguous edges never widen the radius
        self.assertEqual(q["repos_affected"], ["orders"])
        self.assertIn("depended on by, from other repos", self.mesh("query", "--file", J % ("billing", "InvoiceController")))

    def test_path_matching_rules(self):
        m = mesh_mod()
        self.assertTrue(m.path_match("/a/42/b", "/a/{id}/b"))
        self.assertTrue(m.path_match("/a/:id", "/a/{x}"))
        self.assertTrue(m.path_match("/files/x/y", "/files/*"))
        self.assertTrue(m.path_match("/x/page.do", "/x/*.do"))
        self.assertFalse(m.path_match("/a/b", "/a"))
        self.assertTrue(m.suffix_match("/gw/a/b", "/a/b"))
        self.assertFalse(m.suffix_match("/gw/a/42", "/{id}"))
        names = {"api": {"api"}, "billing": {"billing"}}
        self.assertEqual(m.resolve_target("api.example.com", names), set())
        self.assertEqual(m.resolve_target("billing.ns.svc", names), {"billing"})


if __name__ == "__main__":
    unittest.main()
