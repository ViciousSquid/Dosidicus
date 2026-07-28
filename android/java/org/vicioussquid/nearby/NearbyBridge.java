package org.vicioussquid.nearby;

import android.app.Activity;
import android.util.Base64;

import com.google.android.gms.nearby.Nearby;
import com.google.android.gms.nearby.connection.AdvertisingOptions;
import com.google.android.gms.nearby.connection.ConnectionInfo;
import com.google.android.gms.nearby.connection.ConnectionLifecycleCallback;
import com.google.android.gms.nearby.connection.ConnectionResolution;
import com.google.android.gms.nearby.connection.ConnectionsClient;
import com.google.android.gms.nearby.connection.DiscoveredEndpointInfo;
import com.google.android.gms.nearby.connection.DiscoveryOptions;
import com.google.android.gms.nearby.connection.EndpointDiscoveryCallback;
import com.google.android.gms.nearby.connection.Payload;
import com.google.android.gms.nearby.connection.PayloadCallback;
import com.google.android.gms.nearby.connection.PayloadTransferUpdate;
import com.google.android.gms.nearby.connection.Strategy;

/**
 * Thin wrapper over Google Nearby Connections. It owns the ConnectionsClient,
 * subclasses the abstract Nearby callbacks (which pyjnius can't), and forwards
 * every event to a {@link NearbyListener} the Python layer supplies.
 *
 * Strategy is P2P_POINT_TO_POINT (a single reliable link between two squids).
 * Snapshots are sent as BYTES payloads, delivered to Python as Base64.
 */
public class NearbyBridge {
    private final ConnectionsClient client;
    private final String serviceId;
    private final Strategy strategy = Strategy.P2P_POINT_TO_POINT;
    private NearbyListener listener;

    public NearbyBridge(Activity activity, String serviceId) {
        this.client = Nearby.getConnectionsClient(activity);
        this.serviceId = serviceId;
    }

    public void setListener(NearbyListener l) {
        this.listener = l;
    }

    private void status(String s) {
        if (listener != null) listener.onStatus(s);
    }

    public void startAdvertising(String name) {
        AdvertisingOptions options =
            new AdvertisingOptions.Builder().setStrategy(strategy).build();
        client.startAdvertising(name, serviceId, connectionLifecycleCallback, options)
            .addOnSuccessListener(unused -> status("advertising"))
            .addOnFailureListener(e -> status("advertise failed: " + e.getMessage()));
    }

    public void startDiscovery() {
        DiscoveryOptions options =
            new DiscoveryOptions.Builder().setStrategy(strategy).build();
        client.startDiscovery(serviceId, endpointDiscoveryCallback, options)
            .addOnSuccessListener(unused -> status("discovering"))
            .addOnFailureListener(e -> status("discover failed: " + e.getMessage()));
    }

    public void requestConnection(String name, String endpointId) {
        client.requestConnection(name, endpointId, connectionLifecycleCallback)
            .addOnFailureListener(e -> status("request failed: " + e.getMessage()));
    }

    public void acceptConnection(String endpointId) {
        client.acceptConnection(endpointId, payloadCallback);
    }

    public void rejectConnection(String endpointId) {
        client.rejectConnection(endpointId);
    }

    public void sendBytes(String endpointId, String base64Data) {
        byte[] data = Base64.decode(base64Data, Base64.NO_WRAP);
        client.sendPayload(endpointId, Payload.fromBytes(data));
    }

    public void disconnect(String endpointId) {
        client.disconnectFromEndpoint(endpointId);
    }

    public void stopAll() {
        try { client.stopAdvertising(); } catch (Exception ignored) {}
        try { client.stopDiscovery(); } catch (Exception ignored) {}
        try { client.stopAllEndpoints(); } catch (Exception ignored) {}
    }

    private final EndpointDiscoveryCallback endpointDiscoveryCallback =
        new EndpointDiscoveryCallback() {
            @Override
            public void onEndpointFound(String endpointId, DiscoveredEndpointInfo info) {
                if (listener != null)
                    listener.onEndpointFound(endpointId, info.getEndpointName());
            }
            @Override
            public void onEndpointLost(String endpointId) {
                if (listener != null) listener.onEndpointLost(endpointId);
            }
        };

    private final ConnectionLifecycleCallback connectionLifecycleCallback =
        new ConnectionLifecycleCallback() {
            @Override
            public void onConnectionInitiated(String endpointId, ConnectionInfo info) {
                if (listener != null)
                    listener.onConnectionInitiated(
                        endpointId, info.getEndpointName(), info.getAuthenticationDigits());
            }
            @Override
            public void onConnectionResult(String endpointId, ConnectionResolution resolution) {
                if (listener == null) return;
                if (resolution.getStatus().isSuccess()) listener.onConnected(endpointId);
                else listener.onRejected(endpointId);
            }
            @Override
            public void onDisconnected(String endpointId) {
                if (listener != null) listener.onDisconnected(endpointId);
            }
        };

    private final PayloadCallback payloadCallback = new PayloadCallback() {
        @Override
        public void onPayloadReceived(String endpointId, Payload payload) {
            if (listener != null && payload.getType() == Payload.Type.BYTES) {
                byte[] data = payload.asBytes();
                if (data != null)
                    listener.onBytesReceived(
                        endpointId, Base64.encodeToString(data, Base64.NO_WRAP));
            }
        }
        @Override
        public void onPayloadTransferUpdate(String endpointId, PayloadTransferUpdate update) {
        }
    };
}
