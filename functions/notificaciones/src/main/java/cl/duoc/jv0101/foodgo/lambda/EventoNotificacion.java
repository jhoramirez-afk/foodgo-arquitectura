package cl.duoc.jv0101.foodgo.lambda;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.UUID;

public record EventoNotificacion(String eventoId, long notificacionId) {
    static EventoNotificacion leer(String body, ObjectMapper mapper) throws IOException {
        if (body == null || body.length() > 4096) {
            throw new IllegalArgumentException("El evento debe contener un cuerpo de hasta 4096 caracteres");
        }
        JsonNode data = mapper.readTree(body);
        if (data == null || !data.isObject()
                || !data.path("version").isIntegralNumber() || !data.path("version").canConvertToInt()
                || data.path("version").intValue() != 1
                || !"NOTIFICACION_SOLICITADA".equals(data.path("tipo").asText())
                || !data.path("eventoId").isTextual()
                || !data.path("notificacionId").isIntegralNumber()
                || !data.path("notificacionId").canConvertToLong()
                || data.path("notificacionId").longValue() <= 0) {
            throw new IllegalArgumentException("Evento de notificacion invalido");
        }
        String id = data.path("eventoId").textValue();
        if (!UUID.fromString(id).toString().equals(id)) {
            throw new IllegalArgumentException("eventoId debe ser un UUID canonico");
        }
        return new EventoNotificacion(id, data.path("notificacionId").longValue());
    }
}
