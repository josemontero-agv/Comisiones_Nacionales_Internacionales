# Skill: Extracción de Requisitos y Diseño de Base de Datos

## 📋 Descripción

Esta skill permite al agente de Cursor extraer sistemáticamente requisitos funcionales, no funcionales y diseño completo de base de datos desde documentación técnica existente (PDFs, Markdown, Word, etc.).

## 🎯 Cuándo se Activa Automáticamente

El agente usará esta skill cuando detecte:
- Solicitudes de extracción de requisitos
- Análisis de documentación técnica
- Diseño o modelado de base de datos
- Palabras clave: "requisitos", "requirements", "especificaciones", "modelo de datos", "diseño de BD", "tablas", "schema"

## 📁 Estructura de Archivos

```
extract-requirements-db-design/
├── SKILL.md              # Instrucciones principales para el agente
├── examples.md           # Ejemplo completo usando proyecto Pharmadix
├── quick-reference.md    # Referencia rápida y checklists
└── README.md            # Este archivo (documentación para humanos)
```

## 🚀 Cómo Usar

### Uso Básico

Simplemente pide al agente que extraiga requisitos de tu documentación:

```
"Extrae los requisitos y diseño de base de datos de @Documentacion_Realizada/"
```

```
"Analiza @arquitectura.pdf y genera el modelo de datos"
```

```
"Necesito los requisitos funcionales del proyecto según @especificaciones.md"
```

### Uso Avanzado

Puedes ser más específico:

```
"Extrae requisitos y diseño de BD de @docs/ y genera también los scripts SQL"
```

```
"Analiza @informe.pdf y crea un documento de especificaciones con diagramas Mermaid"
```

```
"Revisa @plan.md y extrae solo los requisitos no funcionales"
```

## 📤 Qué Genera

La skill produce un documento Markdown estructurado con:

### 1. Requisitos Funcionales (RF-XXX)
- Descripción clara de cada funcionalidad
- Actor que la utiliza
- Prioridad (Must/Should/Could Have)
- Criterios de aceptación verificables

### 2. Requisitos No Funcionales (RNF-XXX)
- Rendimiento (transacciones/seg, latencia)
- Seguridad (autenticación, auditoría)
- Disponibilidad (uptime, offline)
- Escalabilidad (usuarios, volumen)
- Usabilidad (UX, accesibilidad)

### 3. Diseño de Base de Datos
- **Tablas Maestras**: Catálogos y datos de referencia
- **Tablas Transaccionales**: Operaciones del negocio
- **Tablas de Auditoría**: Trazabilidad y logs
- Para cada tabla:
  - Propósito y descripción
  - Campos con tipos de datos
  - Restricciones (PK, FK, NOT NULL, UNIQUE)
  - Índices recomendados
  - Relaciones con otras tablas

### 4. Diagramas Visuales
- Diagrama Entidad-Relación (Mermaid)
- Diagramas de flujo (si aplica)

### 5. Reglas de Negocio (RN-XXX)
- Validaciones de integridad
- Cálculos automáticos
- Restricciones de estado
- Implementación sugerida

### 6. Scripts SQL (Opcional)
- DDL completo (CREATE TABLE)
- Triggers para reglas de negocio
- Índices y constraints
- Datos de ejemplo

## 💡 Ejemplo Real

Basado en el proyecto Pharmadix, la skill extrajo:

**Entrada:**
- `Arquitectura y Diseño Técnico (1).pdf`
- `Informe Ejecutivo_ Digitalización de Tiempos Pharmadix.pdf`
- `Flujo_Procesos_Pharmadix.md`

**Salida:**
- 10+ Requisitos Funcionales detallados
- 5+ Requisitos No Funcionales con métricas
- 5 Tablas completamente especificadas
- Diagrama ER con relaciones
- 4 Reglas de Negocio implementables
- Scripts SQL listos para ejecutar

Ver `examples.md` para el ejemplo completo.

## ✅ Mejores Prácticas

1. **Proporciona todos los documentos**: Menciona carpetas o archivos específicos con `@`
2. **Especifica si necesitas SQL**: Indica si quieres scripts además del diseño
3. **Revisa el resultado**: Valida que no falte información crítica
4. **Itera si es necesario**: Pide ajustes o información adicional

## 🎓 Aprendizaje

### Para Desarrolladores
Esta skill te enseña:
- Cómo estructurar requisitos funcionales y no funcionales
- Mejores prácticas de diseño de base de datos
- Nomenclatura y convenciones SQL
- Uso de diagramas Mermaid para documentación

### Para Project Managers
Te ayuda a:
- Validar completitud de especificaciones
- Identificar requisitos faltantes
- Comunicar diseño técnico al equipo
- Mantener trazabilidad entre docs y BD

## 🔧 Personalización

Puedes modificar `SKILL.md` para:
- Agregar convenciones específicas de tu empresa
- Incluir plantillas personalizadas
- Añadir validaciones adicionales
- Integrar con herramientas específicas

## 📚 Archivos de Referencia

- **SKILL.md**: Instrucciones completas para el agente (lectura técnica)
- **examples.md**: Ejemplo paso a paso con Pharmadix (muy útil para entender)
- **quick-reference.md**: Checklists y plantillas rápidas (consulta frecuente)

## 🤝 Contribuir

Si mejoras esta skill:
1. Documenta los cambios en este README
2. Actualiza los ejemplos si es necesario
3. Mantén la concisión (SKILL.md < 500 líneas)

## 📞 Soporte

Si la skill no se activa automáticamente:
- Usa palabras clave explícitas: "extrae requisitos", "diseño de BD"
- Menciona archivos específicos con `@`
- Verifica que los documentos estén en el workspace

## 🏆 Casos de Uso

✅ **Ideal para:**
- Proyectos nuevos que requieren diseño de BD
- Migración de sistemas legacy (extraer modelo actual)
- Documentación de sistemas existentes
- Auditorías de arquitectura
- Onboarding de nuevos desarrolladores

❌ **No ideal para:**
- Generación de requisitos desde cero (sin documentación)
- Análisis de código fuente (usa otras skills)
- Optimización de BD existente (requiere análisis de performance)

## 📊 Métricas de Calidad

Una buena extracción debe tener:
- ✅ Todos los requisitos numerados consecutivamente
- ✅ Cada tabla con al menos: nombre, propósito, campos, PK, índices
- ✅ Todas las FK con su tabla referenciada
- ✅ Tipos de datos específicos (no genéricos)
- ✅ Diagrama ER que coincida con las tablas
- ✅ Referencias a documentos fuente

## 🎯 Roadmap

Mejoras futuras planeadas:
- [ ] Validación automática de consistencia
- [ ] Generación de migraciones (Alembic, Flyway)
- [ ] Exportación a herramientas de modelado (dbdiagram.io)
- [ ] Análisis de normalización (1NF, 2NF, 3NF)
- [ ] Sugerencias de optimización

---

**Versión**: 1.0  
**Última actualización**: Enero 2026  
**Autor**: Creada para proyecto Pharmadix  
**Licencia**: Uso interno del proyecto
