"""P3-002 step 1: endpoint routes and HTTP clients extracted by graphify-build."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(REPO_DIR, "bin", "graphify-build.py")


def load_build():
    spec = importlib.util.spec_from_file_location("graphify_build", BUILD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = load_build()


def routes(src):
    return B.extract_signals(textwrap.dedent(src))["routes"]


class RouteExtractionTest(unittest.TestCase):
    def test_jaxrs_joins_class_prefix_and_reads_verbs(self):
        src = """
            import jakarta.ws.rs.*;

            @Path("/api/assets")
            @Produces("application/json")
            public class AssetResource {
                @GET
                @Path("{id}")
                public Asset get(@PathParam("id") String id) { return null; }

                @POST
                public Asset create(Asset a) { return a; }

                @Path("sub")
                public SubResource sub() { return null; }
            }
        """
        self.assertEqual(routes(src), ["ANY /api/assets/sub", "GET /api/assets/{id}", "POST /api/assets"])

    def test_jaxrs_needs_the_ws_rs_namespace(self):
        self.assertEqual(routes('@Path("/x")\nclass A { @GET void a() {} }'), [])

    def test_spring_class_prefix_verbs_and_arrays(self):
        src = """
            import org.springframework.web.bind.annotation.*;

            @RestController
            @RequestMapping("/v1")
            public class OrderController {
                @GetMapping("/a")
                public String a() { return ""; }

                @PostMapping
                public String create() { return ""; }

                @RequestMapping(value = "/b", method = RequestMethod.PUT)
                public String b() { return ""; }

                @GetMapping({"/c", "/d"})
                public String cd() { return ""; }

                @DeleteMapping(path = "/e/{id}")
                public void e() {}
            }
        """
        self.assertEqual(routes(src), ["DELETE /v1/e/{id}", "GET /v1/a", "GET /v1/c", "GET /v1/d",
                                       "POST /v1", "PUT /v1/b"])

    def test_spring_controller_name_is_not_a_prefix(self):
        src = """
            import org.springframework.stereotype.Controller;
            @Controller("homeController")
            public class Home {
                @GetMapping("/home")
                public String home() { return "home"; }
            }
        """
        self.assertEqual(routes(src), ["GET /home"])

    def test_micronaut_controller(self):
        src = """
            import io.micronaut.http.annotation.*;
            @Controller("/hello")
            public class HelloController {
                @Get("/{name}")
                public String hi(String name) { return name; }
            }
        """
        self.assertEqual(routes(src), ["GET /hello/{name}"])

    def test_nestjs_controller_without_leading_slashes(self):
        src = """
            import { Controller, Get, Post } from '@nestjs/common';

            @Controller('cats')
            export class CatsController {
              @Get(':id')
              findOne() {}

              @Post()
              create() {}
            }
        """
        self.assertEqual(routes(src), ["GET /cats/:id", "POST /cats"])

    def test_servlet_annotation(self):
        src = """
            import javax.servlet.annotation.WebServlet;
            @WebServlet(name = "up", urlPatterns = {"/upload", "/upload/*"})
            public class UploadServlet extends HttpServlet {}
        """
        self.assertEqual(routes(src), ["ANY /upload", "ANY /upload/*"])
        self.assertEqual(routes('import javax.servlet.annotation.*;\n@WebServlet("/x")\nclass X {}'), ["ANY /x"])

    def test_function_frameworks_keep_their_verbs(self):
        self.assertEqual(routes("app.get('/health', h)\nrouter.use('/api', r)\n"),
                         ["ANY /api", "GET /health"])
        self.assertEqual(routes('@app.post("/items")\ndef create(): ...\n@router.get("/x")\ndef x(): ...\n'),
                         ["GET /x", "POST /items"])
        self.assertEqual(routes('http.HandleFunc("/metrics", m)'), ["ANY /metrics"])

    def test_endpoints_stay_distinct_paths(self):
        sig = B.extract_signals('import jakarta.ws.rs.*;\n@Path("/a")\nclass A {\n@GET\nvoid g(){}\n@POST\nvoid p(){}\n}')
        self.assertEqual(sig["endpoints"], ["/a"])
        self.assertEqual(sig["routes"], ["GET /a", "POST /a"])


class ClientExtractionTest(unittest.TestCase):
    def test_rest_client_config_key_is_a_call_target(self):
        src = '@RegisterRestClient(configKey = "platform-service")\npublic interface PlatformApi {}'
        self.assertIn("platform-service", B.extract_signals(src)["calls"])

    def test_java_http_clients_count_as_dynamic(self):
        for src in ("HttpClient client = HttpClient.newHttpClient();",
                    "Client c = ClientBuilder.newClient();",
                    "HttpURLConnection con = (HttpURLConnection) url.openConnection();",
                    "OkHttpClient c = new OkHttpClient();"):
            self.assertEqual(B.extract_signals(src)["calls"], ["[dynamic]"], src)


def calls(src):
    return B.extract_signals(textwrap.dedent(src))["http_calls"]


def C(verb, target, path, via):
    return {"verb": verb, "target": target, "path": path, "via": via}


class StructuredCallTest(unittest.TestCase):
    def test_feign_interface_is_a_client_not_a_server(self):
        src = """
            import org.springframework.cloud.openfeign.FeignClient;
            @FeignClient(name = "inventory-service", path = "/api/stock")
            public interface StockClient {
                @GetMapping("/{sku}")
                Stock get(@PathVariable String sku);

                @PostMapping
                void reserve(Stock s);
            }
        """
        sig = B.extract_signals(textwrap.dedent(src))
        self.assertEqual(sig["routes"], [])
        self.assertEqual(sig["http_calls"], [C("GET", "inventory-service", "/api/stock/{sku}", "feign"),
                                             C("POST", "inventory-service", "/api/stock", "feign")])
        self.assertIn("inventory-service", sig["calls"])

    def test_feign_url_and_placeholder_targets(self):
        self.assertEqual(calls('@FeignClient(url = "http://Pricing:8080")\ninterface P {\n@GetMapping("/p")\nX p();\n}'),
                         [C("GET", "pricing", "/p", "feign")])
        self.assertEqual(calls('@FeignClient(name = "x", url = "${pricing.url}")\ninterface P {\n@GetMapping("/p")\nX p();\n}'),
                         [C("GET", "config:pricing.url", "/p", "feign")])

    def test_microprofile_rest_client_interface(self):
        src = """
            import jakarta.ws.rs.*;
            @RegisterRestClient(configKey = "platform-service")
            @Path("/v1/tenants")
            public interface TenantApi {
                @GET
                @Path("{id}")
                Tenant get(@PathParam("id") String id);
            }
        """
        sig = B.extract_signals(textwrap.dedent(src))
        self.assertEqual(sig["routes"], [])
        self.assertEqual(sig["http_calls"], [C("GET", "platform-service", "/v1/tenants/{id}", "rest-client")])

    def test_literal_urls_take_the_verb_on_their_line(self):
        src = """
            Invoice i = restTemplate.getForObject("http://billing-service/api/invoices/{id}?x=1", Invoice.class, id);
            restTemplate.exchange("http://billing-service/api/invoices", HttpMethod.PUT, req, Void.class);
            webClient.post().uri("lb://audit-service/events").retrieve();
            String docs = "https://docs.example.com";
        """
        self.assertEqual(calls(src), [
            C("ANY", "docs.example.com", "/", "url"),
            C("GET", "billing-service", "/api/invoices/{id}", "url"),
            C("POST", "audit-service", "/events", "url"),
            C("PUT", "billing-service", "/api/invoices", "url"),
        ])

    def test_python_and_js_calls(self):
        self.assertEqual(calls('r = requests.post("http://auth-service/token", data=d)'),
                         [C("POST", "auth-service", "/token", "url")])
        self.assertEqual(calls("fetch('/api/users')\naxios.post('/api/login', body)\naxios.get(`${BASE}/x`)\n"),
                         [C("GET", "", "/api/users", "fetch"), C("POST", "", "/api/login", "fetch")])

    def test_url_literals_count_only_in_files_that_make_http_calls(self):
        xml = 'Element e = doc.createElementNS("http://www.w3.org/2000/svg", "svg");\nString help = "https://docs.example.com/x";'
        self.assertEqual(calls(xml), [])
        client = 'String base = "http://billing-service/api";\nHttpClient c = HttpClient.newHttpClient();'
        self.assertEqual(calls(client), [C("ANY", "billing-service", "/api", "url")])

    def test_calls_are_capped(self):
        src = "\n".join('fetch("/p%d")' % i for i in range(150))
        self.assertEqual(len(calls(src)), 100)


class WebXmlBuildTest(unittest.TestCase):
    def test_web_xml_mappings_attach_to_the_servlet_class(self):
        root = tempfile.mkdtemp()
        java = os.path.join(root, "src", "main", "java", "com", "acme", "web")
        os.makedirs(java)
        with open(os.path.join(java, "Upload.java"), "w") as fh:
            fh.write("package com.acme.web;\npublic class Upload extends HttpServlet {}\n")
        winf = os.path.join(root, "src", "main", "webapp", "WEB-INF")
        os.makedirs(winf)
        with open(os.path.join(winf, "web.xml"), "w") as fh:
            fh.write("""<web-app>
  <servlet><servlet-name>up</servlet-name><servlet-class>com.acme.web.Upload</servlet-class></servlet>
  <servlet-mapping><servlet-name>up</servlet-name><url-pattern>/upload/*</url-pattern></servlet-mapping>
  <servlet-mapping><servlet-name>up</servlet-name><url-pattern>*.up</url-pattern></servlet-mapping>
  <servlet><servlet-name>gone</servlet-name><servlet-class>com.acme.Missing</servlet-class></servlet>
  <servlet-mapping><servlet-name>gone</servlet-name><url-pattern>/gone</url-pattern></servlet-mapping>
</web-app>""")
        out = os.path.join(root, "out")
        subprocess.run([sys.executable, BUILD, "--quiet", "--out", out], cwd=root, check=True,
                       capture_output=True, timeout=60)
        with open(os.path.join(out, "knowledge-graph.json"), encoding="utf-8") as fh:
            g = json.load(fh)
        self.assertEqual(g["version"], "5.3")
        self.assertIn("http_calls", node := next(n for n in g["nodes"] if n["path"].endswith("Upload.java")))
        node = next(n for n in g["nodes"] if n["path"].endswith("Upload.java"))
        self.assertEqual(node["routes"], ["ANY *.up", "ANY /upload/*"])
        self.assertEqual(node["endpoints"], ["*.up", "/upload/*"])
        self.assertFalse(any("/gone" in n.get("endpoints", []) for n in g["nodes"]))


if __name__ == "__main__":
    unittest.main()
