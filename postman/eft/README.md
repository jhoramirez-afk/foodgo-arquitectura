# Colecciones EFT

- **CRUD Usuarios y direcciones**: Docker local, sin autenticación y sin entorno seleccionado.
  Captura IDs, modifica usuario/dirección y comprueba 400, 404, 409 y eliminación.
- **Acceso y SQS-Lambda**: API Gateway con firma IAM y entorno FoodGo AWS.
  El GET de resultado espera hasta 30 consultas en Runner con Delay 1000 ms.
- **Continuidad durante escalado**: solo GET, Runner secuencial; detener al finalizar.

No incluir claves ni tokens en los archivos. El host firmado se valida antes de enviar.
Los archivos no arrancan AWS. Las consultas SQL no modifican tablas.

Para el CRUD seleccionar carpetas y peticiones según el guion, deteniéndose antes
de la limpieza para mostrar la fila SQL. La petición 09 requiere un reinicio real de
la aplicación para acreditar persistencia. Ejecutar toda la colección sin ese
reinicio comprueba el contrato HTTP, pero no esa condición.

En Send individual no se ejecuta setNextRequest: esperar y repetir GET.
El éxito final requiere el evento publicado, un único intento y resultado ENVIADO.
Una espera agotada, un error HTTP o duplicados conservan un fallo de prueba.
