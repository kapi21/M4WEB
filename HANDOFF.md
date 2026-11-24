# HANDOFF - M4WEB

_Última actualización: 2026-11-24 (cierre de sesión)_

## Objetivo
Proxy local + UI mejorada de la web de la M4 Board (Amstrad CPC).

## Estado
- Hecho: v0.1 en GitHub (`master`); Files/Roms/Control/Settings; stdlib only; `original/` sanitizado
- Pendiente: uso real → pulir UX / atajos (p. ej. subir BAS + Run)
- Bloqueos / dudas: ninguno

## Repo
https://github.com/kapi21/M4WEB

## Decisiones tomadas
- Proyecto aparte de SINTAXIA (no acoplado al server de aventura)
- Fachada en PC; firmware M4 intacto
- Look CPC azul/amarillo; password enmascarada en Settings

## Archivos y carpetas clave
- `m4web/m4_client.py`, `m4web/server.py`, `m4web/static/`
- `m4web.bat` — arranque Windows
- `docs/DESIGN.md` — arquitectura breve

## Cómo verificar / retomar
```bat
cd "C:\@MIS PROYECTOS\M4WEB"
set M4_HOST=http://192.168.1.128
m4web.bat
```
Abrir `http://127.0.0.1:8787/` — status debe mostrar M4 OK.

## Riesgos
- No subir capturas reales de Settings con WiFi en claro

## Historial
- 2026-11-24: creado y publicado https://github.com/kapi21/M4WEB; cierre de sesión
