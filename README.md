# cs_admission — Centro Sanitario: Admisión

**Versión:** 1.0.0 | **Licencia:** LGPL-3 | **Autor:** Equilibrium Dev Team

Asistente guiado de admisión de residentes para Equilibrium.

## Descripción

Módulo Odoo 19 que implementa un asistente paso a paso para el proceso de admisión de nuevos residentes en centros de salud mental y residencias terapéuticas. Gestiona toda la documentación, evaluaciones iniciales y configuración del expediente del residente desde el primer contacto hasta su ingreso.

## Funcionalidades

- Proceso de admisión guiado con pasos definidos
- Secuencia automática de expedientes de admisión
- Gestión documental del proceso de ingreso
- Integración con historial médico y psicológico inicial
- Conexión con monedero personal del residente
- Seguimiento de formularios de admisión

## Dependencias

```
cs_resident, cs_medical_care, cs_psychology,
cs_purse_pocket, cs_patient_followup_forms
```

## Instalación

1. Instalar primero los módulos dependientes
2. Copiar en directorio `addons` de Odoo
3. Actualizar lista de aplicaciones
4. Buscar "Admisión" e instalar

## Proyecto

Parte del ecosistema **Equilibrium** — software de gestión para centros de salud mental.
