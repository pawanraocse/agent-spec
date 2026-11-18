# mesh-demo — four small repos that really depend on each other (H-010)

| Repo | Language | Depends on |
|------|----------|------------|
| `acme-common` | Python | — (shared library: `acme_common.money`, `acme_common.events`) |
| `orders-api` | Python (Flask-style routes) | imports `acme_common`; publishes `orders.created` |
| `orders-worker` | Python | imports `acme_common`; consumes `orders.created` |
| `shop-ui` | JavaScript | calls `orders-api` over HTTP (`GET /api/orders/{id}`, `POST /api/orders`) |

Build the mesh from any hub folder (each repo is used in place; nothing is written into it):

```bash
bash examples/mesh-demo/build.sh /tmp/mesh-hub
```

`graphify-mesh.py stats` then shows `imports`, `http` and `message` edges across repos, and
`graphify-mesh.py query --file orders-api:orders_api/routes.py` shows the cross-repo blast
radius the risk gate (P4-011) reads.
