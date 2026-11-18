# FoodGo EP03 - AWS Academy Learner Lab

## Verificacion inicial, 17 de noviembre de 2026

Se inicio la sesion del Learner Lab y se comprobo mediante AWS STS que CloudShell usa la identidad temporal del laboratorio. Region seleccionada: us-east-1. El panel informaba Used $0 of $50; el presupuesto se actualiza con retraso, por lo que ese indicador no constituye una factura en tiempo real.

Inventario inicial en us-east-1: sin instancias EC2, repositorios ECR, colas SQS, APIs HTTP o REST ni instancias RDS. Se encontraron cinco funciones Lambda y un stack de CloudFormation del propio laboratorio; se conservaron. Se verificaron LabRole y LabInstanceProfile y la VPC predeterminada con seis subredes. No se crearon componentes FoodGo durante ese inventario.

Restricciones leidas en las instrucciones del laboratorio (actualizadas el 24 de junio de 2025):

- Regiones permitidas us-east-1 y us-west-2.
- Hasta nueve instancias EC2 simultaneas y 32 vCPU por region; tamanos permitidos hasta large, solo On-Demand.
- No se pueden crear usuarios, grupos ni roles IAM ordinarios. Reutilizar LabRole y LabInstanceProfile.
- LabRole tiene acceso de lectura a ECR; la identidad de la consola permite escribir. El despliegue no debe intentar publicar imagenes desde el rol de una instancia EC2.
- Lambda admite hasta diez ejecuciones concurrentes en el laboratorio.
- EBS admite volumenes de hasta 100 GB. La propuesta inicial de FoodGo usara solo la capacidad necesaria.
- Los recursos persisten entre sesiones; las instancias pueden detenerse y reiniciarse al reabrir el laboratorio. Las direcciones publicas pueden cambiar.

Consultar las restricciones vigentes en el README del Learner Lab antes de cada provision. El inventario demuestra acceso de lectura, no garantiza por si solo todos los permisos de escritura requeridos.

## Desarrollo

Las copias de trabajo se prepararon en feature/ep03-cloud a partir de los main verificados en GitHub. Se mantienen los originales del Escritorio y la version EP02 sin modificaciones durante el desarrollo inicial.

Primer componente: functions/notificaciones, funcion Lambda escrita en Java 21. Recibe eventos SQS de solicitudes de notificacion y llama al backend para registrar el intento. El identificador eventoId se conserva en todo el recorrido para evitar duplicados por reintentos.

El resultado ENVIADO corresponde a una simulacion academica del aviso. No representa un correo real ni un cobro bancario.

## Validacion local

Se construyeron nueve imagenes Linux/amd64 con bases fijadas por digest. Maven clean verify paso 243 pruebas dentro de las imagenes (241 en los ocho microservicios y dos en Eureka). La funcion Lambda paso otras 13 pruebas Java; los scripts de despliegue, diez pruebas Python sin AWS. CloudFormation paso cfn-lint y docker stack config acepto el archivo Swarm.

Una prueba Docker aislada con PostgreSQL 18 comprobo la inicializacion de las ocho bases, la lectura de secretos mediante configtree y dos replicas reales de Notificaciones. Dos solicitudes concurrentes del mismo evento produjeron un solo intento en PostgreSQL. Eureka registro ambas instancias UP con identificadores diferentes. El mensaje con tildes y Ñ se conservo tras reiniciar las aplicaciones y la base. Esta prueba local no es un cluster Swarm en AWS.

## Evidencias cloud pendientes

Cluster Swarm manager/worker en AWS; escalado bajo carga; despliegue desde CI/CD; Gateway protegido; productor y consumidor SQS reales; ejecucion de Lambda en AWS; resultado persistido y consulta distribuida de extremo a extremo. La compilacion y las pruebas locales no reemplazan estas evidencias. No se crearon recursos FoodGo ni se compartieron credenciales AWS durante la verificacion inicial y el desarrollo local.
