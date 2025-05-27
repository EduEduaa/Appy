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
    let productoSeleccionado = null;

    function mostrarAlertaSSE(mensaje) {
        const alerta = document.createElement('div');
        alerta.classList.add('alert', 'alert-warning', 'alert-dismissible', 'fade', 'show', 'mt-2');
        alerta.textContent = mensaje;
        const cerrarButton = document.createElement('button');
        cerrarButton.type = 'button';
        cerrarButton.classList.add('close');
        cerrarButton.setAttribute('data-dismiss', 'alert');
        cerrarButton.setAttribute('aria-label', 'Cerrar');
        cerrarButton.innerHTML = '<span aria-hidden="true">&times;</span>';
        alerta.appendChild(cerrarButton);
        alertasDiv.appendChild(alerta);

        setTimeout(() => {
            alerta.remove();
        }, 5000);
    }

    if (typeof EventSource !== 'undefined') {
        eventSource = new EventSource('/stream');

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (data && data.mensaje) {
                    mostrarAlertaSSE(data.mensaje);
                }
            } catch (error) {
                console.error('Error al procesar evento SSE:', error, event.data);
            }
        };

        eventSource.addEventListener('ping', function(event) {
            console.log('Ping recibido del servidor.');
        });

        eventSource.onerror = function(error) {
            console.error('Error en la conexión SSE:', error);
            mostrarAlertaSSE('Error en la conexión de alertas en tiempo real.');
        };
    } else {
        mostrarAlertaSSE('Tu navegador no soporta Server-Sent Events.');
    }

    buscadorForm.addEventListener('submit', function(event) {
        event.preventDefault();

        const nombreProducto = document.getElementById('nombre_producto').value;
        resultadosDiv.innerHTML = `<p>Buscando información para el producto: <strong>${nombreProducto}</strong>...</p>`;
        compraDetalleDiv.innerHTML = '';
        totalCompraDiv.innerHTML = '';

        fetch(`/buscar_producto?nombre=${encodeURIComponent(nombreProducto)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                fetch('https://mindicador.cl/api/dolar')
                    .then(response => {
                        if (!response.ok) {
                            console.error('Error al obtener el valor del dólar desde Mindicador:', response.status);
                            return null;
                        }
                        return response.json();
                    })
                    .then(dolarData => {
                        let dolarRate = null;
                        if (dolarData && dolarData.serie && dolarData.serie.length > 0 && dolarData.serie[0].valor) {
                            dolarRate = dolarData.serie[0].valor;
                        } else {
                            console.error('Formato de respuesta del dólar desde Mindicador inesperado:', dolarData);
                        }

                        resultadosDiv.innerHTML = '';
                        if (data.resultados && data.resultados.length > 0) {
                            const nombreProductoBuscado = nombreProducto;
                            resultadosDiv.innerHTML += `<h3>Resultados para: ${nombreProductoBuscado}</h3>`;

                            const productosAgrupados = {};
                            data.resultados.forEach(resultado => {
                                if (!productosAgrupados[resultado.producto_id]) {
                                    productosAgrupados[resultado.producto_id] = {
                                        nombre: resultado.producto,
                                        sucursales: []
                                    };
                                }
                                productosAgrupados[resultado.producto_id].sucursales.push(resultado);
                            });

                            for (const productoId in productosAgrupados) {
                                const productoInfo = productosAgrupados[productoId];
                                const sucursales = productoInfo.sucursales;

                                sucursales.sort((a, b) => {
                                    if (a.sucursal.toLowerCase() === 'casa matriz') return -1;
                                    if (b.sucursal.toLowerCase() === 'casa matriz') return 1;
                                    return 0;
                                });

                                const productoDiv = document.createElement('div');
                                productoDiv.classList.add('producto-resultados');
                                productoDiv.innerHTML = ``;

                                sucursales.forEach(resultado => {
                                    let precioUsd = null;
                                    if (dolarRate !== null) {
                                        precioUsd = resultado.precio / dolarRate;
                                    }
                                    const itemDiv = document.createElement('div');
                                    itemDiv.classList.add('resultado-item');
                                    itemDiv.innerHTML = `
                                        <p class="card-text">
                                            <strong>Sucursal:</strong> ${resultado.sucursal} <span class="text-info">${resultado.stock} unidades</span>,
                                            <strong>Precio:</strong> <span class="text-success">$${resultado.precio.toLocaleString('es-CL')} CLP</span>
                                           
                                        </p>
                                    `;

                                    const sucursalSelector = document.createElement('div');
                                    sucursalSelector.classList.add('sucursal-selector');
                                    const radioId = `sucursal-${resultado.sucursal.replace(/\s+/g, '-')}-${resultado.producto.replace(/\s+/g, '-')}`;
                                    sucursalSelector.innerHTML = `
                                        <label>
                                            ${resultado.stock > 0 ? `<input type="radio" name="producto-${resultado.producto.replace(/\s+/g, '-')}" value="${resultado.sucursal}" data-precio-clp="${resultado.precio}" data-precio-usd="${precioUsd !== null ? precioUsd : ''}" data-stock="${resultado.stock}" data-sucursal-id="${resultado.sucursal_id}" data-producto-id="${resultado.producto_id}" data-producto-nombre="${resultado.producto}" data-sucursal-nombre="${resultado.sucursal}" id="${radioId}"> Seleccionar` : '<span class="text-danger">Sin Stock</span>'}
                                        </label>
                                    `;
                                    itemDiv.appendChild(sucursalSelector);
                                    productoDiv.appendChild(itemDiv);
                                    if (resultado.stock === 0) {
                                        mostrarAlertaSSE(`¡Atención! El producto "${resultado.producto}" en la "${resultado.sucursal}" tiene bajo stock .`);
                                    }
                                });
                                resultadosDiv.appendChild(productoDiv);
                            }

                            resultadosDiv.addEventListener('change', function(event) {
                                if (event.target.type === 'radio' && event.target.name.startsWith('producto-')) {
                                    productoSeleccionado = {
                                        precio_clp: parseFloat(event.target.dataset.precioClp),
                                        precio_usd: event.target.dataset.precioUsd ? parseFloat(event.target.dataset.precioUsd) : null,
                                        stock: parseInt(event.target.dataset.stock, 10),
                                        sucursalId: event.target.dataset.sucursalId,
                                        productoId: event.target.dataset.productoId,
                                        productoNombre: event.target.dataset.productoNombre,
                                        sucursalNombre: event.target.dataset.sucursalNombre
                                    };
                                    mostrarDetalleCompra(productoSeleccionado, dolarRate);
                                }
                            });

                            function mostrarDetalleCompra(producto, rate) {
                                if (producto) {
                                    const precioUsdCompra = rate !== null ? producto.precio_clp / rate : null;
                                    compraDetalleDiv.innerHTML = `

                                            <label for="cantidad-compra" class="form-label">Cantidad:</label>
                                            <input type="number" class="form-control" id="cantidad-compra" name="cantidad" value="1" min="1" max="${producto.stock}">
                                            <button id="calcular-total-general" class="btn btn-outline-primary me-md-2" data-precio-clp="${producto.precio_clp}" data-precio-usd="${precioUsdCompra !== null ? precioUsdCompra : ''}" data-producto="${producto.productoNombre}" data-sucursal="${producto.sucursalNombre}" ${rate === null ? 'disabled' : ''}>Calcular Total</button>
                                            <button id="realizar-compra-general" class="btn btn-success" data-sucursal-id="${producto.sucursalId}" data-producto-id="${producto.productoId}" data-producto="${producto.productoNombre}" data-sucursal="${producto.sucursalNombre}" style="display: none;">Realizar Compra</button>

                                    `;

                                    const calcularTotalBtnGeneral = document.getElementById('calcular-total-general');
                                    const realizarCompraBtnGeneral = document.getElementById('realizar-compra-general');
                                    const cantidadInputGeneral = document.getElementById('cantidad-compra');

                                    calcularTotalBtnGeneral.addEventListener('click', function() {
                                        const cantidad = parseInt(cantidadInputGeneral.value, 10);
                                        const precioClpUnitario = parseFloat(this.dataset.precioClp);
                                        const precioUsdUnitario = parseFloat(this.dataset.precioUsd);
                                        if (!isNaN(precioClpUnitario) && !isNaN(cantidad) && cantidad > 0 && rate !== null) {
                                            const totalClp = precioClpUnitario * cantidad;
                                            const totalUsd = precioUsdUnitario * cantidad;
                                            totalCompraDiv.innerHTML = `<strong>Total a pagar por ${cantidad} ${producto.productoNombre} en ${producto.sucursalNombre}:</strong> $${totalClp.toLocaleString('es-CL')} CLP <br>
                                                                                 <strong>Total a pagar en Dolar:</strong> ${totalUsd.toFixed(2)} USD`;
                                            realizarCompraBtnGeneral.style.display = 'inline-block';
                                            realizarCompraBtnGeneral.dataset.sucursalId = producto.sucursalId;
                                            realizarCompraBtnGeneral.dataset.productoId = producto.productoId;
                                            realizarCompraBtnGeneral.dataset.cantidad = cantidad;
                                            realizarCompraBtnGeneral.dataset.precioClp = precioClpUnitario;
                                            realizarCompraBtnGeneral.dataset.precioUsd = precioUsdUnitario;
                                        } else {
                                            totalCompraDiv.innerHTML = '<p>Ingrese una cantidad válida y asegúrese de que el valor del dólar esté disponible.</p>';
                                            realizarCompraBtnGeneral.style.display = 'none';
                                        }
                                    });

                                    realizarCompraBtnGeneral.addEventListener('click', function() {
                                        const cantidadComprada = document.getElementById('cantidad-compra').value;
                                        const precioUnitarioClp = this.dataset.precioClp;
                                        const precioUnitarioUsd = this.dataset.precioUsd;
                                        const sucursalId = this.dataset.sucursalId;
                                        const productoId = this.dataset.productoId;
                                        const productoNombre = this.dataset.producto;
                                        const sucursalNombre = this.dataset.sucursal;

                                        window.location.href = `/pagar.html?sucursal_id=${sucursalId}&producto_id=${productoId}&cantidad=${cantidadComprada}&producto_nombre=${encodeURIComponent(productoNombre)}&sucursal_nombre=${encodeURIComponent(sucursalNombre)}&precio_clp=${precioUnitarioClp}&precio_usd=${precioUnitarioUsd}`;
                                    });
                                } else {
                                    compraDetalleDiv.innerHTML = '';
                                    totalCompraDiv.innerHTML = '';
                                }
                            }

                        } else {
                            resultadosDiv.innerHTML = `<p>No se encontraron resultados para el producto: <strong>${nombreProducto}</strong>.</p>`;
                            compraDetalleDiv.innerHTML = '';
                            totalCompraDiv.innerHTML = '';
                        }
                    })
                    .catch(error => {
                        console.error('Error al obtener el valor del dólar:', error);
                        resultadosDiv.innerHTML = `<p class="text-danger">Error al obtener el valor del dólar. Los precios se mostrarán solo en CLP.</p>`;
                        if (data.resultados && data.resultados.length > 0) {
                            resultadosDiv.innerHTML += '<h3>Resultados para: ${nombreProductoBuscado}</h3>';
                            data.resultados.forEach(resultado => {
                                const itemDiv = document.createElement('div');
                                itemDiv.classList.add('resultado-item');
                                itemDiv.innerHTML = `
                                    <p class="card-text">
                                        <strong>Sucursal:</strong> ${resultado.sucursal} <span class="text-info">${resultado.stock} unidades</span>,
                                        <strong>Precio:</strong> <span class="text-success">$${resultado.precio.toLocaleString('es-CL')} CLP</span>
                                    </p>
                                `;
                                const sucursalSelector = document.createElement('div');
                                sucursalSelector.classList.add('sucursal-selector');
                                const radioId = `sucursal-${resultado.sucursal.replace(/\s+/g, '-')}-${resultado.producto.replace(/\s+/g, '-')}`;
                                sucursalSelector.innerHTML = `
                                    <label>
                                        ${resultado.stock > 0 ? `<input type="radio" name="producto-${resultado.producto.replace(/\s+/g, '-')}" value="${resultado.sucursal}" data-precio-clp="${resultado.precio}" data-stock="${resultado.stock}" data-sucursal-id="${resultado.sucursal_id}" data-producto-id="${resultado.producto_id}" data-producto-nombre="${resultado.producto}" data-sucursal-nombre="${resultado.sucursal}" id="${radioId}"> Seleccionar` : '<span class="text-danger">Sin Stock</span>'}
                                    </label>
                                `;
                                itemDiv.appendChild(sucursalSelector);
                                resultadosDiv.appendChild(itemDiv);
                                if (resultado.stock === 0) {
                                    mostrarAlertaSSE(`¡Atención! El producto "${resultado.producto}" en la sucursal "${resultado.sucursal}" tiene stock 0.`);
                                }
                            });
                        }
                        compraDetalleDiv.innerHTML = '';
                        totalCompraDiv.innerHTML = '';
                    });
            })
            .catch(error => {
                console.error('Error al buscar el producto:', error);
                resultadosDiv.innerHTML = `<p>Ocurrió un error al buscar el producto: <strong>${nombreProducto}</strong>.</p>`;
                compraDetalleDiv.innerHTML = '';
                totalCompraDiv.innerHTML = '';
            });
    });
});