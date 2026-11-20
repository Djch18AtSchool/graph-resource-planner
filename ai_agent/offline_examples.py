"""
Especificaciones de ejemplo para el modo OFFLINE (sin API key ni red).

Sirven para: demos en clase/video si falla la conexion, desarrollo del dashboard y pruebas
automaticas. Tienen la misma forma que la salida estructurada del LLM (ver schemas.GraphSpec).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

Node = Tuple[str, str, str]            # (id, label, type)
Edge = Tuple[str, str, str, str]       # (source, target, kind, reason)


def _spec(title: str, nodes: List[Node], edges: List[Edge]) -> Dict[str, Any]:
    return {
        "title": title,
        "nodes": [{"id": i, "label": l, "type": t, "description": ""} for i, l, t in nodes],
        "edges": [{"source": s, "target": d, "kind": k, "reason": r} for s, d, k, r in edges],
    }


ECOMMERCE = _spec(
    "E-commerce de microservicios",
    [
        ("api-gateway", "API Gateway", "gateway"), ("auth-service", "Autenticacion", "service"),
        ("catalog-service", "Catalogo", "service"), ("cart-service", "Carrito", "service"),
        ("checkout-service", "Checkout", "service"), ("payment-service", "Pagos", "service"),
        ("inventory-service", "Inventario", "service"), ("order-service", "Ordenes", "service"),
        ("notification-service", "Notificaciones RT", "service"), ("shipping-service", "Envios", "service"),
        ("orders-db", "BD Ordenes", "database"), ("inventory-db", "BD Inventario", "database"),
        ("event-bus", "Bus de eventos", "queue"), ("payment-provider", "Pasarela de pago", "external"),
        ("backup-job", "Respaldo nocturno", "job"), ("reports-job", "Reportes BI", "job"),
        ("reindex-job", "Reindexado de catalogo", "job"),
    ],
    [
        ("api-gateway", "auth-service", "dependency", "valida tokens"),
        ("api-gateway", "catalog-service", "dependency", "consulta productos"),
        ("api-gateway", "cart-service", "dependency", "gestiona carrito"),
        ("api-gateway", "checkout-service", "dependency", "inicia compra"),
        ("cart-service", "catalog-service", "dependency", "precios y detalles"),
        ("checkout-service", "cart-service", "dependency", "lee items"),
        ("checkout-service", "payment-service", "dependency", "cobra"),
        ("checkout-service", "inventory-service", "dependency", "reserva stock"),
        ("checkout-service", "order-service", "dependency", "crea orden"),
        ("payment-service", "payment-provider", "dependency", "API externa"),
        ("order-service", "orders-db", "dependency", "persistencia"),
        ("inventory-service", "inventory-db", "dependency", "persistencia"),
        ("catalog-service", "inventory-db", "dependency", "lee stock"),
        ("order-service", "event-bus", "dependency", "publica OrderCreated"),
        ("inventory-service", "event-bus", "dependency", "publica StockChanged"),
        ("notification-service", "event-bus", "dependency", "consume eventos"),
        ("shipping-service", "event-bus", "dependency", "consume eventos"),
        ("shipping-service", "orders-db", "dependency", "actualiza estado"),
        ("backup-job", "order-service", "conflict", "snapshot bloquea orders-db"),
        ("backup-job", "inventory-service", "conflict", "snapshot bloquea inventory-db"),
        ("backup-job", "reports-job", "conflict", "I/O de disco exclusivo"),
        ("reports-job", "order-service", "conflict", "lecturas pesadas sobre orders-db"),
        ("reports-job", "inventory-service", "conflict", "lecturas pesadas sobre inventory-db"),
        ("inventory-service", "order-service", "conflict", "bloqueos de reserva de stock"),
        ("order-service", "shipping-service", "conflict", "escrituras concurrentes en orders-db"),
        ("reindex-job", "catalog-service", "conflict", "reindexado bloquea el indice"),
        ("reindex-job", "inventory-service", "conflict", "lee inventory-db completo"),
        ("notification-service", "reports-job", "conflict", "cuota de la API de correo"),
    ],
)

DATA_PIPELINE = _spec(
    "Pipeline de datos diario",
    [
        ("ingest-sales", "Ingesta de ventas", "task"), ("ingest-web", "Ingesta de logs web", "task"),
        ("clean-data", "Limpieza", "task"), ("enrich-geo", "Enriquecimiento geografico", "task"),
        ("train-model", "Entrenamiento", "task"), ("build-dashboard", "Dashboard", "task"),
        ("export-report", "Exportar reporte", "task"), ("warehouse", "Data warehouse", "database"),
    ],
    [
        ("clean-data", "ingest-sales", "dependency", "usa los datos crudos"),
        ("clean-data", "ingest-web", "dependency", "usa los datos crudos"),
        ("enrich-geo", "clean-data", "dependency", "requiere datos limpios"),
        ("train-model", "enrich-geo", "dependency", "features geograficas"),
        ("build-dashboard", "warehouse", "dependency", "lee agregados"),
        ("export-report", "build-dashboard", "dependency", "mismos agregados"),
        ("ingest-sales", "warehouse", "dependency", "escribe"),
        ("ingest-web", "warehouse", "conflict", "escritura exclusiva en la misma particion"),
        ("ingest-sales", "ingest-web", "conflict", "mismo ancho de banda del enlace"),
        ("train-model", "enrich-geo", "conflict", "ambos usan la unica GPU"),
        ("train-model", "build-dashboard", "conflict", "memoria del nodo compartido"),
        ("build-dashboard", "export-report", "conflict", "mismo cache de consultas"),
    ],
)

ML_PLATFORM = _spec(
    "Plataforma de ML con tres tipos de recursos",
    [
        ("feature-store", "Feature store", "service"), ("trainer-a", "Entrenador A", "job"),
        ("trainer-b", "Entrenador B", "job"), ("trainer-c", "Entrenador C", "job"),
        ("gpu-1", "GPU 1", "external"), ("gpu-2", "GPU 2", "external"), ("gpu-3", "GPU 3", "external"),
    ],
    # K3,3 entre entrenadores y GPUs: arquitectura NO plana -> exige nodos virtuales
    [(t, g, "dependency", "puede ejecutarse en esa GPU")
     for t in ("trainer-a", "trainer-b", "trainer-c") for g in ("gpu-1", "gpu-2", "gpu-3")]
    + [("trainer-a", "feature-store", "dependency", "lee features"),
       ("trainer-a", "trainer-b", "conflict", "comparten el feature store en escritura"),
       ("trainer-b", "trainer-c", "conflict", "comparten checkpoint en disco")],
)

EXAMPLES: Dict[str, Dict[str, Any]] = {
    "ecommerce": ECOMMERCE,
    "pipeline": DATA_PIPELINE,
    "ml": ML_PLATFORM,
}

# palabras clave -> ejemplo (heuristica minima del cliente offline)
KEYWORDS = {
    "ecommerce": ("e-commerce", "ecommerce", "tienda", "pagos", "inventario", "microservicio", "checkout"),
    "pipeline": ("pipeline", "etl", "datos", "ingesta", "reporte", "dashboard"),
    "ml": ("gpu", "entren", "modelo", "machine learning", "ml"),
}


def pick_example(text: str) -> Dict[str, Any]:
    low = text.lower()
    scores = {k: sum(w in low for w in ws) for k, ws in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return EXAMPLES[best if scores[best] > 0 else "ecommerce"]
