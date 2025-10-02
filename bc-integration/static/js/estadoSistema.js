let sistemaReservasActivo = false;
let autoUpdateIntervalId = null;

async function mostrarEstadoSistema({ schedulerName, schedulerArn, actualizarPistasDesdeServidor }) {

  
  const url = 'https://zk5p0giaje.execute-api.eu-north-1.amazonaws.com/programador';
  const payload = {
    operacion: 'LEER',
    schedule_name: schedulerName,
    schedule_arn: schedulerArn
  };

  const messageContainer = document.getElementById('messageContainer');

  try {
    const response = await fetch(url, {
      method: "POST",
      mode: 'cors',
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Error del servidor: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    sistemaReservasActivo = String(data.estado).trim().toUpperCase() === 'ENABLED';

    // Guardar estado en localStorage
    localStorage.setItem('estadoSistemaReservas', sistemaReservasActivo ? 'ENABLED' : 'DISABLED');

    console.log("🟢 sistemaReservasActivo actualizado a:", sistemaReservasActivo);

    await actualizarPistasDesdeServidor();

    if (autoUpdateIntervalId !== null) {
      clearInterval(autoUpdateIntervalId);
      autoUpdateIntervalId = null;
    }

    if (sistemaReservasActivo) {
      autoUpdateIntervalId = setInterval(actualizarPistasDesdeServidor, 120000);
    }

    const msg = document.createElement('div');
    msg.className = sistemaReservasActivo
      ? 'p-4 text-sm font-bold text-green-800 rounded-lg bg-green-100 flex items-center justify-between gap-4'
      : 'p-4 text-sm font-bold text-red-800 rounded-lg bg-red-100 flex items-center justify-between gap-4';

    const texto = document.createElement('span');
    texto.textContent = sistemaReservasActivo
      ? window.translations.conectado
      : window.translations.manual;
    msg.appendChild(texto);

    const boton = document.createElement('button');
    boton.textContent = sistemaReservasActivo
      ? window.translations.habilitarManual
      : window.translations.conectarSistema;

    boton.className = sistemaReservasActivo
      ? 'bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded text-sm'
      : 'bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded text-sm';

    boton.addEventListener("click", async () => {
      const operacion = sistemaReservasActivo ? 'DESHABILITAR' : 'HABILITAR';
      const texto = sistemaReservasActivo ? '🔴 Desconectando Sistema de Reservas...' : '🟢 Conectando Sistema de Reservas...';

      // Crear el mensaje parpadeante
      const parpadeoMsg = document.createElement("div");
      parpadeoMsg.textContent = texto;
      parpadeoMsg.className = "text-center font-bold text-blue-700 bg-blue-100 p-3 rounded animate-pulse";

      messageContainer.innerHTML = '';
      messageContainer.appendChild(parpadeoMsg);

      try {
        const accionPayload = {
          operacion: operacion,
          schedule_name: schedulerName,
          schedule_arn: schedulerArn
        };

        const accionResponse = await fetch(url, {
          method: "POST",
          mode: 'cors',
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(accionPayload)
        });

        if (!accionResponse.ok) {
          throw new Error("No se pudo cambiar el estado del sistema.");
        }

        if (autoUpdateIntervalId !== null) {
          clearInterval(autoUpdateIntervalId);
        }

        // Refrescar y persistir el estado
        await mostrarEstadoSistema({ schedulerName, schedulerArn, actualizarPistasDesdeServidor });

      } catch (err) {
        const errorMsg = document.createElement('div');
        errorMsg.textContent = "⚠️ Error al cambiar el estado del sistema: " + err.message;
        errorMsg.className = 'p-4 text-sm text-red-600 bg-red-100 rounded';
        messageContainer.innerHTML = '';
        messageContainer.appendChild(errorMsg);
      }
    });

    msg.appendChild(boton);
    messageContainer.innerHTML = '';
    messageContainer.appendChild(msg);

  } catch (error) {
    console.error('Error al comunicar con la API:', error);
    const errorMsg = document.createElement('div');
    errorMsg.textContent = 'Error al comunicar con el servidor.';
    errorMsg.className = 'p-4 text-sm text-red-600 bg-red-100 rounded';
    messageContainer.innerHTML = '';
    messageContainer.appendChild(errorMsg);
  }
}
