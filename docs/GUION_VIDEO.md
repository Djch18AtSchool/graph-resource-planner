# Guion del video (máximo 5 minutos)

La consigna pide un video de **5 minutos como máximo** que explique cómo funciona el código, sus ventajas y
desventajas, y que muestre una demostración. **Todos los integrantes deben participar.**

El guion está pensado para **4 integrantes** y dura unos **4 min 40 s**: deja 20 segundos de margen. Si son 3,
el integrante 4 se reparte así: la arquitectura (parte 4a) la dice el integrante 3 y la prueba de estrés (4b)
el integrante 1, al final.

| Parte | Quién | Tiempo | Tema |
|---|---|---|---|
| 1 | Integrante 1 | 0:00 – 0:40 | El problema y el modelo con grafos |
| 2 | Integrante 2 | 0:40 – 1:50 | El motor en Python: grafo, DSatur y Welsh-Powell |
| 3 | Integrante 3 | 1:50 – 3:00 | Demostración: coloración paso a paso, cotas de χ(G) y plan |
| 4 | Integrante 4 | 3:00 – 3:50 | Arquitectura, pruebas y prueba de estrés |
| 5 | Todos (uno cada uno) | 3:50 – 4:40 | Ventajas, desventajas y cierre |

## Antes de grabar

* Abrir la app en Chrome: https://djch18atschool.github.io/graph-resource-planner/ y recargar con
  **Ctrl+Shift+R** para tener la última versión. Esperar a que los ejemplos de abajo estén activos (Python ya cargó).
* Dejar el zoom del navegador al 100 % y la ventana a pantalla completa; ocultar marcadores y pestañas ajenas.
* Abrir en VS Code, cada uno en una pestaña, los archivos de la parte 2 en las líneas indicadas.
* Ensayar una vez con cronómetro. Si se pasan de tiempo, recorten la parte 4 (la arquitectura se puede resumir en
  una frase).
* Grabar cada parte por separado (por ejemplo con OBS o la grabación de Zoom/Teams) y unirlas al final.

---

## Parte 1 · El problema (Integrante 1, ~40 s)

**En pantalla:** la app recién abierta, en el paso 1 en blanco. Al decir «por ejemplo», tocar la pill
**E-commerce**.

> Somos el grupo 2 y nos tocó el Módulo 2: coloración de grafos para asignar recursos.
>
> Un sistema tiene muchas tareas, como respaldos o migraciones, y varias usan recursos exclusivos, como una base
> de datos. Si dos tareas comparten un recurso, no pueden correr al mismo tiempo. ¿Cómo las agrupamos en la
> menor cantidad de lotes paralelos?
>
> Lo modelamos como un grafo: cada tarea es un vértice y cada choque, una arista. Colorear el grafo es asignar
> lotes, y el mínimo de colores posible es el número cromático, χ de G. Aquí, por ejemplo, el motor reconoció 12
> tareas con 19 conflictos.

## Parte 2 · El motor en Python (Integrante 2, ~70 s)

**En pantalla:** VS Code. Mostrar cada archivo mientras se menciona.

1. `graph_core/problem.py` línea 148 (`parse_problem`)
2. `graph_core/scheduling.py` línea 41 (el ciclo sobre los recursos)
3. `graph_core/graph.py` líneas 47 y 51 (`_adj` y `_matrix`)
4. `graph_core/coloring.py` línea 89 (el heap de DSatur) y línea 116 (el orden de Welsh-Powell)

> El motor está en Python, en la carpeta `graph_core`. Primero, `parse_problem` lee el texto línea por línea y,
> si algo está mal, dice en qué línea.
>
> Después, `conflict_graph` arma el grafo: todas las tareas que usan un mismo recurso quedan unidas entre sí,
> o sea, cada recurso forma una clique.
>
> El grafo es nuestra propia clase `Graph`, que guarda a la vez una lista y una matriz de adyacencia. Los
> algoritmos recorren vecinos, y con la lista eso cuesta O(V + E); con la matriz costaría O(V²) aunque haya
> pocos conflictos.
>
> Implementamos dos algoritmos de coloración. DSatur colorea primero la tarea más acorralada, es decir, la que
> tiene más colores distintos entre sus vecinos, y le da el primer color libre. Lo hicimos con un heap, así que
> cuesta O((V + E) log V). Welsh-Powell ordena las tareas de más a menos conflictos y va llenando un color a la
> vez. Es más simple y un poco más rápido, pero depende mucho del orden.

## Parte 3 · Demostración (Integrante 3, ~70 s)

**En pantalla:** volver a la app con el ejemplo E-commerce.

1. Botón **Ver conflictos**. Presionar **Reproducir** (velocidad 1×) y dejar que avance unos pasos.
2. Pausar en algún paso y señalar la tabla de la derecha.
3. Al terminar, elegir **Agrupado por lote**.
4. Botón **Ver plan**.

> Este es el grafo de conflictos. Al reproducir, vemos a DSatur trabajar: en cada paso elige la tarea con mayor
> saturación, y a la derecha está la tabla con la que decide: saturación y grado de cada candidata.
>
> Terminó con 4 colores. Si agrupamos por lote, cada columna es un color y todas las aristas cruzan entre
> columnas: ninguna tarea del mismo lote choca con otra.
>
> En el plan, la app no solo dice que son 4 lotes: demuestra que 4 es el mínimo. Encontró una clique de 4
> tareas que chocan todas entre sí, y una clique necesita un color por vértice, así que χ de G es 4. Cuando la
> clique no alcanza, el motor intenta calcular χ exacto con branch and bound en grafos pequeños.
>
> El resultado: los lotes como etapas de un pipeline, un tiempo total de 100 en lugar de 205 si todo fuera en
> fila, y la cantidad de ejecutores que hacen falta, que es el tamaño del lote más grande.

## Parte 4 · Arquitectura, pruebas y estrés (Integrante 4, ~50 s)

**En pantalla:** (4a) el diagrama de `docs/ARQUITECTURA.md` sección 2.1, abierto en GitHub; (4b) la app, botón
**Prueba de estrés** arriba a la derecha, luego **Ejecutar prueba**.

> **4a.** La interfaz está hecha en React con TypeScript, pero no reescribimos los algoritmos en JavaScript: el
> mismo código Python corre dentro del navegador con Pyodide, que es Python compilado a WebAssembly, en un Web
> Worker. Por eso la página es estática y se publica en GitHub Pages sin servidor. Además, más de cien pruebas
> automáticas revisan el motor y la app antes de cada publicación.
>
> **4b.** Esta es la prueba de estrés que pide la consigna: grafos aleatorios de 10, 100 y 1000 tareas,
> coloreados aquí mismo en el navegador. Con mil tareas, DSatur tarda unos pocos milisegundos, y vemos que crece
> casi lineal con el tamaño, como predice su complejidad.

## Parte 5 · Ventajas, desventajas y cierre (~50 s, una frase o dos cada uno)

**En pantalla:** para la frase sobre Welsh-Powell, ir al paso 1, tocar la pill **Caso difícil**, en el paso 2
elegir **Welsh-Powell** y abrir **Ver plan**: aparece «5 lotes… Pero bastan 2» y el botón **Usar DSatur**.

> **Integrante 1:** Como ventajas: los dos algoritmos son casi lineales en grafos dispersos, y la app indica cuándo
> el resultado es el óptimo demostrado, no solo una aproximación.
>
> **Integrante 2:** Como desventaja, son heurísticas: calcular χ de G exacto es NP-difícil. Por ejemplo, Welsh-Powell
> en este grafo usa 5 lotes cuando bastan 2; DSatur sí encuentra los 2.
>
> **Integrante 3:** El modelo también tiene límites: supone recursos de capacidad 1 y minimiza la cantidad de
> lotes, no el tiempo total, que sería un problema de coloración ponderada.
>
> **Integrante 4:** En resumen, convertimos un problema de planificación en coloración de grafos, con dos
> algoritmos, cotas que justifican el resultado y una app que lo muestra paso a paso. Gracias.

---

## Preguntas que podrían hacerles (para preparar)

* **¿Por qué DSatur y no solo Welsh-Powell?** DSatur decide según el estado actual (la saturación), no según un
  orden fijo; por eso es exacto en grafos bipartitos y nunca usó más lotes que Welsh-Powell en nuestras pruebas.
* **¿Cómo saben que 4 es el mínimo?** Porque hay una clique de 4 tareas: cada una necesita su propio color
  (ω(G) ≤ χ(G)) y DSatur usó exactamente 4.
* **¿Qué pasa si no se puede demostrar?** La app muestra un rango, por ejemplo «entre 3 y 4», porque calcular χ
  exacto en grafos grandes es NP-difícil (Karp, 1972).
* **¿Por qué lista de adyacencia y no matriz?** Los algoritmos recorren vecinos: O(d) por vértice con la lista
  y O(V) con la matriz. Con 3000 tareas la lista ocupa 1.1 MB y la matriz 72 MB (`results/`).
* **¿El navegador corre de verdad el Python del repositorio?** Sí: `scripts/build_web.py` empaqueta
  `graph_core` en un zip, y `web/src/engine/worker.ts` lo descomprime y lo ejecuta con Pyodide.
