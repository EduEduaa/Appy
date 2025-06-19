document.addEventListener('DOMContentLoaded', function() {
    const buscadorForm = document.getElementById('buscador');
    const resultadosDiv = document.getElementById('resultados');
    const compraDetalleDiv = document.getElementById('compra-detalle');
    const totalCompraDiv = document.getElementById('total-compra');
    const alertasDiv = document.createElement('div');
    alertasDiv.id = 'alertas-sse';
    alertasDiv.classList.add('mt-3');
    buscadorForm.parentNode.insertBefore(alertasDiv, buscadorForm.nextSibling);

    let eventSource;
    let productoSeleccionado = null; // Almacena el producto y la sucursal seleccionada

    function mostrarAlertaSSE(mensaje) {
        const alerta = document.createElement('div');
        alerta.classList.add('alert', 'alert-warning', 'alert-dismissible', 'fade', 'show', 'mt-2');
        alerta.textContent = mensaje;
        const cerrarButton = document.createElement('button');
        cerrarButton.type = 'button';
        cerrarButton.classList.add('btn-close'); // Clase de Bootstrap 5 para cerrar
        cerrarButton.setAttribute('data-bs-dismiss', 'alert'); // Atributo de Bootstrap 5
        cerrarButton.setAttribute('aria-label', 'Cerrar');
        // cerrarButton.innerHTML = '<span aria-hidden="true">&times;</span>'; // No necesario con btn-close
        alerta.appendChild(cerrarButton);
        alertasDiv.appendChild(alerta);

        setTimeout(() => {
            alerta.remove();
        }, 5000);
    }

    // --- Configuración de Server-Sent Events (SSE) ---
    if (typeof EventSource !== 'undefined') {
        eventSource = new EventSource('/stream');

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                // Si el evento es un 'ping', solo registra en consola
                if (data && data.time) {
                    console.log('Ping recibido del servidor:', data.time);
                } else if (data && data.mensaje) {
                    // Si es un mensaje de alerta, muéstralo
                    mostrarAlertaSSE(data.mensaje);
                }
            } catch (error) {
                console.error('Error al procesar evento SSE:', error, event.data);
            }
        };

        // Escuchar eventos específicos (si tu backend los envía así)
        eventSource.addEventListener('ping', function(event) {
            console.log('Evento "ping" recibido del servidor.');
        });

        eventSource.onerror = function(error) {
            console.error('Error en la conexión SSE:', error);
            // Considera si quieres mostrar esta alerta al usuario, o solo en consola.
            // mostrarAlertaSSE('Error en la conexión de alertas en tiempo real.');
        };
    } else {
        mostrarAlertaSSE('Tu navegador no soporta Server-Sent Events. Las alertas en tiempo real no estarán disponibles.');
    }

    // --- Manejo del Formulario de Búsqueda ---
    buscadorForm.addEventListener('submit', function(event) {
        event.preventDefault();

        const nombreProducto = document.getElementById('nombre_producto').value.trim(); // .trim() para limpiar espacios
        if (!nombreProducto) {
            resultadosDiv.innerHTML = '<p class="text-danger">Por favor, ingresa el nombre de un producto.</p>';
            compraDetalleDiv.innerHTML = '';
            totalCompraDiv.innerHTML = '';
            return;
        }

        resultadosDiv.innerHTML = `<p>Buscando información para el producto: <strong>${nombreProducto}</strong>...</p>`;
        compraDetalleDiv.innerHTML = '';
        totalCompraDiv.innerHTML = '';

        // Realiza la primera llamada para buscar productos
        fetch(`/buscar_producto?nombre=${encodeURIComponent(nombreProducto)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Realiza la segunda llamada para obtener el valor del dólar
                return fetch('https://mindicador.cl/api/dolar')
                    .then(response => {
                        if (!response.ok) {
                            console.warn('Advertencia: Error al obtener el valor del dólar desde Mindicador. Los precios en USD no estarán disponibles.', response.status);
                            return null; // Devuelve null para indicar que no se pudo obtener el dólar
                        }
                        return response.json();
                    })
                    .then(dolarData => {
                        let dolarRate = null;
                        if (dolarData && dolarData.serie && dolarData.serie.length > 0 && dolarData.serie[0].valor) {
                            dolarRate = dolarData.serie[0].valor;
                        } else if (dolarData !== null) { // Solo si la primera parte de la cadena fetch no devolvió null
                            console.warn('Advertencia: Formato de respuesta del dólar desde Mindicador inesperado:', dolarData);
                        }
                        // Pasa los datos del producto y el tipo de cambio del dólar a la función que renderiza los resultados
                        renderizarResultados(data.resultados, nombreProducto, dolarRate);
                    })
                    .catch(error => {
                        console.error('Error al obtener el valor del dólar:', error);
                        // Si falla la obtención del dólar, aún así renderiza los resultados solo en CLP
                        renderizarResultados(data.resultados, nombreProducto, null);
                        mostrarAlertaSSE('No se pudo obtener el valor del dólar. Los precios se mostrarán solo en CLP.');
                    });
            })
            .catch(error => {
                console.error('Error al buscar el producto:', error);
                resultadosDiv.innerHTML = `<p class="text-danger">Ocurrió un error al buscar el producto: <strong>${nombreProducto}</strong>. Por favor, inténtalo de nuevo.</p>`;
                compraDetalleDiv.innerHTML = '';
                totalCompraDiv.innerHTML = '';
            });
    });

    // --- Función para renderizar los resultados de la búsqueda ---
    function renderizarResultados(resultados, nombreProductoBuscado, dolarRate) {
        resultadosDiv.innerHTML = ''; // Limpiar resultados anteriores

        if (resultados && resultados.length > 0) {
            resultadosDiv.innerHTML += `<h3>Resultados para: ${nombreProductoBuscado}</h3>`;

            // Agrupar productos por su ID para mostrar la imagen una vez por producto
            const productosAgrupados = {};
            resultados.forEach(resultado => {
                if (!productosAgrupados[resultado.producto_id]) {
                    productosAgrupados[resultado.producto_id] = {
                        producto_nombre: resultado.producto_nombre, // Renombrado a producto_nombre
                        imagen: resultado.imagen, // ¡Nueva propiedad!
                        sucursales: []
                    };
                }
                productosAgrupados[resultado.producto_id].sucursales.push(resultado);
            });

            for (const productoId in productosAgrupados) {
                const productoInfo = productosAgrupados[productoId];
                const sucursales = productoInfo.sucursales;

                // Ordenar las sucursales para que "Casa Matriz" aparezca primero
                sucursales.sort((a, b) => {
                    if (a.sucursal_nombre.toLowerCase() === 'casa matriz') return -1;
                    if (b.sucursal_nombre.toLowerCase() === 'casa matriz') return 1;
                    return 0;
                });

                const productoCard = document.createElement('div');
                productoCard.classList.add('card', 'mb-3');
                productoCard.innerHTML = `
                    <div class="card-body">
                        <div class="row g-0">
                            <div class="col-md-4">
                                <img src="${productoInfo.imagen || 'https://via.placeholder.com/150'}" class="img-fluid rounded-start" alt="Imagen de ${productoInfo.producto_nombre}" style="max-width: 150px; max-height: 150px; object-fit: contain;">
                            </div>
                            <div class="col-md-8">
                                <h5 class="card-title">${productoInfo.producto_nombre}</h5>
                                <div class="list-group list-group-flush">
                                    ${sucursales.map(resultado => {
                                        let precioUsd = null;
                                        if (dolarRate !== null) {
                                            precioUsd = resultado.precio / dolarRate; // Precio ahora viene del producto
                                        }
                                        const radioId = `sucursal-${resultado.sucursal_id}-${resultado.producto_id}`; // ID más único
                                        const sinStock = resultado.stock_disponible === 0;

                                        if (sinStock) {
                                            mostrarAlertaSSE(`¡Atención! El producto "${resultado.producto_nombre}" en la sucursal "${resultado.sucursal_nombre}" está sin stock.`);
                                        }

                                        return `
                                            <div class="list-group-item d-flex justify-content-between align-items-center">
                                                <div>
                                                    <strong>Sucursal:</strong> ${resultado.sucursal_nombre} 
                                                    <span class="text-info">(${resultado.stock_disponible} unidades)</span><br>
                                                    <strong>Precio:</strong> <span class="text-success">$${resultado.precio.toLocaleString('es-CL')} CLP</span>
                                                    ${precioUsd !== null ? `<br><span class="text-muted">~${precioUsd.toFixed(2)} USD</span>` : ''}
                                                </div>
                                                <div>
                                                    <input type="radio" name="producto-selection-${productoId}" 
                                                           value="${radioId}" 
                                                           data-precio-clp="${resultado.precio}" 
                                                           data-precio-usd="${precioUsd !== null ? precioUsd.toFixed(2) : ''}" 
                                                           data-stock="${resultado.stock_disponible}" 
                                                           data-sucursal-id="${resultado.sucursal_id}" 
                                                           data-producto-id="${resultado.producto_id}" 
                                                           data-producto-nombre="${resultado.producto_nombre}" 
                                                           data-sucursal-nombre="${resultado.sucursal_nombre}" 
                                                           ${sinStock ? 'disabled' : ''} 
                                                           id="${radioId}"> 
                                                    <label for="${radioId}"> ${sinStock ? '<span class="text-danger">Sin Stock</span>' : 'Seleccionar'}</label>
                                                </div>
                                            </div>
                                        `;
                                    }).join('')}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                resultadosDiv.appendChild(productoCard);
            }

            // --- Event listener para la selección de producto/sucursal ---
            resultadosDiv.addEventListener('change', function(event) {
                if (event.target.type === 'radio' && event.target.name.startsWith('producto-selection-')) {
                    const selectedRadio = event.target;
                    productoSeleccionado = {
                        precio_clp: parseFloat(selectedRadio.dataset.precioClp),
                        precio_usd: selectedRadio.dataset.precioUsd ? parseFloat(selectedRadio.dataset.precioUsd) : null,
                        stock: parseInt(selectedRadio.dataset.stock, 10),
                        sucursalId: parseInt(selectedRadio.dataset.sucursalId, 10),
                        productoId: parseInt(selectedRadio.dataset.productoId, 10),
                        productoNombre: selectedRadio.dataset.productoNombre,
                        sucursalNombre: selectedRadio.dataset.sucursalNombre
                    };
                    mostrarDetalleCompra(productoSeleccionado, dolarRate);
                }
            });

        } else {
            resultadosDiv.innerHTML = `<p>No se encontraron resultados para el producto: <strong>${nombreProductoBuscado}</strong>.</p>`;
        }
    }

    // --- Función para mostrar el detalle de la compra y botones ---
    function mostrarDetalleCompra(producto, dolarRate) {
        if (producto) {
            const precioUsdCompra = dolarRate !== null ? producto.precio_clp / dolarRate : null;

            compraDetalleDiv.innerHTML = `
                <div class="mt-4 p-3 border rounded bg-light">
                    <h4>Detalle de Compra</h4>
                    <p><strong>Producto:</strong> ${producto.productoNombre}</p>
                    <p><strong>Sucursal:</strong> ${producto.sucursalNombre}</p>
                    <p><strong>Stock Disponible:</strong> ${producto.stock} unidades</p>
                    <p><strong>Precio Unitario:</strong> $${producto.precio_clp.toLocaleString('es-CL')} CLP 
                    ${precioUsdCompra !== null ? `(~${precioUsdCompra.toFixed(2)} USD)` : ''}</p>
                    
                    <div class="mb-3">
                        <label for="cantidad-compra" class="form-label">Cantidad a comprar:</label>
                        <input type="number" class="form-control" id="cantidad-compra" name="cantidad" value="1" min="1" max="${producto.stock}">
                    </div>
                    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                        <button id="calcular-total-general" class="btn btn-outline-primary me-md-2" 
                                data-precio-clp="${producto.precio_clp}" 
                                data-precio-usd="${precioUsdCompra !== null ? precioUsdCompra.toFixed(2) : ''}" 
                                data-producto="${producto.productoNombre}" 
                                data-sucursal="${producto.sucursalNombre}" 
                                ${dolarRate === null ? 'disabled' : ''}>Calcular Total</button>
                        <button id="realizar-compra-general" class="btn btn-success" 
                                data-sucursal-id="${producto.sucursalId}" 
                                data-producto-id="${producto.productoId}" 
                                data-producto="${producto.productoNombre}" 
                                data-sucursal="${producto.sucursalNombre}" 
                                style="display: none;">Realizar Compra</button>
                    </div>
                </div>
            `;

            const calcularTotalBtnGeneral = document.getElementById('calcular-total-general');
            const realizarCompraBtnGeneral = document.getElementById('realizar-compra-general');
            const cantidadInputGeneral = document.getElementById('cantidad-compra');

            // --- Event Listener para Calcular Total ---
            calcularTotalBtnGeneral.addEventListener('click', function() {
                const cantidad = parseInt(cantidadInputGeneral.value, 10);
                // Validar cantidad
                if (isNaN(cantidad) || cantidad <= 0 || cantidad > producto.stock) {
                    totalCompraDiv.innerHTML = '<p class="text-danger">Por favor, ingrese una cantidad válida y dentro del stock disponible.</p>';
                    realizarCompraBtnGeneral.style.display = 'none';
                    return;
                }

                const precioClpUnitario = parseFloat(this.dataset.precioClp);
                let totalClp = precioClpUnitario * cantidad;
                totalClp = Math.round(totalClp); // Redondear a número entero para CLP

                let totalUsdHtml = '';
                if (dolarRate !== null) {
                    const precioUsdUnitario = parseFloat(this.dataset.precioUsd);
                    const totalUsd = precioUsdUnitario * cantidad;
                    totalUsdHtml = `<br><strong>Total en Dólar:</strong> ${totalUsd.toFixed(2)} USD`;
                }

                totalCompraDiv.innerHTML = `
                    <div class="mt-3 p-3 border rounded bg-info text-white">
                        <p><strong>Total a pagar por ${cantidad} ${producto.productoNombre} en ${producto.sucursalNombre}:</strong></p>
                        <p class="fs-4">$${totalClp.toLocaleString('es-CL')} CLP ${totalUsdHtml}</p>
                    </div>
                `;
                realizarCompraBtnGeneral.style.display = 'inline-block';
                realizarCompraBtnGeneral.dataset.cantidad = cantidad;
                realizarCompraBtnGeneral.dataset.precioClp = precioClpUnitario; // Almacena el precio unitario en CLP
                realizarCompraBtnGeneral.dataset.precioUsd = precioUsdCompra; // Almacena el precio unitario en USD
            });

            // --- Event Listener para Realizar Compra ---
            realizarCompraBtnGeneral.addEventListener('click', function() {
                const cantidadComprada = this.dataset.cantidad;
                const sucursalId = this.dataset.sucursalId;
                const productoId = this.dataset.productoId;
                const productoNombre = this.dataset.producto;
                const sucursalNombre = this.dataset.sucursal;
                const precioClpUnitario = this.dataset.precioClp;
                const precioUsdUnitario = this.dataset.precioUsd;

                // Redirigir a la página de pago con los parámetros correctos
                window.location.href = `/pagar.html?sucursal_id=${sucursalId}&producto_id=${productoId}&cantidad=${cantidadComprada}&producto_nombre=${encodeURIComponent(productoNombre)}&sucursal_nombre=${encodeURIComponent(sucursalNombre)}&precio_clp_unitario=${precioClpUnitario}&precio_usd_unitario=${precioUsdUnitario}`;
            });

        } else {
            compraDetalleDiv.innerHTML = '';
            totalCompraDiv.innerHTML = '';
        }
    }
});