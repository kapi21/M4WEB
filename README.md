# M4WEB

Proxy local + interfaz mejorada de la [M4 Board](https://www.cpcwiki.eu/index.php/M4_Board) (Amstrad CPC).

La web original vive en el firmware del ESP8266. **M4WEB** corre en tu PC, habla con la misma API (`config.cgi`, POST `/`, `/sd/…`) y ofrece una UI más usable con estética CPC (azul/amarillo).

## Requisitos

- Python 3.10+ (solo biblioteca estándar)
- M4 Board encendida y en la misma red

## Arranque (Windows)

```bat
m4web.bat
```

O:

```bat
set M4_HOST=http://192.168.1.128
python -m m4web
```

Abre `http://127.0.0.1:8787/`

## Variables de entorno

| Variable     | Default            | Uso                          |
|--------------|--------------------|------------------------------|
| `M4_HOST`    | `http://cpc6128`   | URL base de la M4            |
| `M4WEB_PORT` | `8787`             | Puerto del proxy local       |
| `M4_TIMEOUT` | `12`               | Timeout HTTP hacia la M4 (s) |

## Qué incluye

| Pestaña   | Función |
|-----------|---------|
| **Files** | Listar SD, subir (progreso / drag&drop), mkdir, borrar, Run, CD on CPC, entrar en `.DSK`/`.CPR` |
| **Roms**  | Config romboard, slots 0–31, upload/remove, cartucho |
| **Control** | M4/CPC Reset, Pause, Hack Menu, Start Cart, Run, CD |
| **Settings** | Reloj, NTP, NetBIOS, WiFi, red; password enmascarada |

## Estructura

```
M4WEB/
├── m4web/           # paquete Python
│   ├── m4_client.py # cliente HTTP → M4
│   ├── server.py    # proxy + /api/* + static
│   ├── static/      # UI nueva
│   └── original/    # copia de referencia de las .shtml (sanitizada)
├── m4web.bat
└── README.md
```

## Nota de seguridad

`m4web/original/` es una referencia de la UI del firmware. Los valores de WiFi/MAC/IP están **sanitizados**; no subas capturas reales de `settings.shtml` con tu contraseña.

## Licencia

Código de M4WEB: uso libre en proyectos personales/retro. La M4 Board y su firmware son de Duke / spinpoint.org.
