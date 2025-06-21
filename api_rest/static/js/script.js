document.addEventListener('DOMContentLoaded', function() {
    const buscadorForm = document.getElementById('buscador');
    const resultadosDiv = document.getElementById('resultados');
    const compraDetalleDiv = document.getElementById('compra-detalle');
    const totalCompraDiv = document.getElementById('total-compra');
    const alertasDiv = document.createElement('div');
    alertasDiv.id = 'alertas-sse';
    alertasDiv.classList.add('mt-3');
    // Inserta las alertas después del formulario del buscador
    buscadorForm.parentNode.insertBefore(alertasDiv, buscadorForm.nextSibling);

    let eventSource;
    let productoSeleccionado = null; // Almacena el producto y la sucursal seleccionada

    // --- Función para mostrar alertas SSE ---
    function mostrarAlertaSSE(mensaje) {
        const alerta = document.createElement('div');
        alerta.classList.add('alert', 'alert-warning', 'alert-dismissible', 'fade', 'show', 'mt-2');
        alerta.textContent = mensaje;
        const cerrarButton = document.createElement('button');
        cerrarButton.type = 'button';
        cerrarButton.classList.add('btn-close'); // Clase de Bootstrap 5 para cerrar
        cerrarButton.setAttribute('data-bs-dismiss', 'alert'); // Atributo de Bootstrap 5
        cerrarButton.setAttribute('aria-label', 'Cerrar');
        alerta.appendChild(cerrarButton);
        alertasDiv.appendChild(alerta);

        // Eliminar la alerta automáticamente después de 5 segundos
        setTimeout(() => {
            alerta.remove();
        }, 5000);
    }

    // --- Configuración de Server-Sent Events (SSE) ---
    // Verifica si el navegador soporta EventSource
    if (typeof EventSource !== 'undefined') {
        eventSource = new EventSource('/stream'); // Conexión al endpoint SSE

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                // Si el evento es un 'ping', solo registra en consola
                if (data && data.time) {
                    console.log('Ping recibido del servidor:', data.time);
                } else if (data && data.mensaje) {
                    // Si es un mensaje de alerta, muéstralo al usuario
                    mostrarAlertaSSE(data.mensaje);
                }
            } catch (error) {
                console.error('Error al procesar evento SSE:', error, event.data);
            }
        };

        // Escuchar eventos específicos (si tu backend los envía con un 'event' type)
        eventSource.addEventListener('ping', function(event) {
            console.log('Evento "ping" recibido del servidor.');
        });

        eventSource.onerror = function(error) {
            console.error('Error en la conexión SSE:', error);
            // Puedes decidir si mostrar esta alerta al usuario o solo en consola
            // mostrarAlertaSSE('Error en la conexión de alertas en tiempo real.');
        };
    } else {
        // Muestra una alerta si el navegador no soporta SSE
        mostrarAlertaSSE('Tu navegador no soporta Server-Sent Events. Las alertas en tiempo real no estarán disponibles.');
    }

    // --- Manejo del Formulario de Búsqueda ---
    buscadorForm.addEventListener('submit', function(event) {
        event.preventDefault(); // Evita el envío del formulario por defecto

        const nombreProducto = document.getElementById('nombre_producto').value.trim(); // .trim() para limpiar espacios en blanco
        if (!nombreProducto) {
            resultadosDiv.innerHTML = '<p class="text-danger">Por favor, ingresa el nombre de un producto para buscar.</p>';
            compraDetalleDiv.innerHTML = '';
            totalCompraDiv.innerHTML = '';
            return; // Sale de la función si el campo está vacío
        }

        resultadosDiv.innerHTML = `<p>Buscando información para el producto: <strong>${nombreProducto}</strong>...</p>`;
        compraDetalleDiv.innerHTML = ''; // Limpia el detalle de compra anterior
        totalCompraDiv.innerHTML = ''; // Limpia el total de compra anterior

        // Realiza la primera llamada para buscar productos
        fetch(`/buscar_producto?nombre=${encodeURIComponent(nombreProducto)}`)
            .then(response => {
                if (!response.ok) { // Si la respuesta HTTP no es exitosa
                    throw new Error(`Error HTTP! estado: ${response.status}`);
                }
                return response.json(); // Parsea la respuesta como JSON
            })
            .then(data => {
                // Una vez que se tienen los datos del producto, se realiza la segunda llamada para obtener el valor del dólar
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
                        // Extrae el valor del dólar si la estructura es la esperada
                        if (dolarData && dolarData.serie && dolarData.serie.length > 0 && dolarData.serie[0].valor) {
                            dolarRate = dolarData.serie[0].valor;
                        } else if (dolarData !== null) {
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
            resultadosDiv.innerHTML += `<h3>Resultados...</h3>`;

            // Agrupar productos por su ID para mostrar la imagen y el nombre una vez por producto
            const productosAgrupados = {};
            resultados.forEach(resultado => {
                if (!productosAgrupados[resultado.producto_id]) {
                    productosAgrupados[resultado.producto_id] = {
                        producto_nombre: resultado.producto_nombre,
                        imagen: resultado.imagen,
                        sucursales: [],
                        // Nuevo: Almacenar precios para encontrar el mínimo
                        precios_clp: [] 
                    };
                }
                productosAgrupados[resultado.producto_id].sucursales.push(resultado);
                productosAgrupados[resultado.producto_id].precios_clp.push(resultado.precio); // Guardar todos los precios
            });

            for (const productoId in productosAgrupados) {
                const productoInfo = productosAgrupados[productoId];
                const sucursales = productoInfo.sucursales;

                // Encontrar el precio más bajo entre todas las sucursales para este producto
                const precioMasBajoClp = Math.min(...productoInfo.precios_clp);
                let precioMasBajoUsd = null;
                if (dolarRate !== null) {
                    precioMasBajoUsd = precioMasBajoClp / dolarRate;
                }

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
                        <div class="row g-0 align-items-center"> <div class="col-md-3 d-flex justify-content-center"> <img src="${productoInfo.imagen || 'https://via.placeholder.com/150'}" class="img-fluid rounded-start" alt="Imagen de ${productoInfo.producto_nombre}" style="max-width: 120px; max-height: 120px; object-fit: contain;"> </div>
                            <div class="col-md-9"> <h5 class="card-title mb-1">${productoInfo.producto_nombre}</h5>
                                <p class="card-text">
                                    <small class="text-muted">Desde </small>
                                    <strong class="text-success fs-5">$${precioMasBajoClp.toLocaleString('es-CL')} CLP</strong>
                                    ${precioMasBajoUsd !== null ? `<br><small class="text-info">${precioMasBajoUsd.toFixed(2)} USD</small>` : ''}
                                </p>
                                <hr> <h6>Sucursales y Stock:</h6>
                                <div class="list-group list-group-flush">
                                    ${sucursales.map(resultado => {
                                        let precioUsd = null;
                                        if (dolarRate !== null) {
                                            precioUsd = resultado.precio / dolarRate;
                                        }
                                        const radioId = `sucursal-${resultado.sucursal_id}-${resultado.producto_id}`; //para el radio button
                                        const sinStock = resultado.stock_disponible === 0;

                                        // Muestra una alerta si el producto está sin stock en una sucursal específica
                                        if (sinStock) {
                                            mostrarAlertaSSE(`¡Atención! en la sucursal "${resultado.sucursal_nombre}" está sin stock`);
                                        }

                                        return `
                                            <div class="list-group-item d-flex justify-content-between align-items-center ${sinStock ? 'bg-light text-muted' : ''}">
                                                <div>
                                                    <strong>${resultado.sucursal_nombre}:</strong> 
                                                    <span class="text-info">${resultado.stock_disponible} unidades</span><br>
                                               
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
                                                            id="${radioId}" class="form-check-input"> 
                                                    <label for="${radioId}" class="form-check-label ms-2"> ${sinStock ? '<span class="text-danger">Sin Stock</span>' : 'Seleccionar'}</label>
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

            // --- Event listener delegado para la selección de producto/sucursal ---
            // Usa 'change' en resultadosDiv para capturar eventos de radio buttons
            resultadosDiv.addEventListener('change', function(event) {
                // Verifica si el elemento que disparó el evento es un radio button y pertenece a la selección de producto
                if (event.target.type === 'radio' && event.target.name.startsWith('producto-selection-')) {
                    const selectedRadio = event.target;
                    // Almacena los datos del producto y sucursal seleccionados
                    productoSeleccionado = {
                        precio_clp: parseFloat(selectedRadio.dataset.precioClp),
                        precio_usd: selectedRadio.dataset.precioUsd ? parseFloat(selectedRadio.dataset.precioUsd) : null,
                        stock: parseInt(selectedRadio.dataset.stock, 10),
                        sucursalId: parseInt(selectedRadio.dataset.sucursalId, 10),
                        productoId: parseInt(selectedRadio.dataset.productoId, 10),
                        productoNombre: selectedRadio.dataset.productoNombre,
                        sucursalNombre: selectedRadio.dataset.sucursalNombre
                    };
                    mostrarDetalleCompra(productoSeleccionado, dolarRate); // Muestra el detalle de la compra
                }
            });

        } else {
            // Si no se encuentran resultados
            resultadosDiv.innerHTML = `<p>No se encontraron resultados para el producto: <strong>${nombreProductoBuscado}</strong>. Intenta con otro nombre.</p>`;
        }
    }

    // --- Función para mostrar el detalle de la compra y botones de acción ---
    function mostrarDetalleCompra(producto, dolarRate) {
        if (producto) {
            const precioUsdCompra = dolarRate !== null ? producto.precio_clp / dolarRate : null;

            compraDetalleDiv.innerHTML = `
                <div class="mt-4 p-3 border rounded bg-light">
                     <p><strong>Sucursal Seleccionada:</strong> ${producto.sucursalNombre}</p>
                    <p><strong>Stock:</strong> ${producto.stock} unidades</p>
                    <p><strong>Precio Unitario:</strong> <span class="text-success">$${producto.precio_clp.toLocaleString('es-CL')} CLP</span></p>
                    <p><strong>Precio Dolar:</strong>${precioUsdCompra !== null ? `$<span class="text-info">${precioUsdCompra.toFixed(2)} USD</span>` : ''}</p>
                    
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
                // Validar la cantidad ingresada
                if (isNaN(cantidad) || cantidad <= 0 || cantidad > producto.stock) {
                    totalCompraDiv.innerHTML = '<p class="text-danger">Por favor, ingrese una cantidad válida y dentro del stock disponible.</p>';
                    realizarCompraBtnGeneral.style.display = 'none'; // Oculta el botón de compra si la cantidad no es válida
                    return;
                }

                const precioClpUnitario = parseFloat(this.dataset.precioClp);
                let totalClp = precioClpUnitario * cantidad;
                totalClp = Math.round(totalClp); // Redondear a número entero para CLP

                let totalUsdHtml = '';
                if (dolarRate !== null) { // Solo calcula y muestra USD si el tipo de cambio está disponible
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
                realizarCompraBtnGeneral.style.display = 'inline-block'; // Muestra el botón de realizar compra
                realizarCompraBtnGeneral.dataset.cantidad = cantidad; // Almacena la cantidad para la compra
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

                // Redirigir a la página de pago con los parámetros de la compra
                window.location.href = `/pagar.html?sucursal_id=${sucursalId}&producto_id=${productoId}&cantidad=${cantidadComprada}&producto_nombre=${encodeURIComponent(productoNombre)}&sucursal_nombre=${encodeURIComponent(sucursalNombre)}&precio_clp_unitario=${precioClpUnitario}&precio_usd_unitario=${precioUsdUnitario}`;
            });

        } else {
            // Limpiar si no hay producto seleccionado
            compraDetalleDiv.innerHTML = '';
            totalCompraDiv.innerHTML = '';
        }
    }
});