# Inventario y flujo de caja para pequeños negocios

Aplicación en **Streamlit** para llevar el inventario, registrar ventas y calcular automáticamente el flujo de caja del negocio, con autenticación de usuarios.

## Funcionalidades

### Autenticación
- Registro de usuarios (crear cuenta) con:
  - Usuario
  - Contraseña
- Inicio de sesión con validación de credenciales.
- Contraseñas almacenadas de forma segura con hash (`PBKDF2-HMAC-SHA256` + salt).
- Control de acceso:
  - Si no hay sesión, solo se muestra login/registro.
  - Si hay sesión, se habilita toda la app.
- Botón de **Cerrar sesión** en barra lateral.

### Inventario de productos
- Agregar, editar y eliminar productos.
- Campos por producto:
  - Nombre
  - Categoría
  - Stock
  - Costo (precio de compra)
  - Precio de venta

### Registro de ventas
- Registro de ventas seleccionando el producto.
- Ingreso de cantidad vendida.
- Selector de impuestos por venta: **¿Esta venta paga impuestos? (Sí/No)**.
- Al registrar una venta:
  - Se descuenta automáticamente del inventario.
  - Se calcula subtotal (`precio de venta × cantidad`).
  - Si aplica impuesto: IVA del 12%.
  - Se calcula total final (subtotal + IVA).
  - Se calcula utilidad antes de ISR, ISR (25%) y utilidad neta.

### Costos del negocio
- Registro mensual de:
  - Costos fijos (renta, salarios, etc.)
  - Costos variables
- Estos costos se incluyen en el cálculo del flujo de caja mensual.

### Flujo de caja y visualización
- Resumen diario y mensual con desglose de:
  - Ventas brutas
  - IVA cobrado
  - Ingresos netos sin IVA
  - Costo de productos vendidos
  - Utilidad antes de ISR
  - ISR (25%)
  - Utilidad neta final
- Visualización separada de ventas con IVA / ventas sin IVA.
- Exportación a Excel para Power BI con botón **Descargar Excel**.

### Exportación a Excel (Power BI)
- Archivo `.xlsx` con hojas:
  - `Inventario`
  - `Flujo_Caja`
  - `Resumen` (opcional de mejora, incluido)
- Estructura tabular limpia:
  - Sin celdas combinadas
  - Encabezados en primera fila
  - Una fila por registro
  - Formato “long” listo para modelado en Power BI
- Incluye columnas fiscales solicitadas:
  - `paga_impuestos`
  - `iva`
  - `subtotal`
  - `total_con_iva`
  - `utilidad_antes_isr`
  - `isr`
  - `utilidad_neta`

### Persistencia de datos
- La información se guarda localmente en `data/`:
  - `products.csv`
  - `sales.csv`
  - `monthly_costs.csv`
  - `users.db` (usuarios y credenciales hasheadas)

## Requisitos
- Python 3.10+

## Instalación y ejecución

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
