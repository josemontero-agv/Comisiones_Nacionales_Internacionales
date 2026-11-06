---
name: extract-requirements-db-design
description: Extrae requisitos funcionales, no funcionales y diseño de base de datos desde documentación técnica (PDFs, Markdown, Word). Genera especificaciones estructuradas con tablas, campos, relaciones y diagramas. Usa cuando el usuario pida extraer requisitos, analizar documentación técnica, diseñar base de datos, o mencione "requirements", "especificaciones", "modelo de datos", "tablas", "schema".
---

# Extracción de Requisitos y Diseño de Base de Datos

Esta skill te guía para extraer sistemáticamente requisitos y diseño de base de datos desde documentación técnica existente, generando especificaciones estructuradas y listas para implementación.

## Cuándo Usar Esta Skill

- El usuario solicita extraer requisitos de documentos técnicos
- Necesitas analizar documentación para diseñar una base de datos
- Hay PDFs, documentos Word o Markdown con especificaciones técnicas
- Se requiere estructurar información dispersa en múltiples documentos
- El usuario menciona: "extrae requisitos", "diseño de BD", "modelo de datos", "especificaciones"

## Proceso de Extracción

### 1. Identificar Fuentes de Información

Busca y lee todos los documentos relevantes:

```bash
# Buscar documentos técnicos comunes
**/*.pdf
**/*arquitectura*.pdf
**/*diseño*.pdf
**/*especificaciones*.md
**/*requirements*.md
**/Documentacion*/**
```

Lee completamente:
- PDFs de arquitectura técnica
- Informes ejecutivos
- Documentos de flujo de procesos
- Especificaciones funcionales
- Diagramas existentes

### 2. Extraer Requisitos Funcionales

Identifica y documenta:

**Formato de salida:**

```markdown
## Requisitos Funcionales

### RF-001: [Nombre del Requisito]
- **Descripción**: [Qué debe hacer el sistema]
- **Actor**: [Quién lo usa]
- **Prioridad**: Must Have | Should Have | Could Have
- **Criterios de Aceptación**:
  - [ ] Criterio 1
  - [ ] Criterio 2
```

**Buscar en documentos:**
- Verbos de acción: "debe permitir", "el sistema registra", "captura", "calcula"
- Casos de uso y flujos de trabajo
- Funcionalidades descritas en diagramas de secuencia
- Historias de usuario

### 3. Extraer Requisitos No Funcionales

**Formato de salida:**

```markdown
## Requisitos No Funcionales

### Rendimiento
- **RNF-001**: Soportar X transacciones/segundo con latencia < Yms
- **RNF-002**: Tiempo de respuesta de consultas < Z segundos

### Seguridad
- **RNF-003**: Cumplimiento de principios ALCOA+ para auditoría
- **RNF-004**: Autenticación y autorización por roles

### Disponibilidad
- **RNF-005**: Soporte offline-first con sincronización automática
- **RNF-006**: Disponibilidad del 99.X%

### Escalabilidad
- **RNF-007**: Capacidad para X usuarios concurrentes
```

**Buscar en documentos:**
- Métricas de rendimiento (transacciones/seg, latencia, tiempo de respuesta)
- Requisitos de seguridad y cumplimiento normativo
- Necesidades de disponibilidad y tolerancia a fallos
- Capacidad y escalabilidad proyectada

### 4. Extraer Diseño de Base de Datos

#### A. Identificar Entidades y Tablas

**Formato de salida:**

```markdown
## Modelo de Base de Datos

### Tablas Maestras (Catálogos)

#### NOMBRE_TABLA
**Propósito**: [Descripción de qué almacena]

| Campo | Tipo | Restricciones | Descripción |
|-------|------|---------------|-------------|
| id_campo | PK, Varchar(50) | NOT NULL, UNIQUE | Identificador único |
| campo_2 | Varchar(100) | NOT NULL | Descripción del campo |
| campo_3 | Enum | 'VALOR1', 'VALOR2' | Estados posibles |
| fecha_creacion | Datetime | DEFAULT NOW() | Timestamp de creación |

**Índices:**
- PRIMARY KEY: `id_campo`
- INDEX: `idx_campo_2` en `campo_2`

**Relaciones:**
- FK: `id_relacionado` → `OTRA_TABLA(id)`
```

#### B. Clasificar Tablas

Organiza las tablas en categorías:

1. **Tablas Maestras/Catálogos**: Datos de referencia relativamente estáticos
   - Empleados, productos, actividades, ubicaciones

2. **Tablas Transaccionales**: Registros de operaciones del negocio
   - Órdenes, movimientos, registros de tiempo, transacciones

3. **Tablas de Auditoría**: Trazabilidad y logs
   - Historial de cambios, logs de acceso, auditoría

4. **Tablas de Configuración**: Parámetros del sistema
   - Configuraciones, permisos, roles

#### C. Documentar Relaciones

```markdown
### Diagrama de Relaciones

\`\`\`mermaid
erDiagram
    TABLA_PADRE ||--o{ TABLA_HIJA : "contiene"
    TABLA_HIJA }o--|| CATALOGO : "referencia"
    
    TABLA_PADRE {
        int id_padre PK
        string nombre
    }
    
    TABLA_HIJA {
        int id_hija PK
        int id_padre FK
        int id_catalogo FK
    }
\`\`\`
```

### 5. Identificar Reglas de Negocio

```markdown
## Reglas de Negocio

### RN-001: Validación de Estado
- No permitir registros en lotes con estado CERRADO
- Validar antes de INSERT en tabla transaccional

### RN-002: Cálculo Automático
- `horas_totales = hora_salida - hora_entrada`
- Trigger o cálculo en aplicación

### RN-003: Integridad Referencial
- No eliminar registros maestros con dependencias activas
- Usar ON DELETE RESTRICT
```

**Buscar en documentos:**
- Validaciones mencionadas
- Cálculos automáticos
- Restricciones de integridad
- Flujos condicionales

### 6. Generar Scripts SQL (Opcional)

Si el usuario lo solicita, genera scripts DDL:

```sql
-- Crear tabla maestra
CREATE TABLE NOMBRE_TABLA (
    id_campo VARCHAR(50) PRIMARY KEY,
    campo_2 VARCHAR(100) NOT NULL,
    campo_3 ENUM('VALOR1', 'VALOR2') DEFAULT 'VALOR1',
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_campo_2 (campo_2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Crear tabla transaccional con FK
CREATE TABLE TABLA_HIJA (
    id_hija BIGINT AUTO_INCREMENT PRIMARY KEY,
    id_padre VARCHAR(50) NOT NULL,
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_padre) REFERENCES TABLA_PADRE(id_padre)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Estructura del Documento Final

Genera un documento Markdown con esta estructura:

```markdown
# Especificación de Requisitos y Diseño de Base de Datos
## [Nombre del Proyecto]

**Fecha**: [Fecha actual]
**Versión**: 1.0
**Fuentes**: [Lista de documentos analizados]

---

## 1. Resumen Ejecutivo
[Breve descripción del sistema y alcance]

## 2. Requisitos Funcionales
[RF-001, RF-002, etc.]

## 3. Requisitos No Funcionales
[RNF-001, RNF-002, etc.]

## 4. Modelo de Base de Datos

### 4.1 Diagrama Entidad-Relación
[Diagrama Mermaid]

### 4.2 Tablas Maestras
[Especificación detallada]

### 4.3 Tablas Transaccionales
[Especificación detallada]

### 4.4 Tablas de Auditoría
[Especificación detallada]

## 5. Reglas de Negocio
[RN-001, RN-002, etc.]

## 6. Consideraciones de Implementación
[Índices, particionamiento, estrategias de backup]

## 7. Anexos
[Scripts SQL, diagramas adicionales]
```

## Mejores Prácticas

### Completitud
- Lee TODOS los documentos disponibles antes de empezar a extraer
- Busca información en diagramas, tablas y texto narrativo
- Cruza referencias entre múltiples documentos

### Precisión
- Usa los nombres exactos de tablas y campos del documento fuente
- Respeta los tipos de datos especificados
- Mantén la terminología original del negocio

### Claridad
- Usa tablas Markdown para campos de BD (mejor legibilidad)
- Incluye ejemplos de datos cuando sea posible
- Explica el propósito de cada tabla

### Trazabilidad
- Indica de qué documento proviene cada requisito
- Numera requisitos consecutivamente (RF-001, RF-002...)
- Mantén referencias cruzadas entre requisitos y tablas

### Validación
- Verifica que todas las FK tengan su tabla referenciada
- Confirma que los tipos de datos sean consistentes
- Revisa que no falten campos críticos mencionados en flujos

## Patrones Comunes a Buscar

### En Diagramas de Secuencia
- Cada `INSERT`, `UPDATE`, `SELECT` indica una tabla
- Los parámetros de API revelan campos de tabla
- Los flujos muestran relaciones entre entidades

### En Descripciones de Flujo
- "El sistema registra..." → Tabla transaccional
- "Catálogo de..." → Tabla maestra
- "Auditoría de..." → Tabla de log/auditoría

### En Requisitos de Negocio
- "Debe calcular..." → Campo calculado o regla de negocio
- "No permitir..." → Constraint o validación
- "Vincular con..." → Foreign Key

## Ejemplo Completo

Para ver un ejemplo completo de extracción, consulta [examples.md](examples.md).

## Notas Finales

- **Siempre pregunta** si el usuario quiere scripts SQL además del documento
- **Valida** con el usuario si falta alguna fuente de información
- **Sugiere mejoras** al diseño si detectas problemas (normalización, índices faltantes)
- **Genera diagramas** Mermaid para mejor visualización
