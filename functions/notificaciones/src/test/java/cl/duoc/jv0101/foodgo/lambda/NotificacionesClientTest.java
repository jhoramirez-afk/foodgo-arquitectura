package cl.duoc.jv0101.foodgo.lambda;

import static org.junit.jupiter.api.Assertions.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

class NotificacionesClientTest {
    private HttpServer server;
    private final ObjectMapper mapper = new ObjectMapper();
    private final EventoNotificacion evento = new EventoNotificacion("25fc6053-62bb-459a-a1ea-07940f648d7a", 7);
    private final AtomicReference<String> requestBody = new AtomicReference<>();

    private NotificacionesClient backend(int status, String response) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/notificaciones/api/notificaciones/7/intentos", exchange -> {
            assertEquals("POST", exchange.getRequestMethod());
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] bytes = response.getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(status, bytes.length);
            exchange.getResponseBody().write(bytes);
            exchange.close();
        });
        server.start();
        return new NotificacionesClient("http://127.0.0.1:" + server.getAddress().getPort() + "/notificaciones/",
                HttpClient.newHttpClient(), mapper,
                Clock.fixed(Instant.parse("2026-11-17T12:00:00Z"), ZoneOffset.UTC));
    }

    private String confirmado() {
        return "{\"id\":12,\"eventoId\":\"" + evento.eventoId() + "\",\"resultado\":\"ENVIADO\"}";
    }

    @AfterEach void cerrar() {
        if (server != null) server.stop(0);
    }

    @Test void enviaUnIntentoAcademicoConIdentificadorEstable() throws Exception {
        backend(201, confirmado()).registrar(evento);
        var body = mapper.readTree(requestBody.get());
        assertEquals(evento.eventoId(), body.path("eventoId").asText());
        assertEquals("ENVIADO", body.path("resultado").asText());
        assertEquals("2026-11-17T11:59:59", body.path("fechaHora").asText());
        assertTrue(body.path("detalle").asText().startsWith("Simulación académica:"));
    }

    @Test void aceptaLaConfirmacionDeUnEventoYaProcesado() throws Exception {
        assertDoesNotThrow(() -> backend(200, confirmado()).registrar(evento));
    }

    @Test void unErrorHttpDebeConservarElMensajeEnSqs() throws Exception {
        var client = backend(503, "{\"message\":\"No disponible\"}");
        assertThrows(IOException.class, () -> client.registrar(evento));
    }

    @Test void noConfirmaUnEventoDistintoAunqueLaRespuestaSeaExitosa() throws Exception {
        var client = backend(201, confirmado().replace(evento.eventoId(), "otro-evento"));
        assertThrows(IOException.class, () -> client.registrar(evento));
    }

    @Test void requiereUnBackendHttpSinCredencialesEnLaUrl() {
        assertThrows(IllegalArgumentException.class, () -> new NotificacionesClient(
                "file:///tmp/backend", HttpClient.newHttpClient(), mapper, Clock.systemUTC()));
        assertThrows(IllegalArgumentException.class, () -> new NotificacionesClient(
                "https://usuario:clave@example.com", HttpClient.newHttpClient(), mapper, Clock.systemUTC()));
    }
}
