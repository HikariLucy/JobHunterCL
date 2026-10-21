# Análisis de puntuaciones — 326 ofertas de Get on Board

Fecha: 2026-10-21. Insumo para M1 («Mejorar ranking»). Las secciones «Distribución» a «Defectos concretos» describen el algoritmo **anterior**; los resultados de M1 están al final.

## Método

- Una descarga del feed público de Get on Board (326 ofertas, 326 URL únicas), guardada solo en una carpeta temporal fuera del repositorio. Nada se escribió en `data/`.
- Perfil de prueba: `DEFAULT_PROFILE` de `jobhunter/config.py` (el equipo no tiene `data/profile.json`, así que es también el perfil efectivo de la app). No se usó ningún perfil ni CV personal.
- Referencia de relevancia: el campo `Nivel` que Get on Board antepone a cada descripción (`Nivel: … · Jornada: … · Categoría: …`), más revisión manual de títulos y categorías.
- Los casos representativos quedaron como pruebas sintéticas en `tests/test_matching_cases.py` (sin texto copiado ni empresas).

## Distribución

| Puntaje | Ofertas |
|---|---|
| 0 | 176 |
| 1–9 | 86 |
| 10–19 | 24 |
| 20–29 | 29 |
| 30–39 | 5 |
| 40–49 | 5 |
| 60–69 | 1 |

11 ofertas (3,4 %) superan el umbral de 30.

| Nivel según la fuente | Ofertas | Puntaje medio | ≥ 30 |
|---|---|---|---|
| Senior | 198 | 4,3 | 4 |
| Semi Senior | 103 | 10,2 | 3 |
| Junior | 14 | 19,8 | 4 |
| Expert | 9 | 0,9 | 0 |
| Sin experiencia requerida | 2 | 4,0 | 0 |

El 95 % del feed es Semi Senior o superior: para un perfil inicial el volumen útil es bajo por naturaleza de la fuente, no solo por el ranking.

## Motivos y advertencias

| Señal | Ofertas | Lectura |
|---|---|---|
| Ubicación/modalidad de interés (+8) | 282 | No discrimina: casi todo es «Remoto» o incluye Chile. |
| Coincidencias técnicas | 154 | python 62, sql 52, git 44, docker 32, postgresql 30, soporte 19, linux 16, redes 10, fastapi 5. |
| Nivel inicial indicado (+18) | 6 | Solo se busca en el título. |
| Cargo objetivo / similar | 0 / 1 | Los títulos configurados casi nunca aparecen literalmente. |
| Cargo senior/liderazgo (−48) | 136 | Solo en el título. |
| 5+ años de experiencia (−24) | 96 | Incluye falsos positivos (ver abajo). |
| Inglés exigido | 17 | |

## Falsos positivos (≥ 30 pero no adecuados a un perfil inicial)

De las 11 ofertas sobre el umbral: **4 Junior** (adecuadas), **3 Semi Senior** (dudosas) y **4 Senior** (falsos positivos). Precisión estricta ≈ 36 %.

Causa principal: el nivel solo se detecta en el título. **92 de 207** ofertas Senior/Expert no tienen la palabra en el título y no reciben penalización; si además coinciden 4–5 habilidades (+28/+35) y la ubicación (+8) superan el umbral.

## Falsos negativos (adecuadas pero < 30)

De 16 ofertas Junior / Sin experiencia, 7 son de TI. 4 superan el umbral; 3 no (puntajes 15, 15 y 26): desarrollo .NET, front-end Angular/Flutter y front-end WordPress. Recall en TI inicial ≈ 57 %.

Causa: **10 de 16** ofertas de nivel inicial no dicen «junior» en el título y no reciben la bonificación de +18. Las tecnologías no coinciden con el perfil de prueba, por lo que parte de esto depende del perfil.

## Defectos concretos

| # | Defecto (corregido en M1 salvo el 8) | Ejemplo observado | Prueba |
|---|---|---|---|
| 1 | Nivel leído solo del título | Senior sin «senior» en el título | `test_senior_level_field_is_penalized` |
| 2 | Ídem para nivel inicial | Junior sin «junior» en el título | `test_junior_level_field_counts_as_entry_level` |
| 3 | `norm()` descarta caracteres no ASCII, incluido el guion largo | «1–3 years» → «13 years» → advertencia 5+ años | `test_year_range_with_en_dash_is_not_five_plus` |
| 4 | Cualquier «N años» es experiencia | «mayor de 18 años», «más de 12 años creciendo» (antigüedad de la empresa) | `test_minimum_age_is_not_experience` |
| 5 | `redes` coincide con «redes sociales» | Marketing puntuado como redes | `test_social_media_is_not_networking` |
| 6 | `soporte` coincide con «soporte al cliente» | Atención al cliente como soporte TI | `test_customer_service_is_not_it_support` |
| 7 | «Remoto» siempre suma ubicación | Remoto restringido a residentes de otro país | `test_remote_bonus_respects_residency_restriction` |
| 8 | «lead» en el título = liderazgo | «Sales Assistant – Lead Response» (cargo junior) | sin prueba: ambiguo |

## Recomendaciones para M1

1. Extraer `Nivel` y `Categoría` del feed de Get on Board como campos estructurados (el conector ya tiene el texto) y usarlos antes que las heurísticas del título.
2. Normalizar guiones y rangos antes de quitar acentos; interpretar «N–M años» por el mínimo y exigir contexto de experiencia («experiencia», «experience»).
3. Habilidades con exclusiones de contexto (p. ej. `redes` ≠ `redes sociales`, `soporte` ≠ `soporte al cliente`), configurables en el perfil.
4. Reducir o condicionar el +8 de ubicación; detectar «solo residentes en …».
5. Filtrar por categoría (Comercial, Marketing, Contenido) como incompatibilidad blanda configurable.
6. Medir antes y después con estas pruebas y con un conjunto etiquetado mayor; objetivo inicial: precisión ≥ 70 % sin bajar el recall de TI inicial.

## Resultados M1 (2026-10-21)

Reproducible con `python scripts/eval_matching.py SNAPSHOT.json [--details]` (el snapshot de 326 ofertas se guarda fuera del repositorio; `--fetch` lo descarga con una consulta). Perfil: `DEFAULT_PROFILE`. Etiquetas: nivel y categoría publicados por la fuente (relevante = inicial y técnica; dudosa = Semi Senior técnica).

| Paso (commit) | Sobre umbral | Precisión | Con dudosas | Recall | Top 10 relevantes / dudosas / no | Puntuar 326 |
|---|---|---|---|---|---|---|
| Línea base (`d405e2c`) | 11 | 0,364 | 0,636 | 0,571 | 3 / 3 / 4 | 0,33 s |
| Nivel de la fuente + «Nivel buscado» (`e6abc08`) | 7 | 0,857 | 0,857 | 0,857 | 7 / 1 / 2 | 0,33 s |
| Años de experiencia (`6ea1251`) | 7 | 0,857 | 0,857 | 0,857 | 6 / 1 / 3 | 0,46 s |
| «redes sociales», «soporte al cliente» (`0bd1c4b`) | 6 | **1,0** | 1,0 | 0,857 | 6 / 1 / 3 | 0,34 s |
| Ubicación y residencia (`f063e27`) | 6 | 1,0 | 1,0 | 0,857 | 6 / 1 / 3 | 0,38 s |
| Afinidad requerida para nivel y ubicación (`202b9d0`) | 6 | 1,0 | 1,0 | 0,857 | **6 / 4 / 0** | 0,30 s |

Detalle por cambio:

- **Años:** la advertencia de 5+ años pasó de 96 a 87 ofertas. Se revisaron a mano las 78 que cambiaron: desaparecieron los falsos de edad, antigüedad de la empresa y rangos, y aparecieron 73 avisos reales de 3–4 años.
- **Habilidades:** 11 ofertas perdieron la coincidencia de `redes` o `soporte`; las 11 eran de marketing, ventas o atención al cliente.
- **Ubicación:** 44 ofertas que listan países elegibles sin Chile reciben ahora un aviso y −20. Ninguna frase de residencia incompatible en el snapshot (las 6 «based in Latin America» son compatibles).
- **Única relevante bajo el umbral:** una oferta junior de front-end WordPress sin ninguna habilidad del perfil de prueba.

### Límites de esta medición

- **Circularidad:** las etiquetas y el matching usan el mismo campo `Nivel`. Se compensó revisando a mano la lista sobre el umbral (las 6 son puestos junior técnicos) y el top 10.
- **Muestra pequeña:** solo 7 ofertas relevantes, de una fuente y un día.
- **Segundo perfil** (analista de datos junior, sintético): el snapshot no tiene vacantes junior de datos, así que la precisión no es medible. Antes: 7 sobre el umbral, todas Semi Senior o ajenas. Ahora: 2, ambas junior técnicas con SQL.
- Siguiente paso: acumular un conjunto etiquetado de varias fechas y fuentes (ver [FUENTES.md](FUENTES.md)).

### Rendimiento de la API (326 ofertas, servidor local, 5 peticiones por ruta)

| Versión | `/api/dashboard` | `/api/jobs` y `/api/tracking` |
|---|---|---|
| Fin de ronda 2 (`1483fe7`) | ~0,45 s | ~0,43 s |
| Inicio de M1 (`92229db`, caché de `norm`) | ~0,34 s | ~0,33 s |
| Caché de puntajes (`95b2433`) | 1.ª petición ~0,35 s; siguientes **~0,02 s** | ~0,02 s |

La cifra de 2,5 s del informe de la ronda 3 fue una única petición en frío, con Chrome cargando a la vez; no es reproducible.
