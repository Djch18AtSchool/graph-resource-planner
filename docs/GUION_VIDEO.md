# Guion del video (máximo 5 minutos)

La consigna pide un video de **5 minutos como máximo** que explique cómo funciona el código, sus ventajas y
desventajas, y que muestre una demostración. **Todos los integrantes deben participar.**

El texto hablado explica las ideas con palabras simples y nombra los conceptos clave (grafo de conflictos,
saturación, clique, número cromático, complejidad). El detalle formal va en **láminas** (al final de este
archivo) que se muestran en pantalla mientras se habla, y en las preguntas de preparación por si la profesora
quiere profundizar.

Está pensado para **4 integrantes** y dura unos **4 min 20 s** a ritmo normal, así que deja margen. Si son 3,
la parte 4 la dicen entre el integrante 2 (tiempo y memoria) y el integrante 3 (calidad y Pyodide).

| Parte | Quién | Tiempo | Tema | Lámina |
|---|---|---|---|---|
| 1 | Integrante 1 | 0:00 – 0:55 | El problema y el modelo con grafos | 1 |
| 2 | Integrante 2 | 0:55 – 1:50 | Cómo se guarda el grafo y cómo trabajan DSatur y Welsh-Powell | 2 |
| 3 | Integrante 3 | 1:50 – 2:50 | Demostración: paso a paso, por qué 4 lotes es el mínimo y el plan | 3 |
| 4 | Integrante 4 | 2:50 – 3:40 | Pruebas de estrés: qué muestran los resultados | 4 |
| 5 | Todos | 3:40 – 4:20 | Ventajas, desventajas y cierre | — |

## Antes de grabar

* Abrir la app en Chrome: https://djch18atschool.github.io/graph-resource-planner/ y recargar con
  **Ctrl+Shift+R**. Esperar a que las pills de ejemplo estén activas (Python ya cargó).
* Preparar las 4 láminas del final (Google Slides, PowerPoint o una captura de este archivo en GitHub).
* Abrir en VS Code las líneas de la parte 2 y las imágenes `results/stress_times.png`,
  `results/stress_colors.png` y `results/stress_memory.png`.
* Ensayar una vez con cronómetro.

---

## Parte 1 · El problema y el modelo (Integrante 1, ~55 s)

**En pantalla:** la app en blanco; **Lámina 1** mientras se explica el modelo; al final, tocar la pill
**E-commerce**.

> Somos el grupo 2 y nos tocó el Módulo 2: coloración de grafos para asignar recursos.
>
> El problema es este: un sistema tiene tareas que usan recursos exclusivos, como una base de datos o un disco.
> Si dos tareas comparten un recurso, no pueden correr al mismo tiempo. ¿Cómo las agrupamos en la menor cantidad
> de lotes paralelos?
>
> Lo modelamos con un grafo de conflictos: cada tarea es un vértice, y dos tareas se unen con una arista si
> comparten un recurso. Colorear el grafo es asignar lotes: dos vecinos nunca comparten color, así que cada color
> es un grupo de tareas que pueden correr juntas. El mínimo de colores posible es el número cromático, χ(G), y
> calcularlo es un problema NP-difícil.
>
> En este ejemplo, el motor leyó 12 tareas y encontró 19 conflictos.

## Parte 2 · El motor (Integrante 2, ~55 s)

**En pantalla:** VS Code y, al final, la **Lámina 2**.

1. `graph_core/graph.py` líneas 47 y 51 (`_adj` y `_matrix`)
2. `graph_core/coloring.py` línea 89 (el heap de DSatur) y línea 116 (el orden de Welsh-Powell)

> El grafo se guarda en nuestra clase `Graph`, con lista y matriz de adyacencia. Los algoritmos recorren los
> vecinos de cada vértice: con la lista eso cuesta O(V + E) en total, y con la matriz costaría O(V²). Por eso
> trabajan con la lista.
>
> Implementamos dos algoritmos. DSatur colorea primero la tarea más acorralada, la que tiene más colores
> distintos entre sus vecinos; a eso se le llama saturación. Le da el menor color libre y, gracias a un heap,
> cuesta O((V + E) log V).
>
> Welsh-Powell ordena las tareas de más a menos conflictos y llena un color a la vez. Es más simple y algo más
> rápido, pero depende mucho del orden. Ninguno de los dos usa más de Δ + 1 colores, donde Δ es el grado máximo.

## Parte 3 · Demostración (Integrante 3, ~60 s)

**En pantalla:** la app con E-commerce.

1. **Ver conflictos** → **Reproducir** a 1×; pausar un momento y señalar la tabla de la derecha.
2. Al terminar, **Agrupado por lote**.
3. **Lámina 3** mientras se explica por qué 4 es el mínimo.
4. **Ver plan**.

> Al reproducir vemos a DSatur trabajar: empieza por la tarea con más conflictos, y la tabla de la derecha
> muestra la saturación y el grado de cada candidata.
>
> Terminó con 4 colores. ¿Es el mínimo? Sí, y la app lo demuestra: encontró 4 tareas que chocan todas entre sí,
> lo que se llama una clique, y una clique de 4 necesita 4 colores distintos. Como DSatur usó 4, no se puede
> hacer mejor. Cuando esa cota no alcanza, el motor intenta calcular χ(G) exacto con branch and bound en grafos
> pequeños.
>
> Si agrupamos por lote, cada columna es un color y ninguna línea queda dentro de una columna.
>
> En el plan, cada lote dura lo que su tarea más larga: el tiempo total es 100, contra 205 si todo fuera en fila,
> y hacen falta 5 ejecutores.

## Parte 4 · Pruebas de estrés (Integrante 4, ~50 s)

**En pantalla:** **Lámina 4**; luego `results/stress_times.png` y `results/stress_memory.png`; al final, la
página **Prueba de estrés** de la app corriendo los tres tamaños.

> Para las pruebas de estrés coloreamos grafos de 10, 100 y 1000 tareas, y los resultados coinciden con la
> teoría.
>
> En tiempo: al pasar de 100 a 1000 tareas, la complejidad predice que DSatur tarde unas 15 veces más, y medimos
> 16. Con mil tareas tarda unos 4 milisegundos.
>
> En calidad: en grafos planos DSatur usa 4 colores, como dice el Teorema de los Cuatro Colores, y Welsh-Powell
> usa 6. En grafos aleatorios densos queda una brecha entre la cota y el resultado, lo esperable en un problema
> NP-difícil.
>
> En memoria: con 3000 tareas la lista ocupa 1 MB y la matriz 72.
>
> Y todo esto corre en el navegador: el mismo código Python se ejecuta con Pyodide, sin servidor.

## Parte 5 · Ventajas, desventajas y cierre (~40 s, una frase cada uno)

**En pantalla:** para la frase del integrante 2: pill **Caso difícil**, en el paso 2 elegir **Welsh-Powell** y
**Ver plan** («5 lotes. Pero bastan 2»).

> **Integrante 1:** A favor: los algoritmos son rápidos, casi lineales, y la app dice cuándo el resultado es el
> óptimo y no solo una aproximación.
>
> **Integrante 2:** En contra: son heurísticas. En este grafo, Welsh-Powell usa 5 lotes cuando bastan 2, porque
> depende del orden; DSatur encuentra los 2.
>
> **Integrante 3:** El modelo también tiene límites: cada recurso lo usa una sola tarea a la vez, y minimizamos la
> cantidad de lotes, no el tiempo total.
>
> **Integrante 4:** En resumen: convertimos un problema de planificación en coloración de grafos, con dos
> algoritmos y cotas que justifican el resultado. Gracias.

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
