# Perfil local y recuperación

El backend guarda `<JOBHUNTER_DATA_DIR>/profile.json` (por defecto `data/profile.json`). El MVP Streamlit mantiene su compatibilidad. No se requiere migración SQLite para los campos de M1.4.

## Primera configuración

Si no existe perfil, el panel abre Mi perfil con un asistente de siete pasos opcionales. No presupone cargos ni habilidades y activa feed + API Get on Board solo en la plantilla nueva. Los perfiles existentes conservan fuentes y no son obligados a usar el asistente. «Abrir asistente» lo invoca de nuevo con el perfil guardado.

El borrador vive en memoria hasta «Guardar perfil». Anterior/Siguiente conserva sus datos; el resumen permite volver a editar. Cancelar no escribe. Es posible guardar un perfil parcial y completarlo después. Salir de la página o cerrar la app descarta cambios sin guardar. Cancelar suspende la redirección automática durante esa pestaña, sin almacenar información profesional en sessionStorage. Un error de guardado muestra el mensaje y conserva el borrador; no muestra éxito.

Los campos de Mi perfil incluyen áreas, experiencia (tipo empleo/práctica/proyecto/voluntariado/por confirmar), formación con estado, habilidades declaradas, aprendizaje, evidencia por habilidad, idiomas con nivel y evidencia opcional, zonas permitidas, modalidad, seniority, relocalización, renta opcional con moneda y periodicidad, notas y fuentes. Un proyecto no se transforma en años de empleo; «en curso» no se transforma en título completado. Las notas de residencia son información para revisión manual, no autorización para trabajar.

## Escritura y respaldo

Se valida y serializa antes de tocar el archivo; se crea un temporal en el mismo directorio, se hace flush/fsync y se sustituye con os.replace. La versión válida anterior se conserva en `profile.json.bak`, también mediante temporal y sustitución atómica. Hay reintentos breves ante PermissionError en Windows. Un fallo de validación/escritura/reemplazo no modifica el perfil actual ni informa éxito. Si el reemplazo final falla tras actualizar .bak, ambos contienen la versión actual válida. No es una garantía contra fallos físicos del disco.

La carga corrupta no escribe ni restaura automáticamente; el panel informa el problema y no abre el asistente. El guardado explícito desde API sobre un archivo dañado conserva una copia `.corrupt-<fecha>` y no reemplaza el respaldo válido por basura. Las claves heredadas desconocidas del nivel superior y fuentes se conservan desde el servidor; un cliente no puede agregar claves arbitrarias nuevas por PUT /api/profile.

## Recuperación manual

1. Cierra JobHunter y conserva una copia del archivo dañado con otro nombre. No borres el único archivo disponible.
2. Revisa `profile.json.bak` localmente, sin subirlo ni compartirlo. Debe ser un objeto JSON y un perfil válido; GET /api/profile/status informa si detecta una copia legible.
3. Copia (no muevas) la copia válida sobre `profile.json`, manteniendo `.bak` y el dañado aparte. Usa la carpeta que hayas configurado, no necesariamente `data/`.
4. Inicia la app y revisa Mi perfil antes de guardar. Si no tienes copia válida, conserva los archivos para recuperación y crea después un perfil nuevo explícitamente con datos revisados.

No uses datos personales como fixtures. Para verificar sin tocar tu perfil: `JOBHUNTER_DATA_DIR=$(mktemp -d) .venv/bin/python -m pytest -q`; el smoke automatizado usa su propio TemporaryDirectory: `.venv/bin/python scripts/smoke_m14.py`.

## Ranking y caché

El ranking conserva score 0–100 y umbral configurable. Modalidad confirmada afín +6; modalidad distinta −8; desconocida avisa sin sumar. La elegibilidad geográfica se evalúa aparte con sus tres estados y restricciones explícitas prioritarias. Se prioriza nivel estructurado frente al título; sin nivel no se descarta un N1/N2. Las penalizaciones por seniority/años usan la mayor, no la suma.

Idiomas: requisitos de idiomas reconocidos y niveles explícitos se contrastan con declaraciones; solo CEFR se compara ordinalmente con CEFR. «Fluent», «avanzado» y otros textos requieren revisión manual. Evidencia aportada no equivale a certificación validada. Las palabras técnicas en inglés no declaran por sí solas requisitos de idioma.

Remuneración: solo se compara el formato explícito `Renta: mínimo - máximo MONEDA/mes` (o salary/salario/remuneración, /año, /month, /year). La API actual de Get on Board usa USD/mes. Monedas/periodicidades diferentes, rangos ausentes o formatos no reconocidos generan revisión; no se convierten divisas ni se descartan ofertas por ello. Confirmar siempre bruto/neto.

Requisitos: solo marcadores explícitos `Obligatorio:`, `Required:`, `Deseable:`, etc. generan clasificación. Se muestran fragmento literal, coincidencias declaradas y brechas por confirmar; no se afirma cumplimiento completo. El aprendizaje no suma coincidencias dominadas; la evidencia es la declaración del usuario. Idioma, renta y requisitos agregan explicaciones sin penalización adicional.

La caché usa perfil completo más título/descripción/ubicación/geografía de la oferta; cambiar preferencias o contenido la invalida. No se persisten puntajes ni se necesita migrar la base. Comparación sintética reproducible: `.venv/bin/python scripts/eval_m14.py`.
