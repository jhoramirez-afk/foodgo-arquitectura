package cl.duoc.jv0101.foodgo.lambda;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Map;

final class NotificacionesClient {
    private final URI base;
    private final HttpClient http;
    private final ObjectMapper mapper;
    private final Clock clock;

    NotificacionesClient(String baseUrl, HttpClient http, ObjectMapper mapper, Clock clock) {
        if (baseUrl == null || baseUrl.isBlank()) {
            throw new IllegalArgumentException("Definir NOTIFICACIONES_BASE_URL");
        }
        base = URI.create(baseUrl.replaceAll("/+$", ""));
        if (!("http".equals(base.getScheme()) || "https".equals(base.getScheme()))
                || base.getHost() == null || base.getUserInfo() != null
                || base.getQuery() != null || base.getFragment() != null) {
            throw new IllegalArgumentException("NOTIFICACIONES_BASE_URL debe ser una URL HTTP valida");
        }
        this.http = http;
        this.mapper = mapper;
        this.clock = clock;
    }

    void registrar(EventoNotificacion evento) throws IOException, InterruptedException {
        String body = mapper.writeValueAsString(Map.of(
                "eventoId", evento.eventoId(),
                "resultado", "ENVIADO",
                "fechaHora", LocalDateTime.now(clock).minusSeconds(1).withNano(0).toString(),
                "detalle", "Simulación académica: aviso del pedido procesado desde SQS por Lambda."));
        HttpRequest request = HttpRequest.newBuilder(
                    URI.create(base + "/api/notificaciones/" + evento.notificacionId() + "/intentos"))
                .timeout(Duration.ofSeconds(5))
                .header("Content-Type", "application/json; charset=UTF-8")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
        HttpResponse<String> response = http.send(request,
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() != 200 && response.statusCode() != 201) {
            throw new IOException("Notificaciones rechazo el intento: HTTP " + response.statusCode());
        }
        JsonNode result = mapper.readTree(response.body());
        if (result == null || !result.path("id").isIntegralNumber() || result.path("id").longValue() <= 0
                || !evento.eventoId().equals(result.path("eventoId").asText())
                || !"ENVIADO".equals(result.path("resultado").asText())) {
            throw new IOException("Notificaciones no confirmo la persistencia del evento");
        }
    }
}
