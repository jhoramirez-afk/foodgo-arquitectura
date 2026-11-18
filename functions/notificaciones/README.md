# Lambda de Notificaciones - FoodGo EP03

Funcion Java 21 que consume solicitudes SQS y registra su procesamiento en Notificaciones. Su handler es `cl.duoc.jv0101.foodgo.lambda.NotificacionHandler::handleRequest`.

```sh
mvn clean verify
```

Artefacto: `target/foodgo-notificaciones-lambda-3.0.0.jar`, con las dependencias incluidas mediante Maven Shade. El JAR es un paquete Lambda, no una aplicacion Spring Boot para ejecutar con java -jar.

## Contrato del evento

El cuerpo del mensaje SQS es:

```json
{
  "version": 1,
  "tipo": "NOTIFICACION_SOLICITADA",
  "eventoId": "25fc6053-62bb-459a-a1ea-07940f648d7a",
  "notificacionId": 7
}
```

Los identificadores anteriores son ejemplos de formato. Usar la notificacion existente y el evento devuelto por POST /api/notificaciones/{id}/encolar. El mensaje no copia el correo ni el contenido del aviso a la cola.

Configurar `NOTIFICACIONES_BASE_URL` con la URL privada del backend; por ejemplo el balanceador interno y el prefijo /notificaciones. La funcion envia un intento a /api/notificaciones/{id}/intentos y confirma el registro solamente si el backend devuelve un ID y el mismo eventoId.

El microservicio conserva eventoId y evita crear un segundo intento si SQS entrega nuevamente el mismo evento. La funcion no mantiene esa proteccion en memoria: debe funcionar aunque AWS reemplace el entorno de ejecucion o ejecute varias instancias.

## Reintentos

Activar ReportBatchItemFailures en el event source mapping. La respuesta batchItemFailures incluye solo los messageId que fallaron; no se confirman mensajes cuyo backend no respondio correctamente. Los errores se reintentan y pueden enviarse a la cola de errores segun la politica de redrive.

El resultado ENVIADO identifica una simulacion academica del procesamiento. El detalle guardado lo declara expresamente. Esta funcion no envia correo ni SMS reales.

## Pruebas

Las pruebas verifican validacion de eventos, fallos parciales del lote, errores HTTP, confirmacion de persistencia, URI del backend y texto UTF-8. Utilizan un servidor HTTP local efimero y no requieren credenciales AWS ni modifican las bases del estudiante.
