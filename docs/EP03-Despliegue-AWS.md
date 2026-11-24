# Desplegar FoodGo en AWS Academy Learner Lab

## Revisar antes de habilitar CD

El despliegue se limita a `us-east-1` o `us-west-2`, la cuenta configurada y una sesión temporal `voclabs` del Learner Lab. Reutiliza VPC predeterminada, dos subredes con Internet Gateway, `LabRole` y `LabInstanceProfile`. No usar una cuenta personal de facturación.

Recursos previstos: dos EC2 `t3.medium` con discos gp3 cifrados de 20 GB, ALB interno, VPC Link, HTTP API con IAM, nueve ECR, dos secretos de BD, S3 privado, SQS con DLQ, Lambda y logs con retención de siete días. No crea NAT Gateway, RDS ni roles/usuarios IAM. Consume presupuesto incluso fuera de la grabación.

Revisar y fusionar primero los ocho PR `feature/ep03-cloud`. Sus `application-cloud.yml` permiten montar secretos y evitan IDs Eureka repetidos al escalar. Notificaciones añade productor SQS, perfil `aws` e idempotencia. Después fusionar este repositorio. Mantener `AWS_DEPLOY_ENABLED` sin definir o en `false` durante la revisión. No modificar fechas ni reescribir `main`.

## Credenciales y variables

Iniciar Learner Lab y esperar el indicador verde. **AWS Details → AWS CLI** entrega tres valores temporales. Guardarlos únicamente como **Actions secrets** en `jhoramirez-afk/foodgo-arquitectura`, con autorización del administrador de la cuenta y repositorio:

| Secret | Origen |
|---|---|
| `AWS_ACCESS_KEY_ID` | `aws_access_key_id` de la sesión actual |
| `AWS_SECRET_ACCESS_KEY` | `aws_secret_access_key` de la sesión actual |
| `AWS_SESSION_TOKEN` | `aws_session_token` de la sesión actual |

No pegarlos en conversaciones, código, PR, capturas ni historial de terminal. Los workflows y administradores de ese repositorio podrán usar el acceso temporal mientras siga vigente. No duplicar estos secretos en los otros repositorios.

En **Settings → Secrets and variables → Actions → Variables**:

| Variable | Valor |
|---|---|
| `AWS_REGION` | `us-east-1` |
| `AWS_ACCOUNT_ID` | ID de 12 dígitos del Learner Lab, comprobado con STS |
| `AWS_DEPLOY_ENABLED` | `true`, al autorizar el despliegue |

No asumir `LabRole` desde Actions: su acceso ECR es de lectura en este laboratorio. El pipeline usa la sesión `voclabs`; EC2 y Lambda sí usan el perfil/rol existente. Al caducar la sesión, renovar los tres secretos. `ExpiredToken` no se corrige cambiando código. Si tu cuenta no administra Actions secrets, debe configurarlos el administrador del repositorio; no ampliar permisos IAM para sortear restricciones de Academy.

## Ejecutar y observar el pipeline

**Actions → Desplegar FoodGo en AWS Academy → Run workflow → main**. Habilitado CD, un push a `main` de este repositorio también lo dispara. Un cambio de microservicio ejecuta su CI propio; para publicar una nueva versión del conjunto ejecutar el workflow central. No hay disparo automático entre repositorios ni PAT compartido.

El pipeline:

1. Prueba Lambda y scripts; valida CloudFormation y Swarm.
2. Fija los nueve SHA de `main` en un manifiesto. Rechaza clientes sin perfil cloud.
3. Aprovisiona CloudFormation y sube JAR, manifiesto y configuración Swarm a S3 privado con un prefijo versionado.
4. Construye nueve imágenes con Maven y pruebas; publica etiquetas SHA inmutables en ECR. Conserva una imagen que ya exista.
5. Despliega mediante SSM en el manager. El worker se une con un token almacenado como SecureString. No abre SSH.
6. Comprueba ocho endpoints, rechazo sin firma IAM, backend privado, escalado bajo carga y Notificaciones → SQS → Lambda → intento persistido.
7. Conserva `foodgo-aws-ep03-evidencia` como artefacto real.

Un archivo con `estado: EN_CURSO` indica que la prueba no terminó correctamente. Sin evidencia no se declara validado. Revisar el primer error antes de repetir. Un fallo de build posterior a la provisión puede dejar recursos activos generando costos.

## Comandos directos

Estos comandos van en **AWS CloudShell** (Bash):

```bash
aws sts get-caller-identity --query Account --output text
aws cloudformation describe-stacks --stack-name foodgo-ep03-cluster --query 'Stacks[0].StackStatus' --output text
aws cloudformation describe-stacks --stack-name foodgo-ep03-mensajeria --query 'Stacks[0].StackStatus' --output text
aws lambda get-function-configuration --function-name foodgo-notificaciones-ep03 --query '{Runtime:Runtime,Estado:State,Memoria:MemorySize,Timeout:Timeout}'
aws logs tail /aws/lambda/foodgo-notificaciones-ep03 --since 5m
```

No proyectar STS completo si contiene el correo del alumno. No imprimir contraseñas, credenciales ni tokens de unión.

Para Docker: **EC2 → foodgo-ep03-manager → Connect → Session Manager**. Dentro del manager:

```bash
sudo docker node ls
sudo docker stack services foodgo
sudo docker service ps foodgo_notificaciones
sudo docker service scale foodgo_notificaciones=2
sudo docker service ps foodgo_notificaciones
sudo docker service scale foodgo_notificaciones=1
sudo docker service logs --tail 20 foodgo_notificaciones
```

Mantener peticiones HTTP activas durante el escalado. Verificar nuevas tareas `Running` y respuestas correctas. Se cambia el número de tareas, no de EC2. No escalar PostgreSQL a dos réplicas sobre un mismo volumen. No ejecutar `swarm init` en el equipo personal.

Eureka no se publica como ruta administrativa en Internet. Puede mostrarse localmente o inspeccionarse en la red interna. Complementa el registro de instancias; no sustituye la evidencia de nodos y tareas de Swarm.

## Datos y recuperación

Secrets Manager genera las contraseñas. Docker secrets las monta y `application-cloud.yml` las lee con `configtree:/run/secrets/`. No van en Dockerfiles ni variables públicas de Actions. `foodgo_app` es un rol sin superusuario, propietario de las ocho bases del ejercicio; se conserva una base por dominio.

PostgreSQL está fijado al nodo `foodgo.data=true`, en `/srv/foodgo/postgres`. No borrar volumen ni reinicializar el directorio. Respaldar antes de migrar datos. La política del stack impide reemplazar/borrar manager y secretos en actualizaciones ordinarias; no equivale a backup ni bloquea un borrado completo del stack.

El AMI se fija al crear el cluster y se conserva después. Actualizar imágenes de aplicación no reemplaza el nodo de datos. Las actualizaciones fallidas de tareas tienen rollback configurado; revisar tareas y logs antes de forzarlo.

El parámetro `InternalAlbName` conserva el nombre físico del balanceador que ya administra CloudFormation, incluso si una recuperación lo cambió. El pipeline obtiene ese nombre del recurso `InternalAlb`; no vuelve al nombre inicial al actualizar. Así evita reemplazar el ALB y asociar su grupo de destinos a dos balanceadores durante la transición.

Si la provisión termina en rollback, el log muestra el recurso fallido y su `ResourceStatusReason`. Revisar ese motivo antes de reintentar. `UPDATE_ROLLBACK_COMPLETE` permite preparar una actualización corregida; no es necesario borrar el stack ni las bases.

## Presupuesto y cierre

Deshabilitar `AWS_DEPLOY_ENABLED` y retirar los secretos temporales cuando no se usarán. `End Lab` no garantiza que ALB, ECR, S3 y discos dejen de consumir presupuesto. Detener EC2 tampoco elimina esos cargos. Revisar recursos y presupuesto, considerando el retraso del panel de Academy.

La limpieza definitiva requiere respaldo y revisión. ECR, secretos y disco del manager tienen retención; no desaparecen al borrar CloudFormation. No borrarlos a ciegas ni eliminar las funciones/stack iniciales de Academy. Este proyecto no ejecuta una limpieza destructiva automática.
