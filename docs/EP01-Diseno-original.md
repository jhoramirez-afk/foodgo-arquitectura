> Documento histórico de la propuesta EP01. La arquitectura implementada está en el README y en diagrama/FoodGo_Arquitectura.png.

# FoodGo — Arquitectura de Microservicios

**Evaluación Parcial N°1 · JVY0101 — Java: Diseño y Construcción de Soluciones Nativas en Nube**
Encargo (diagrama) + Presentación (video), trabajo en parejas.

> Este repositorio es el **documento de arquitectura e índice del proyecto**: aquí se explica el caso
> de negocio, los requisitos y las decisiones de diseño, y se enlaza a los 8 repositorios independientes
> (uno por microservicio). No contiene código — cada microservicio vive en su propio repo, para que
> pueda desarrollarse, desplegarse y versionarse de forma independiente (RNF-03, IE10).

---

## 1. Integrantes

| Nombre | Rol en la entrega |
|---|---|
| _Jhohan Ramírez_ | diagrama / código|
| _Alex Llanten_ | video / documentación |

## 2. El caso: FoodGo

FoodGo es una aplicación de delivery de comida a domicilio que conecta clientes, restaurantes y
repartidores. Permite armar pedidos, pagar en línea y hacer seguimiento en tiempo real hasta la
entrega.

- **Rubro**: FoodTech / Delivery
- **Actores**: clientes, restaurantes aliados, repartidores
- **Escala esperada**: miles de pedidos diarios, con picos en horas de almuerzo y cena
- **Problema de negocio**: coordinar 3 actores con estados que cambian en minutos, sin que un fallo
  de pagos detenga la creación de pedidos ni que un pico de demanda pierda pedidos

## 3. Diagrama de arquitectura

El diagrama general del sistema (componentes, patrones, flujos de comunicación, seguridad y flujos de
datos críticos) está en [`diagrama/EP01/FoodGo_Arquitectura.drawio`](diagrama/EP01/FoodGo_Arquitectura.drawio)
(editable en [app.diagrams.net](https://app.diagrams.net)) y su export como imagen en
`diagrama/EP01/FoodGo_Arquitectura.jpg` — **recuerden exportar el PNG antes de entregar**, es lo
que se copia directamente en AVA.

## 4. Requisitos funcionales (RF)

| Código | Requisito | Dominio | Repositorio |
|---|---|---|---|
| RF-01 | Registro y autenticación de clientes, restaurantes y repartidores | Usuarios | `foodgo-ms-usuarios` |
| RF-02 | Publicar menú con precios, disponibilidad y horarios | Restaurantes | `foodgo-ms-restaurantes` |
| RF-03 | Armar y confirmar pedidos (carrito, dirección, tiempo estimado) | Pedidos | `foodgo-ms-pedidos` |
| RF-04 | Procesar el pago del pedido y las propinas | Pagos | `foodgo-ms-pagos` |
| RF-05 | Asignar repartidor y mostrar seguimiento GPS en tiempo real | Delivery | `foodgo-ms-delivery` |
| RF-06 | Notificar estados del pedido a cliente y restaurante | Notificaciones | `foodgo-ms-notificaciones` |
| RF-07 | Aplicar cupones y descuentos | Cupones | `foodgo-ms-cupones` |
| RF-08 | Calificar el pedido (comida y repartidor) | Reseñas | `foodgo-ms-resenas` |

## 5. Requisitos no funcionales (RNF)

| Código | Criterio | Requerimiento | Cómo se aborda |
|---|---|---|---|
| RNF-01 | Escalabilidad | Absorber picos de pedidos (almuerzo/cena) | Pedidos y Pagos escalan por separado; cada microservicio es independiente |
| RNF-02 | Disponibilidad | La creación de pedidos sigue aunque Pagos o Notificaciones fallen | Comunicación asíncrona vía eventos/colas, Circuit Breaker en llamadas síncronas |
| RNF-03 | Mantenibilidad | Servicios pequeños por dominio, despliegue independiente | 8 microservicios, **cada uno en su propio repositorio** con su propio pipeline CI/CD |
| RNF-04 | Seguridad | Autenticación por rol, cifrado de datos de pago, control de acceso | JWT por rol (Cognito), tokenización de pagos, cifrado TLS/at-rest (KMS) |
| RNF-05 | Rendimiento | Confirmación de pedido < 3s; GPS con latencia < 5s | Aislamiento del servicio de Delivery, DynamoDB con baja latencia |
| RNF-06 | Consistencia | Los pedidos no se pierden ante fallas; pago atómico con el pedido | Persistencia + colas (SQS), patrón Saga (Pedido → Pago → Delivery) |

## 6. Microservicios — un repositorio por servicio

| # | Repositorio | Responsabilidad (SRP) | Enlace |
|---|---|---|---|
| 1 | `foodgo-ms-usuarios` | Identidad, autenticación y perfiles de los 3 actores | https://github.com/`<usuario>`/foodgo-ms-usuarios |
| 2 | `foodgo-ms-restaurantes` | Catálogo de restaurantes, menús, horarios y disponibilidad | https://github.com/`<usuario>`/foodgo-ms-restaurantes |
| 3 | `foodgo-ms-pedidos` | Carrito, creación, estados y ciclo de vida del pedido | https://github.com/`<usuario>`/foodgo-ms-pedidos |
| 4 | `foodgo-ms-pagos` | Cobro, propinas, reembolsos y conciliación | https://github.com/`<usuario>`/foodgo-ms-pagos |
| 5 | `foodgo-ms-delivery` | Asignación de repartidor y tracking GPS en tiempo real | https://github.com/`<usuario>`/foodgo-ms-delivery |
| 6 | `foodgo-ms-notificaciones` | Alertas de estado del pedido a los 3 actores | https://github.com/`<usuario>`/foodgo-ms-notificaciones |
| 7 | `foodgo-ms-cupones` | Emisión, validación y aplicación de descuentos | https://github.com/`<usuario>`/foodgo-ms-cupones |
| 8 | `foodgo-ms-resenas` | Calificaciones y comentarios de pedidos | https://github.com/`<usuario>`/foodgo-ms-resenas |

> Reemplacen `<usuario>` por su usuario/organización de GitHub una vez publicados. Esta tabla —
> junto con el link de este mismo repo `foodgo-arquitectura` — es lo que se copia en AVA como
> "varios enlaces a Github" (9 enlaces en total).

Cada repositorio de microservicio trae, de forma independiente:

- Código fuente completo (Spring Boot 3.3, Java 21)
- `README.md` propio
- `docs/00-04` (resumen, arquitectura, API, pruebas, despliegue)
- `Dockerfile` + `docker-compose.yml`
- **`.github/workflows/ci.yml`** — pipeline CI/CD que compila, corre tests (unitarios + Cucumber) y verifica cobertura JaCoCo en cada push

## 7. Patrones de diseño aplicados

| Patrón | Dónde se aplica | Qué resuelve |
|---|---|---|
| **API Gateway** | Punto de entrada único para clientes, restaurantes y repartidores | Enruta, autentica (JWT) y expone una sola API pública |
| **Service Registry** (AWS Cloud Map) | Todos los microservicios | Descubrimiento dinámico de instancias sin direcciones fijas |
| **Circuit Breaker** | Pedidos → Restaurantes (disponibilidad), Pedidos → Cupones (validación) | Evita que la caída de un servicio dependiente tumbe a Pedidos |
| **Saga (coreografía por eventos)** | Pedido → Pago → Delivery | Coordina una transacción distribuida sin bloqueo entre servicios |
| **Colas (Amazon SQS)** | Pedidos → Pagos | Desacopla la creación del pedido del procesamiento del pago; persiste ante fallas (RNF-06) |
| **Event bus (Amazon EventBridge)** | Pago/Delivery → Notificaciones | Un evento, múltiples suscriptores (fan-out) sin acoplar al productor |
| **Serverless (AWS Lambda)** | Procesamiento de pago, notificaciones | Escala a cero entre picos, solo se paga por ejecución |

## 8. Seguridad

| Zona | Control |
|---|---|
| API Gateway | Autenticación JWT por rol (Cognito) |
| ms-usuarios | Credenciales aisladas, nunca en logs |
| ms-pagos | Tokenización de tarjeta (sin PAN almacenado), cumplimiento PCI |
| Todas las bases de datos | Cifrado at-rest (KMS) |
| Todas las comunicaciones | Cifrado en tránsito (TLS) |
| Secretos (credenciales BD, pasarela) | AWS Secrets Manager con rotación |

## 9. Flujo de datos crítico

```
Cliente confirma pedido
   → API Gateway (autenticación)
   → ms-pedidos (persiste, valida disponibilidad y cupón vía Circuit Breaker)
   → evento "pedido-creado" → Amazon SQS   (punto de monitoreo: profundidad de cola)
   → AWS Lambda dispara ms-pagos (tokenización, cobro)
   → evento "pago-confirmado" → Amazon EventBridge
   → ms-delivery asigna repartidor y comienza tracking GPS
   → en cada transición → ms-notificaciones informa a cliente, restaurante y repartidor
```

## 10. Trazabilidad con la pauta EP01

| Indicador | Dónde se evidencia |
|---|---|
| IE1, IE2, IE3 (requisitos y elección de microservicios) | Secciones 4, 5 y 6 de este README + video |
| IE4 (diagrama claro) | `diagrama/EP01/FoodGo_Arquitectura.drawio` |
| IE5 (patrones de diseño) | Sección 7 + diagrama |
| IE6 (flujos y tecnologías cloud) | Sección 9 + diagrama |
| IE7 (seguridad) | Sección 8 + diagrama |
| IE8 (flujos de datos críticos) | Sección 9 + diagrama |
| IE9, IE10, IE11 (delimitación, interdependencias, división lógica) | Sección 6 (repos independientes = bajo acoplamiento) + `docs/01_Arquitectura.md` de cada repo |
| IE12, IE13 (video: orden, lenguaje técnico, audio) | [`docs/video/`](docs/video/) — enlace o archivo del video |

## 11. Entrega final en AVA

```
Diagrama: [imagen PNG adjunta, exportada de diagrama/EP01/FoodGo_Arquitectura.drawio]

Repositorios (9 enlaces):
- Arquitectura (este repo): https://github.com/jhoramirez-afk/foodgo-arquitectura
- ms-usuarios:               https://github.com/jhoramirez-afk/foodgo-ms-usuarios
- ms-restaurantes:            https://github.com/jhoramirez-afk/foodgo-ms-restaurantes
- ms-pedidos:                 https://github.com/jhoramirez-afk/foodgo-ms-pedidos
- ms-pagos:                   https://github.com/jhoramirez-afk/foodgo-ms-pagos
- ms-delivery:                https://github.com/jhoramirez-afk/foodgo-ms-delivery
- ms-notificaciones:          https://github.com/jhoramirez-afk/foodgo-ms-notificaciones
- ms-cupones:                 https://github.com/jhoramirez-afk/foodgo-ms-cupones
- ms-resenas:                 https://github.com/jhoramirez-afk/foodgo-ms-resenas

Video: [archivo adjunto o enlace]
```
