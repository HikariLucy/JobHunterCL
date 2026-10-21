# Análisis de puntuaciones — 326 ofertas de Get on Board

Fecha: 2026-10-21. Insumo para M1 («Mejorar ranking»). **No se cambió el algoritmo.**

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

| # | Defecto | Ejemplo observado | Prueba |
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
