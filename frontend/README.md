# Frontend de Infia

La interfaz interactiva usa React, Vite, React Router, Tailwind CSS y Motion. Flask sigue gestionando las sesiones, las reglas de negocio, PostgreSQL y las APIs.

## Desarrollo

Desde esta carpeta, ejecutá `npm ci` y `npm run dev`. Vite sirve el frontend en `http://127.0.0.1:5173` y reenvía las llamadas `/api` a Flask en el puerto 5000.

## Build para Flask

Ejecutá `npm run build` antes de publicar cambios del frontend. Vite genera `../static/react-app`; esos archivos de producción se versionan para que el servicio Python de Render pueda servirlos sin instalar Node durante el deploy.

Las APIs y rutas de aplicación se sirven en el mismo dominio para conservar las cookies de sesión y el comportamiento de la PWA.
