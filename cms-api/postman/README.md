# Preparación de Postman

Crear posteriormente un entorno local con la variable:

```text
base_url=http://127.0.0.1:8000
```

La referencia REST será `{{base_url}}/api/v1`. El contrato generado por FastAPI estará disponible en `{{base_url}}/openapi.json`; en esta fase todavía no contiene operaciones de negocio.

Las futuras pruebas manuales incluirán GET, POST, PUT y DELETE una vez definido e implementado cada contrato. No se incluye todavía una colección ni requests con cuerpos, campos o respuestas inventados.

## Convenciones

- Usar `Content-Type: application/json` en requests con cuerpos JSON.
- Usar path parameters para la identidad del recurso.
- Usar query parameters para filtros, paginación y búsquedas definidos por el contrato.
- Usar cuerpos JSON para POST y PUT cuando el contrato los establezca.
- Esperar respuestas JSON salvo operaciones explícitamente sin contenido.

Las pruebas se diseñarán según los estados aplicables a cada operación: `200 OK`, `201 Created`, `202 Accepted`, `204 No Content`, `404 Not Found`, `409 Conflict`, `422 Unprocessable Entity`, `500 Internal Server Error` y `504 Gateway Timeout`. Esta lista no asigna estados a rutas ni implica que estén implementados.

## PATCH

Estado: `CONTRACT_PENDING`.

Antes de crear requests PATCH deben definirse el recurso, los campos modificables, los estados permitidos, el request, el response, los errores y la idempotencia si aplica. No hay endpoint PATCH implementado.

## Live Preview y Metrics

Live Preview contempla `GET /api/v1/documents/{document_id}/live-preview` con upgrade a WebSocket. La negociación y los mensajes están pendientes; no hay endpoint HTTP ficticio ni WebSocket implementado.

Metrics se implementará en una fase posterior, después de completar su contrato. No existe integración analítica real.

Consultar el orden de trabajo en [../api-docs/implementation-plan.md](../api-docs/implementation-plan.md).
