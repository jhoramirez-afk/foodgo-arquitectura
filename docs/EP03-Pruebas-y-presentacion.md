# Evidencia y presentación EP03

EP03 exige video de **3 a 8 minutos**, narrado por ambos integrantes. El guion largo de EP02 no cambia ese requisito. Preparar ventanas y resultados; explicar qué se comprueba.

## Prueba local

En CMD de VS Code, dentro del microservicio elegido, comprobar que existe `pom.xml`. No ejecutar Maven desde la carpeta que agrupa todos los repositorios.

```cmd
java -version
mvn -version
mvn clean verify
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d --build
docker compose ps
```

El `.env` local, excluido de Git, debe definir contraseña. No mostrarlo. Cada README indica puertos; Usuarios usa normalmente `http://127.0.0.1:18081`. Mostrar un GET correcto y un error en Postman. `docker compose stop` detiene ese proyecto sin borrar datos. No detener otras aplicaciones.

Abrir el Dockerfile: etapa Maven con pruebas, JAR copiado a Java 21, usuario sin privilegios y healthcheck. El build cloud también queda registrado en Actions.

## Gateway y flujo asíncrono en Postman

Importar `postman/FoodGo-EP03-AWS.postman_collection.json`. Configurar `api_base_url` con el `ApiEndpoint` de CloudFormation. La autorización **AWS Signature** usa región, servicio `execute-api` y las tres credenciales temporales. Mantenerlas locales o en Vault; no sincronizar/exportar secretos. La colección distribuida no los contiene.

1. GET Usuarios sin autorización: **403**, rechazo de Gateway por falta de firma.
2. GET Usuarios autorizado: **200**. Mostrar ocho GET por el mismo Gateway.
3. Crear una notificación con datos legibles. `POST /notificaciones/api/notificaciones/{id}/encolar`: **202**, `ENCOLADO` y `eventoId`.
4. GET de intentos de ese ID: esperar el mismo `eventoId`. 202 confirma aceptación en cola, no que Lambda ya terminó.
5. En AWS mostrar SQS, su disparador Lambda y el log `Procesado mensaje=... evento=...`. Volver a Postman: el resultado quedó persistido.

No repetir los POST innecesariamente al grabar; reutilizar el ID o borrar únicamente el registro de la prueba. No deducir identidad por nombre; comparar ID y correo.

SQS entrega al menos una vez. El consumidor Lambda llama por HTTP privado a Notificaciones; `(notificacion_id, evento_id)`, transacción y bloqueo del padre evitan intentos duplicados ante reentregas concurrentes. Un fallo se devuelve en `batchItemFailures` para reintentar; después de tres recepciones fallidas pasa a DLQ. El resultado es una simulación académica, sin proveedor de correo/SMS.

`python scripts/smoke.py --scale --async-flow` usa AWS y HTTP reales. Envía dos reentregas del mismo evento, confirma sus IDs en CloudWatch y comprueba un solo intento. Es evidencia del comprobador Python, no del Runner gráfico de Postman.

## Matriz de evidencia

| IE | Mostrar | Evidencia |
|---|---|---|
| 1 | Dockerfiles reproducibles | Ocho repositorios y builds |
| 2 | Docker local y endpoint | `compose ps`, Postman |
| 3 | Compose y Swarm | Archivos, red, volumen, `deploy` |
| 4 | Build, test y deploy automático | Workflow y ejecución real |
| 5 | Provisión desde pipeline | CloudFormation y job `provisionar` |
| 6 | Ocho dominios funcionando en cloud | Ocho GET por Gateway |
| 7 | Manager y worker | `node ls`, servicios, tareas |
| 8 | Escalado bajo carga | Réplicas 1→2→1 y respuestas reales |
| 9 | Justificar decisiones | Escala por dominio y límites del laboratorio |
| 10 | FaaS en código y configuración | Handler Java, JAR y plantilla |
| 11 | Cola cloud | SQS, DLQ y disparador |
| 12 | Proteger backend | 403 sin firma / 200 con firma, ALB interno |
| 13 | Función integrada | SQS → Lambda → HTTP privado |
| 14 | Productor-consumidor completo | 202, evento, log, intento persistido |
| 15 | Flujo distribuido y escalado | Evidencia real y tareas |
| 16 | Orden técnico | Hilo conductor del video |
| 17 | Audio | Voz clara de ambos estudiantes |

## Distribución de ocho minutos

| Tiempo | Integrante | Pantalla y explicación |
|---|---|---|
| 0:00–0:40 | 1 | Arquitectura y alcance académico |
| 0:40–1:35 | 1 | Dockerfile, Compose, contenedores y GET local |
| 1:35–2:35 | 1 | Pipeline real, pruebas, CloudFormation e imágenes SHA |
| 2:35–3:35 | 2 | AWS, manager/worker y servicios Swarm |
| 3:35–4:25 | 2 | Gateway: 403 sin firma y 200 con firma; backend privado |
| 4:25–6:10 | 2 | POST encolar, SQS, Lambda, resultado e idempotencia |
| 6:10–7:25 | 1 | Escalar 1→2→1 con peticiones activas, tareas y respuestas |
| 7:25–8:00 | Ambos | Resultado, límites de disponibilidad y cierre |

No afirmar alta disponibilidad completa: existe un solo manager y un solo nodo PostgreSQL. Réplicas y balanceo mejoran capacidad y permiten observar continuidad durante el escalado; no eliminan esos puntos de fallo.
