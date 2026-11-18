package cl.duoc.jv0101.foodgo.lambda;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.HttpClient;
import java.time.Clock;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class NotificacionHandler implements RequestHandler<Map<String, Object>, Map<String, Object>> {
    @FunctionalInterface
    interface RegistrarIntento {
        void registrar(EventoNotificacion evento) throws Exception;
    }

    private final ObjectMapper mapper;
    private final RegistrarIntento registrar;

    public NotificacionHandler() {
        mapper = new ObjectMapper();
        var client = new NotificacionesClient(System.getenv("NOTIFICACIONES_BASE_URL"),
                HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3))
                        .followRedirects(HttpClient.Redirect.NEVER).build(), mapper, Clock.systemUTC());
        registrar = client::registrar;
    }

    NotificacionHandler(ObjectMapper mapper, RegistrarIntento registrar) {
        this.mapper = mapper;
        this.registrar = registrar;
    }

    @Override
    public Map<String, Object> handleRequest(Map<String, Object> input, Context context) {
        if (input == null || !(input.get("Records") instanceof List<?> records)) {
            throw new IllegalArgumentException("La funcion recibe eventos SQS con Records");
        }
        for (Object raw : records) {
            if (!(raw instanceof Map<?, ?> record)
                    || !(record.get("messageId") instanceof String id) || id.isBlank()) {
                throw new IllegalArgumentException("Cada registro SQS requiere messageId");
            }
        }
        List<Map<String, String>> failures = new ArrayList<>();
        for (Object raw : records) {
            Map<?, ?> record = (Map<?, ?>) raw;
            String id = (String) record.get("messageId");
            try {
                if (!(record.get("body") instanceof String body)) {
                    throw new IllegalArgumentException("El cuerpo SQS debe ser un texto JSON");
                }
                EventoNotificacion evento = EventoNotificacion.leer(body, mapper);
                registrar.registrar(evento);
                if (context != null && context.getLogger() != null) {
                    context.getLogger().log("Procesado mensaje=" + id + " evento=" + evento.eventoId()
                            + " notificacion=" + evento.notificacionId() + "\n");
                }
            } catch (Exception error) {
                if (error instanceof InterruptedException) {
                    Thread.currentThread().interrupt();
                }
                failures.add(Map.of("itemIdentifier", id));
                if (context != null && context.getLogger() != null) {
                    context.getLogger().log("Reintentar mensaje=" + id
                            + " causa=" + error.getClass().getSimpleName() + "\n");
                }
            }
        }
        return Map.of("batchItemFailures", failures);
    }
}
