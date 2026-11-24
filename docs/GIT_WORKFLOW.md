# Flujo de trabajo Git de FoodGo

Main conserva la entrega aprobada. Develop parte del main aprobado e integra avances.
Las ramas feature/* contienen cambios concretos y commits descriptivos con fechas reales.
La rama feature/eft-entrega reúne diagrama, colecciones y preparación del examen.

Antes de publicar: revisar git status, git diff --check y las validaciones locales.
Publicar la rama sin force y abrir PR hacia main para que el equipo revise el diff y el CI.
La fusión la realiza el estudiante autorizado; no se habilita auto-merge.
No reescribir historia ni agregar commits vacíos para aparentar avance.

El CI valida main, develop y feature, además de los PR. El workflow cloud únicamente
se activa por cambios en los componentes de despliegue indicados en su filtro paths,
o por ejecución manual. Documentación, diagramas, colecciones y pruebas de contrato
no deben crear ni reanudar recursos cloud.
