package org.vicioussquid.nearby;

/**
 * Plain callback interface the Python layer implements (via pyjnius). The
 * NearbyBridge subclasses Google Nearby's *abstract* callback classes — which
 * pyjnius cannot subclass — and translates every event into a call on this
 * interface. Payloads cross the boundary as Base64 strings to keep marshalling
 * simple and reliable.
 */
public interface NearbyListener {
    void onStatus(String message);
    void onEndpointFound(String endpointId, String name);
    void onEndpointLost(String endpointId);
    void onConnectionInitiated(String endpointId, String name, String authDigits);
    void onConnected(String endpointId);
    void onRejected(String endpointId);
    void onDisconnected(String endpointId);
    void onBytesReceived(String endpointId, String base64Data);
}
