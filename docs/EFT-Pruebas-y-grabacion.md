# FoodGo EFT: preparación y evidencias

La entrega reúne los ocho microservicios, Eureka y este repositorio de arquitectura.
El diagrama actual representa los componentes implementados. EP01 se conserva como antecedente.

## Antes de grabar

1. Revisar el código aprobado y la sesión local de Docker Desktop.
2. Usar Java 21. Ejecutar Maven dentro de cada carpeta con pom.xml.
3. Preparar los Compose locales y comprobar app/postgres saludables.
4. Importar las tres colecciones de postman/eft. Para CRUD local usar No Environment.
5. En pgAdmin conectar la base del contenedor Usuarios: 127.0.0.1:54321,
   base foodgo_usuarios, usuario foodgo_ep02 y clave local ya configurada.
6. No confundir PostgreSQL Docker con el servidor nativo de Windows.
7. Preparar la sesión AWS solo cuando se autorice retomar la grabación.
   Esta preparación y el CI del material no inicializan AWS.

## Evidencias del examen

| Indicadores | Comprobación |
|---|---|
| IE1, IE2 | Diagrama completo: dominios, bases y flujos HTTP / SQS-Lambda |
| IE3 | controller/service/repository/model e inyección por constructor |
| IE4, IE5 | CRUD HTTP y escenarios 400, 404 y 409 esperados |
| IE6, IE8 | pom, perfil postgres, entidades OneToMany/ManyToOne y FK SQL |
| IE7 | Misma fila por HTTP y SQL, actualización, reinicio de app y eliminación |
| IE9 | mvn clean verify, pruebas y JAR ejecutable de Spring Boot |
| IE10 | main/develop/feature, commits reales y PR revisado |
| IE11 | Dockerfile multietapa, cache, usuario sin privilegios e imagen funcional |
| IE12, IE16 | docker-stack.yml y clúster con manager y worker Ready |
| IE13-IE15 | Configuración CI/CD, provisión y ejecución cloud exitosa con endpoints |
| IE17 | 2/2 con dos tareas Running, continuidad, carga diferenciada y retorno 1/1 |
| IE18 | POST 202, eventoId, log de Lambda y un resultado persistido |
| IE19, IE20 | Hilo conductor, explicación propia y audio revisado |

## Docker local

Cada microservicio tiene su propio Compose. Las API publican 18081-18088 y las bases
54321-54328. Dentro del contenedor PostgreSQL escucha en 5432.

~~~sh
docker compose build app
docker compose up -d --wait
docker compose ps
~~~

No ejecutar docker compose config con contraseñas visibles durante la grabación.
El archivo docker-stack.yml se despliega en el manager cloud con imágenes publicadas,
no se sustituye por los Compose locales.

## CRUD y persistencia

La colección de Usuarios captura los IDs devueltos al crear. El PUT de usuario usa su ID;
el PUT de dirección utiliza el ID de dirección. La última carpeta elimina solo lo creado
por esa secuencia. Detenerse antes de eliminar para mostrar SQL y el reinicio de app.
El archivo postman/eft/FoodGo-EFT-Consultas.sql contiene únicamente lecturas.

La petición 09 por sí sola no reinicia nada. Para probar persistencia, reiniciar
realmente app, esperar healthy y repetir la consulta; no eliminar el volumen.
Una ejecución automática de toda la colección no acredita ese reinicio.

## Swarm y carga

En Session Manager de la EC2 manager, no en CloudShell:

~~~sh
sudo docker node ls
sudo docker stack services foodgo
sudo docker service scale --detach=false foodgo_notificaciones=2
sudo docker service ls --filter name=foodgo_notificaciones
sudo docker service ps foodgo_notificaciones --filter desired-state=running
~~~

Esperar 2/2 y dos estados CURRENT STATE Running antes de reducir. Mantener el Runner
de continuidad y comprobar un evento mientras hay dos réplicas. Después volver a 1/1.
El Runner funcional es secuencial; no presentarlo como cuatro clientes concurrentes.
Las métricas del pipeline tienen su propia fecha y SHA y deben identificarse como tales.
Cambiar simultáneamente carga y réplicas no aísla una mejora causal de latencia.

## Cola y función

Usar el entorno FoodGo AWS con valores temporales exclusivamente locales.
Enviar 03 Crear aviso y 04 Publicar evento. El 202 confirma aceptación, no finalización.
En Runner configurar Delay 1000 ms: 05 espera hasta 30 consultas y exige un único
ENVIADO del mismo evento. En Send individual esperar y repetir GET manualmente.
No volver a publicar para esperar el resultado.

Comparar eventoId en Postman, CloudWatch y el intento persistido.
Los avisos y pagos son registros académicos; no hay correo ni cobro reales.

## Evidencias y límites

Las validaciones estáticas se ejecutan con:

~~~sh
node postman/tests/validate-eft.cjs
python -m unittest discover -s scripts/tests -v
~~~

No se deben presentar sus resultados como un Runner gráfico o un ensayo cloud.
El run #5, SHA 13956a745638500a21fef422ba942a1d3e106a23, es evidencia histórica del
despliegue EP03; no demuestra que la sesión del laboratorio siga activa.
La grabación final requiere peticiones y estados reales en esa sesión.
Un manager y PostgreSQL sin réplica conservan puntos únicos de fallo.
No afirmar alta disponibilidad completa, TLS de extremo a extremo ni autoscalado por CPU.
