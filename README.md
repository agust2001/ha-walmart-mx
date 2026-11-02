# Walmart México para Home Assistant

Integración para seguir el precio de productos de [walmart.com.mx](https://www.walmart.com.mx) desde Home Assistant: precio actual, ofertas, historial, mínimo y máximo, y un evento cada vez que cambia el precio para armar alertas.

> No informa disponibilidad/stock: Walmart la calcula según una sucursal que deduce por la IP (y para envío a domicilio), así que no coincide con la sucursal que elijas en el sitio.

> No es una integración oficial de Walmart. Walmart no tiene API pública: se lee la página del producto (los datos que la propia página trae embebidos). Si Walmart cambia su sitio puede dejar de funcionar hasta que se actualice la integración.

## Instalación

### HACS (recomendado)

1. HACS → menú ⋮ → **Repositorios personalizados**.
2. Repositorio: `https://github.com/agust2001/ha-walmart-mx`, tipo **Integración**.
3. Busca **Walmart México**, instálala y reinicia Home Assistant.

### Manual

Copia `custom_components/walmart_mx` a la carpeta `custom_components` de tu configuración y reinicia Home Assistant.

## Agregar un producto

**Ajustes → Dispositivos y servicios → Agregar integración → Walmart México**, y pega el link del producto o su ID (el número al final del link):

```
https://www.walmart.com.mx/ip/Licor-de-Hierbas-Fernet-Branca-750-ml/00800440001437
00800440001437
```

Cada producto se agrega por separado y queda como un dispositivo. Por defecto se consulta **una vez por hora**; se puede cambiar en **Configurar** (de 15 minutos a 24 horas).

## Entidades por producto

| Entidad | Qué es |
|---|---|
| `sensor.…_precio` | Precio actual (MXN). Guarda estadísticas: en el historial ves mínimo, máximo y promedio por día. |
| `sensor.…_precio_anterior` | Precio "antes" que muestra Walmart cuando hay rebaja (vacío si no hay). |
| `sensor.…_ahorro` | Cuánto ahorras con la rebaja actual (MXN). |
| `sensor.…_descuento` | Descuento actual en %. |
| `sensor.…_precio_minimo_historico` | El precio más bajo visto desde que agregaste el producto (atributo `date`). |
| `sensor.…_precio_maximo_historico` | El más alto visto. |
| `sensor.…_diferencia_con_el_minimo` | Cuánto está el precio actual por encima del mínimo histórico. |
| `sensor.…_ultimo_cambio_de_precio` | Diferencia del último cambio (negativo = bajó). Atributos: precio anterior, actual y %. |
| `sensor.…_fecha_del_ultimo_cambio` | Cuándo cambió el precio por última vez. |
| `sensor.…_historial_de_precios` | Cantidad de cambios registrados; atributo `history` con la lista `[{date, price}]` (últimos 100). |
| `sensor.…_link` | URL de la página del producto en walmart.com.mx (para tarjetas que la abran). |
| `sensor.…_calificacion` / `sensor.…_resenas` | Estrellas y cantidad de reseñas. |
| `binary_sensor.…_en_oferta` | Tiene rebaja / rollback. |
| `binary_sensor.…_en_precio_minimo` | El precio actual es el más bajo registrado (y el precio ya cambió alguna vez). |
| `image.…_foto` | Foto del producto. |
| `button.…_actualizar_ahora` | Consulta el precio en el momento. |
| Diagnóstico | Vendedor, límite por pedido y hora de la última consulta. |

El historial (mínimo, máximo y cambios) se guarda aparte y sobrevive a reinicios. Se borra si eliminas el producto.

## Evento `walmart_mx_price_changed`

Se dispara cada vez que cambia el precio de un producto, con estos datos:

```yaml
product_id: "00800440001437"
name: Licor de Hierbas Fernet Branca 750 ml
old_price: 389.0
new_price: 349.0
difference: -40.0
percent: -10.3
url: https://www.walmart.com.mx/ip/producto/00800440001437
lowest_price: 349.0
```

### Ejemplo: avisar cuando baja el precio

### Tarjeta que abre la página del producto

Con [button-card](https://github.com/custom-cards/button-card) (las plantillas `[[[ ]]]` leen el sensor `…_link`):

```yaml
type: custom:button-card
entity: sensor.licor_de_hierbas_fernet_branca_750_ml_precio
show_state: true
tap_action:
  action: url
  url_path: "[[[ return states['sensor.licor_de_hierbas_fernet_branca_750_ml_link'].state; ]]]"
```

```yaml
alias: Walmart - bajó un precio
triggers:
  - trigger: event
    event_type: walmart_mx_price_changed
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.difference < 0 }}"
actions:
  - action: notify.notify
    data:
      title: "🛒 Bajó de precio"
      message: >
        {{ trigger.event.data.name }}: ${{ trigger.event.data.old_price }} → ${{ trigger.event.data.new_price }}
        ({{ trigger.event.data.percent }}%)
      data:
        url: "{{ trigger.event.data.url }}"
```

### Ejemplo: avisar cuando llega a su mínimo histórico

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.licor_de_hierbas_fernet_branca_750_ml_en_precio_minimo
    to: "on"
```

### Gráfica del historial

Con la tarjeta de historial nativa basta con agregar `sensor.…_precio`. Con [apexcharts-card](https://github.com/RomRider/apexcharts-card) puedes graficar el atributo `history`:

```yaml
type: custom:apexcharts-card
header:
  title: Fernet Branca
graph_span: 90d
series:
  - entity: sensor.licor_de_hierbas_fernet_branca_750_ml_historial_de_precios
    name: Precio
    curve: stepline
    data_generator: |
      return entity.attributes.history.map(p => [new Date(p.date).getTime(), p.price]);
```

## Notas

- Cada producto hace una consulta por intervalo. Con muchos productos y un intervalo corto, Walmart puede empezar a frenar las consultas; en ese caso las entidades quedan como no disponibles hasta la siguiente consulta exitosa.
- La búsqueda de Walmart tiene captcha, por eso los productos se agregan por link o ID y no por nombre.

## Licencia

MIT
