# Guion del video (máximo 5 minutos)

La consigna pide un video de **5 minutos como máximo** que explique cómo funciona el código, sus ventajas y
desventajas, y que muestre una demostración. **Todos los integrantes deben participar.**

Este guion prioriza el contenido técnico y matemático. Para que quepa en 5 minutos, las fórmulas van en
**láminas** (al final de este archivo) que se muestran en pantalla mientras se habla. Así la profesora ve la
matemática completa aunque no se lea en voz alta cada símbolo.

Está pensado para **4 integrantes** y dura unos **4 min 40 s** a ritmo de exposición (unas 145 palabras por
minuto). Las frases marcadas con **[opcional]** se pueden cortar si el ensayo pasa de 5 minutos. Si son 3
integrantes, la parte 4 se divide: el integrante 2 dice el bloque «Tiempo» y el integrante 3 dice «Calidad» y
«Memoria».

| Parte | Quién | Tiempo | Tema | Lámina |
|---|---|---|---|---|
| 1 | Integrante 1 | 0:00 – 0:45 | Modelo formal: grafo de conflictos y número cromático | 1 |
| 2 | Integrante 2 | 0:45 – 1:55 | Representación, construcción del grafo, DSatur y Welsh-Powell con su complejidad | 2 |
| 3 | Integrante 3 | 1:55 – 3:05 | Demostración: paso a paso, cotas de χ(G), optimalidad y plan | 3 |
| 4 | Integrante 4 | 3:05 – 4:05 | Pruebas de estrés como evidencia de la teoría | 4 |
| 5 | Todos | 4:05 – 4:40 | Ventajas, desventajas y cierre | — |

## Antes de grabar

* Abrir la app en Chrome: https://djch18atschool.github.io/graph-resource-planner/ y recargar con
  **Ctrl+Shift+R**. Esperar a que las pills de ejemplo estén activas (Python ya cargó).
* Preparar las 4 láminas del final (Google Slides, PowerPoint o una captura de este archivo en GitHub).
* Abrir en VS Code las líneas de la parte 2 y las imágenes `results/stress_times.png`,
  `results/stress_colors.png` y `results/stress_memory.png`.
* Ensayar con cronómetro. Si pasa de 5:00, cortar primero las frases **[opcional]**.

---

## Parte 1 · Modelo formal (Integrante 1, ~45 s)

**En pantalla:** la app en blanco; tocar la pill **E-commerce** al final. Mientras se habla del modelo,
**Lámina 1**.

> Somos el grupo 2 y desarrollamos el Módulo 2: coloración de vértices para asignar recursos.
>
> Cada tarea usa recursos exclusivos. Construimos el grafo de conflictos G = (T, E): dos tareas son adyacentes
> si comparten un recurso o si se declaró que chocan.
>
> Una coloración propia asigna colores de modo que los extremos de toda arista tengan colores distintos. Cada
> clase de color es un conjunto independiente: un lote que corre en paralelo. Buscamos el mínimo de colores, el
> número cromático χ(G); decidir si χ(G) ≤ k es NP-completo para k ≥ 3.
>
> En este ejemplo, el motor leyó 12 tareas y encontró 19 conflictos.

## Parte 2 · Representación y algoritmos (Integrante 2, ~70 s)

**En pantalla:** VS Code, en este orden, con la **Lámina 2** al final.

1. `graph_core/graph.py` líneas 47 y 51 (`_adj` y `_matrix`)
2. `graph_core/scheduling.py` línea 41 (las cliques por recurso)
3. `graph_core/coloring.py` línea 89 (el heap de DSatur) y línea 116 (el orden de Welsh-Powell)

> El grafo vive en nuestra clase `Graph`, con dos representaciones sincronizadas: la lista de adyacencia, que
> ocupa O(V + E), y la matriz, que ocupa O(V²). Los algoritmos recorren vecinos, lo que cuesta O(grado) con la
> lista y O(V) con la matriz; por eso usan la lista.
>
> Al construir el grafo, cada recurso que usan k tareas aporta una clique K_k.
>
> DSatur define la saturación de un vértice como la cantidad de colores distintos entre sus vecinos ya
> coloreados. En cada paso toma el vértice sin color de mayor saturación, desempata por mayor grado y le asigna
> el menor color libre. Lo implementamos con un heap de entradas perezosas: cada arista genera a lo sumo una
> inserción, así que cuesta O((V + E) log V).
>
> Welsh-Powell ordena los vértices por grado decreciente y construye un color a la vez, metiendo en él todo
> vértice no adyacente a los ya elegidos. Cuesta O(V log V + kV + E). Ambos usan a lo sumo Δ + 1 colores.

## Parte 3 · Demostración y optimalidad (Integrante 3, ~70 s)

**En pantalla:** la app con E-commerce.

1. **Ver conflictos** → **Reproducir** a 1×; pausar en el paso 3 y señalar la tabla.
2. Al terminar, **Agrupado por lote** (sin comentarlo: la imagen habla sola).
3. **Lámina 3** mientras se explica la cota y el branch & bound.
4. **Ver plan**.

> DSatur empieza por «Reporte de ventas», el vértice de grado máximo, 6. La tabla de la derecha muestra la
> saturación y el grado de cada candidata.
>
> Terminó con 4 colores. ¿Es el mínimo? Usamos la cota ω(G) ≤ χ(G): una clique de tamaño ω necesita ω colores
> distintos. El motor encontró una clique de 4 tareas, así que χ(G) ≥ 4; como DSatur logró 4, χ(G) = 4 y la
> optimalidad queda demostrada.
>
> La cota no siempre alcanza: el grafo de Grötzsch tiene ω = 2 pero χ = 4. Cuando no coincide, calculamos χ
> exacto con branch and bound: recorre las asignaciones en el orden de DSatur y poda toda rama que ya usa tantos
> colores como la mejor solución conocida. **[opcional]** Lo limitamos a componentes de hasta 60 vértices.
>
> En el plan, cada lote dura lo que su tarea más larga. El tiempo total es la suma de esas duraciones: 100,
> contra 205 en secuencia. Se necesitan 5 ejecutores, el tamaño de la clase de color más grande.

## Parte 4 · Pruebas de estrés como evidencia (Integrante 4, ~60 s)

**En pantalla:** **Lámina 4** con la tabla; luego `results/stress_times.png`, `results/stress_colors.png` y
`results/stress_memory.png`, una por bloque. **[opcional]** Al final, la página **Prueba de estrés** de la app
corriendo los tres tamaños.

> Coloreamos grafos de 10, 100 y 1000 vértices de cinco familias, y los resultados confirman la teoría.
>
> **Tiempo.** Al pasar de 100 a 1000 vértices en una triangulación plana, (V + E) log V predice que el tiempo de
> DSatur se multiplica por 15, y medimos 16. En el grafo aleatorio denso la predicción es 25 y medimos 23.
> **[opcional]** Con mil vértices, DSatur tarda unos 4 milisegundos.
>
> **Calidad.** En la triangulación plana DSatur usa 4 colores, como garantiza el Teorema de los Cuatro Colores,
> y Welsh-Powell usa 6. En el aleatorio denso, en cambio, la clique encontrada es 4 y DSatur usa 16: queda una
> brecha que no podemos cerrar, porque el problema es NP-difícil.
>
> **Memoria.** Con 3000 vértices, la lista ocupa 1,1 MB y la matriz 72. Al multiplicar V por 30, la matriz
> crece 877 veces, casi 30 al cuadrado; la lista, 38 veces.

## Parte 5 · Ventajas, desventajas y cierre (~35 s, una frase cada uno)

**En pantalla:** para la frase del integrante 2: pill **Caso difícil**, en el paso 2 elegir **Welsh-Powell** y
**Ver plan** («5 lotes. Pero bastan 2»).

> **Integrante 1:** A favor: ambos algoritmos son casi lineales en grafos dispersos, y la app distingue un
> resultado aproximado de uno demostrado óptimo.
>
> **Integrante 2:** En contra: son heurísticas. En este grafo corona, que es bipartito, Welsh-Powell usa 5 lotes
> por depender del orden; DSatur encuentra 2.
>
> **Integrante 3:** El modelo supone recursos de capacidad 1 y minimiza lotes, no el tiempo total; eso sería
> coloración ponderada, también NP-difícil.
>
> **Integrante 4:** En resumen: modelamos la planificación como coloración, implementamos DSatur y Welsh-Powell
> con su complejidad, y acotamos χ(G) para saber cuándo la respuesta es óptima. Gracias.

---

## Láminas de apoyo

Texto para copiar en las diapositivas; cada una acompaña una parte.

### Lámina 1 · Modelo

* T = tareas, R = recursos exclusivos, rec(t) ⊆ R
* Grafo de conflictos G = (T, E), con {u, v} ∈ E ⟺ rec(u) ∩ rec(v) ≠ ∅ (o conflicto declarado)
* Coloración propia c : T → {1, …, k} con c(u) ≠ c(v) para toda {u, v} ∈ E
* Lote i = c⁻¹(i), un conjunto independiente
* χ(G) = mínimo k posible; decidir χ(G) ≤ k es NP-completo para k ≥ 3 (Karp, 1972)

### Lámina 2 · Algoritmos y complejidad

| | Tiempo | Espacio |
|---|---|---|
| Lista de adyacencia | vecinos de v: O(d(v)) | O(V + E) |
| Matriz de adyacencia | vecinos de v: O(V) | O(V²) |
| Grafo de conflictos | O(V + Σ_r k_r²) | O(V + E) |
| DSatur (heap perezoso) | O((V + E) log V) | O(V + E) |
| Welsh-Powell | O(V log V + kV + E) | O(V) |

* sat(v) = |{ c(u) : u ∈ N(v), u ya coloreado }|
* DSatur elige argmax (sat(v), d(v)) y le asigna min{ c ≥ 1 : c no usado en N(v) }
* Ambos: χ(G) ≤ k ≤ Δ(G) + 1

### Lámina 3 · Cotas y optimalidad

* ω(G) ≤ χ(G) ≤ k_heurística ≤ Δ(G) + 1
* Recurso usado por k tareas ⟹ K_k ⊆ G ⟹ χ(G) ≥ k
* Si ω encontrado = k_heurística ⟹ χ(G) = k (óptimo demostrado)
* Si no: branch & bound (orden DSatur, poda cuando los colores usados ≥ mejor solución)
* Ejemplo de por qué hace falta: Grötzsch, ω = 2 y χ = 4
* Plan: duración(lote i) = máx{ dur(t) : c(t) = i }; tiempo total = Σ_i duración(lote i);
  ejecutores = máx_i |c⁻¹(i)|

### Lámina 4 · Pruebas de estrés (CPython, mejor de 3 ejecuciones)

| Familia (n = 1000) | E | DSatur ms / colores | Welsh-Powell ms / colores | Clique | χ(G) |
|---|---|---|---|---|---|
| Triangulación plana | 2994 | 3.91 / **4** | 1.45 / 6 | 4 | 4 |
| Grilla (bipartita) | 1860 | 1.68 / 2 | 0.88 / 2 | 2 | 2 |
| Aleatorio denso | 24975 | 14.17 / 16 | 6.09 / 19 | 4 | entre 4 y 16 |
| Recursos compartidos | 9959 | 8.35 / 20 | 2.98 / 20 | 20 | 20 |

* De n = 100 a n = 1000, DSatur: predicho ×15,2 y medido ×16,4 (triangulación); predicho ×24,6 y medido ×23,1
  (denso)
* Memoria con V = 3000 y E = 3V: lista 1,1 MB y matriz 72 MB (V ×30 ⟹ matriz ×877 ≈ 30², lista ×38)

---

## Preguntas que podrían hacerles (para preparar)

* **¿Por qué el heap «perezoso» da O((V + E) log V)?** La saturación de un vértice solo sube cuando un vecino
  recibe un color nuevo para él, así que cada arista genera a lo sumo una inserción. En vez de actualizar una
  entrada, se inserta otra y la vieja se descarta al sacarla del heap. Total: O(V + E) operaciones de O(log V).
* **¿Por qué DSatur y no solo Welsh-Powell?** DSatur decide según el estado actual (la saturación) y no según un
  orden fijo. Por eso es exacto en grafos bipartitos, ciclos y ruedas, y en nuestras pruebas nunca usó más
  colores que Welsh-Powell.
* **¿Por qué ambos usan a lo sumo Δ + 1 colores?** Al colorear un vértice, sus vecinos ocupan como mucho Δ
  colores, así que siempre queda uno libre entre los primeros Δ + 1. Por el teorema de Brooks, en un grafo
  conexo incluso χ(G) ≤ Δ, salvo que sea completo o un ciclo impar.
* **¿Cómo funciona el branch & bound?** Recorre las asignaciones en el orden de DSatur. Cada rama que ya usa
  tantos colores como la mejor solución conocida se poda, y la búsqueda termina antes si la solución iguala a la
  cota de la clique. Tiene un límite de 200 000 nodos; si lo excede, la app muestra un rango para χ(G).
* **¿Por qué la cota de la clique es débil en grafos aleatorios?** En G(n, p) la clique máxima crece como
  log n, pero χ crece como n / log n; por eso con 1000 vértices la brecha es 4 contra 16.
* **¿Cómo verifican que la coloración es correcta?** Las pruebas comprueban que c(u) ≠ c(v) para cada arista,
  que los lotes particionan las tareas y que χ exacto coincide con la fuerza bruta en grafos pequeños.
* **¿El navegador corre de verdad el Python del repositorio?** Sí: `scripts/build_web.py` empaqueta
  `graph_core` en un zip y `web/src/engine/worker.ts` lo ejecuta con Pyodide (Python en WebAssembly).
