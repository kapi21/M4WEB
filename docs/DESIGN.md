# Diseño M4WEB

Proxy Python en el PC + front estático. La M4 no se modifica.

```
Navegador → localhost:8787 → M4_HOST (http://cpc6128 o IP)
              ├─ static UI
              └─ /api/* → m4_client → config.cgi, POST /, /sd/, …
```

Detalle acordado en el workspace SINTAXIA/M4: `docs/superpowers/specs/2026-11-24-m4web-proxy-design.md` (origen del diseño).
