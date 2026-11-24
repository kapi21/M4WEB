# HANDOFF - M4WEB

_Última actualización: 2026-11-24_

## Objetivo
Proxy local + UI mejorada de la web de la M4 Board (Amstrad CPC), listo para publicar en GitHub.

## Estado
- Hecho: proyecto en GitHub; paquete `m4web`, launcher, README; settings original sanitizado
- Pendiente: feedback de uso real / pulir UX
- Bloqueos / dudas: ninguno

## Repo
https://github.com/kapi21/M4WEB

## Decisiones tomadas
- Proyecto aparte (no acoplado a SINTAXIA)
- Solo stdlib Python
- Credenciales reales fuera del repo (placeholders en `original/`)

## Archivos y carpetas clave
- `m4web/`: código y UI
- `m4web.bat`: arranque en Windows
- `README.md`: uso público

## Cómo verificar / retomar
```bat
cd "C:\@MIS PROYECTOS\M4WEB"
set M4_HOST=http://192.168.1.128
python -m m4web --no-browser
curl http://127.0.0.1:8787/api/status
```

## Riesgos
- Subir a GitHub una captura no sanitizada de Settings con WiFi en claro

## Historial
- 2026-11-24: creado proyecto M4WEB; publicado en https://github.com/kapi21/M4WEB
