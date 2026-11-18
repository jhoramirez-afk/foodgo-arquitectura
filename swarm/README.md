# FoodGo con Docker Swarm

El archivo ../docker-stack.yml usa el formato Compose v3.8 admitido por docker stack deploy. Las imagenes se construyen y publican antes del despliegue. Los ocho docker-compose.yml de los microservicios conservan su uso local.

## Topologia inicial

Dos nodos EC2: un manager y un worker. Un contenedor por microservicio, Eureka, PostgreSQL y dos replicas del proxy de entrada. Las aplicaciones pueden distribuirse entre ambos nodos. PostgreSQL se restringe al nodo etiquetado foodgo.data=true y conserva sus datos en /srv/foodgo/postgres.

Esta topologia no proporciona tolerancia a la perdida del manager ni replicacion de PostgreSQL. La disponibilidad de la aplicacion se mejora al escalar replicas, pero no elimina esos puntos unicos. No se presentara como una arquitectura con alta disponibilidad completa.

## Comandos de administracion

CloudFormation inicializa el manager con su IP privada, agrega la etiqueta de datos e incorpora el worker. El token se transfiere mediante SSM SecureString. No repetir `swarm init` en un cluster activo ni imprimir el token durante la demostracion. Abrir Session Manager en la instancia manager y anteponer `sudo` si la sesion no tiene permiso sobre Docker.

En el manager, con las variables IMAGE_USUARIOS, IMAGE_RESTAURANTES, IMAGE_PEDIDOS, IMAGE_PAGOS, IMAGE_DELIVERY, IMAGE_NOTIFICACIONES, IMAGE_CUPONES, IMAGE_RESENAS, IMAGE_EUREKA y SQS_QUEUE_URL configuradas por el despliegue:

```sh
docker stack config -c docker-stack.yml
docker stack deploy --with-registry-auth -c docker-stack.yml foodgo
docker node ls
docker stack services foodgo
docker service ps foodgo_notificaciones
docker service scale foodgo_notificaciones=2
docker service ps foodgo_notificaciones
docker service scale foodgo_notificaciones=1
```

El despliegue debe crear los secretos externos foodgo_ep03_db_password y foodgo_ep03_db_root_password sin imprimir sus valores. CONFIG_VERSION identifica los archivos de configuracion inmutables de cada version. Las imagenes deben etiquetarse con el commit del codigo.

## Redes y persistencia

Solo el proxy publica el puerto 80 del nodo; las reglas AWS deben permitirlo exclusivamente desde el balanceador interno. Los ocho puertos de Java, Eureka y PostgreSQL permanecen dentro de la red overlay cifrada. El trafico de Swarm entre nodos debe limitarse al grupo de seguridad del cluster: TCP 2377, TCP/UDP 7946, UDP 4789 y ESP para el cifrado.

El proxy atiende /usuarios/, /restaurantes/, /pedidos/, /pagos/, /delivery/, /notificaciones/, /cupones/ y /resenas/. Por ejemplo /usuarios/api/usuarios llega a /api/usuarios del microservicio correspondiente.

El perfil cloud obtiene la clave desde /run/secrets/db_password y asigna a cada replica un identificador Eureka distinto. La conexion compartida de PostgreSQL contiene una base por dominio, propiedad de foodgo_app, que no tiene privilegios de superusuario. El limite de cuatro conexiones por pool mantiene acotado el uso de la base al escalar.

Un volumen local no se copia entre nodos. No escalar PostgreSQL mediante docker service scale ni mover su etiqueta a un nodo sin sus datos. Probar el reinicio y comparar los registros antes de afirmar que la persistencia funciona.
