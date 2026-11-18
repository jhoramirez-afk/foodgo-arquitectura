package cl.duoc.jv0101.foodgo.lambda;

import static org.junit.jupiter.api.Assertions.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class NotificacionHandlerTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private static final String EVENT_ID = "25fc6053-62bb-459a-a1ea-07940f648d7a";

    private String body() {
        return "{\"version\":1,\"tipo\":\"NOTIFICACION_SOLICITADA\",\"eventoId\":\"" + EVENT_ID
                + "\",\"notificacionId\":7}";
    }

    private Map<String, Object> record(String id, String body) {
        return Map.of("messageId", id, "body", body);
    }

    @Test void confirmaSoloDespuesDeRegistrarElIntento() {
        List<EventoNotificacion> captured = new ArrayList<>();
        var handler = new NotificacionHandler(mapper, captured::add);
        var response = handler.handleRequest(Map.of("Records", List.of(record("mensaje-1", body()))), null);
        assertEquals(List.of(), response.get("batchItemFailures"));
        assertEquals(List.of(new EventoNotificacion(EVENT_ID, 7)), captured);
    }

    @Test void unRegistroInvalidoNoRepiteLosExitososDelLote() {
        List<EventoNotificacion> captured = new ArrayList<>();
        var handler = new NotificacionHandler(mapper, captured::add);
        var response = handler.handleRequest(Map.of("Records", List.of(
                record("correcto", body()), record("invalido", "{no es json}"))), null);
        assertEquals(List.of(Map.of("itemIdentifier", "invalido")), response.get("batchItemFailures"));
        assertEquals(1, captured.size());
    }

    @Test void conservaElMensajeParaReintentoSiElBackendFalla() {
        var handler = new NotificacionHandler(mapper, e -> { throw new IOException("sin conexion"); });
        var response = handler.handleRequest(Map.of("Records", List.of(record("reintentar", body()))), null);
        assertEquals(List.of(Map.of("itemIdentifier", "reintentar")), response.get("batchItemFailures"));
    }

    @Test void rechazaUnEventoDeOtraVersionSinLlamarAlBackend() {
        var handler = new NotificacionHandler(mapper, e -> fail("No debe producir un intento"));
        var response = handler.handleRequest(Map.of("Records", List.of(
                record("version", body().replace("\"version\":1", "\"version\":2")))), null);
        assertEquals(List.of(Map.of("itemIdentifier", "version")), response.get("batchItemFailures"));
    }

    @Test void rechazaIdNegativoYUuidInvalido() {
        var handler = new NotificacionHandler(mapper, e -> fail("No debe producir un intento"));
        var response = handler.handleRequest(Map.of("Records", List.of(
                record("negativo", body().replace("\"notificacionId\":7", "\"notificacionId\":-1")),
                record("uuid", body().replace(EVENT_ID, "sin-identificador")))), null);
        assertEquals(2, ((List<?>) response.get("batchItemFailures")).size());
    }

    @Test void unaVersionFueraDeRangoNoPuedeDesbordarseHastaUno() {
        var handler = new NotificacionHandler(mapper, e -> fail("No debe llamar al backend"));
        var response = handler.handleRequest(Map.of("Records", List.of(
                record("desbordamiento", body().replace("\"version\":1", "\"version\":4294967297")))), null);
        assertEquals(List.of(Map.of("itemIdentifier", "desbordamiento")), response.get("batchItemFailures"));
    }

    @Test void unLoteSinMessageIdNoPuedeSerConfirmadoPorAccidente() {
        var handler = new NotificacionHandler(mapper, e -> fail("No debe llamar al backend"));
        assertThrows(IllegalArgumentException.class, () -> handler.handleRequest(
                Map.of("Records", List.of(Map.of("body", body()))), null));
    }

    @Test void requiereFormatoSqsYAdmiteLoteVacio() {
        var handler = new NotificacionHandler(mapper, e -> fail("No debe llamar al backend"));
        assertThrows(IllegalArgumentException.class, () -> handler.handleRequest(Map.of(), null));
        assertEquals(List.of(), handler.handleRequest(Map.of("Records", List.of()), null).get("batchItemFailures"));
    }
}
