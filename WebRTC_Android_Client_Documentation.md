# WebRTC Screen Streaming - Android Client Documentation

## Overview

This documentation provides guidance for implementing an Android client that can connect to the LLM Control WebRTC screen streaming server. The server streams desktop screen content to Android devices using WebRTC technology.

## Server Architecture

The WebRTC system consists of:

1. **Signaling Server**: A FastAPI-based WebSocket server that handles WebRTC connection establishment
2. **Screen Capture Module**: Captures the desktop screen and creates video frames for streaming
3. **WebRTC Connection**: Handles peer-to-peer media streaming once a connection is established

## Connection Protocol

### 1. WebSocket Connection

The Android client must first establish a WebSocket connection to the server's `/ws` endpoint:

```
ws://SERVER_IP:PORT/ws
```

Example connection:
```java
private final String wsUrl = "ws://192.168.1.100:8080/ws";
```

### 2. Signaling Process

The client must implement the following WebRTC signaling protocol:

1. **Establish WebSocket Connection**
2. **Create and Send Offer**: Create an RTCPeerConnection and send an SDP offer
3. **Process Answer**: Handle the server's SDP answer 
4. **Exchange ICE Candidates**: Send and receive ICE candidates (optional - server handles ICE internally)
5. **Establish Media Connection**: Process incoming video track

### 3. Message Format

All WebSocket messages use JSON format with a `type` field indicating the message type:

#### Client-to-Server Messages:

**SDP Offer**:
```json
{
  "type": "offer",
  "sdp": "<offer_sdp_string>"
}
```

**ICE Candidate** (optional):
```json
{
  "type": "ice_candidate",
  "candidate": "<candidate_string>",
  "sdpMid": "<mid_value>",
  "sdpMLineIndex": <line_index>
}
```

**Ping** (keep-alive):
```json
{
  "type": "ping"
}
```

**Bye** (disconnection):
```json
{
  "type": "bye"
}
```

#### Server-to-Client Messages:

**SDP Answer**:
```json
{
  "type": "answer",
  "sdp": "<answer_sdp_string>"
}
```

**Pong** (response to ping):
```json
{
  "type": "pong"
}
```

## Android Implementation Guide

### Required Dependencies

Add to your app's `build.gradle`:

```gradle
dependencies {
    // WebRTC
    implementation 'org.webrtc:google-webrtc:1.0.32006'
    
    // WebSocket client
    implementation 'org.java-websocket:Java-WebSocket:1.5.3'
    
    // For JSON processing
    implementation 'org.json:json:20210307'
}
```

### Permissions

Add to your `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
```

### Implementation Steps

#### 1. WebSocket Connection Handler

Create a WebSocket client to handle signaling:

```java
public class SignalingClient extends WebSocketClient {
    private final SignalingClientListener listener;
    
    public interface SignalingClientListener {
        void onConnectionEstablished();
        void onOfferReceived(JSONObject data);
        void onAnswerReceived(JSONObject data);
        void onIceCandidateReceived(JSONObject data);
        void onConnectionClosed();
        void onError(Exception e);
    }
    
    public SignalingClient(URI serverUri, SignalingClientListener listener) {
        super(serverUri);
        this.listener = listener;
    }
    
    @Override
    public void onOpen(ServerHandshake handshakedata) {
        listener.onConnectionEstablished();
    }
    
    @Override
    public void onMessage(String message) {
        try {
            JSONObject data = new JSONObject(message);
            String type = data.getString("type");
            
            switch (type) {
                case "answer":
                    listener.onAnswerReceived(data);
                    break;
                case "pong":
                    // Handle keep-alive response
                    break;
                default:
                    Log.d("SignalingClient", "Unhandled message type: " + type);
                    break;
            }
        } catch (JSONException e) {
            listener.onError(e);
        }
    }
    
    @Override
    public void onClose(int code, String reason, boolean remote) {
        listener.onConnectionClosed();
    }
    
    @Override
    public void onError(Exception ex) {
        listener.onError(ex);
    }
    
    public void sendOffer(String sdpOffer) {
        try {
            JSONObject message = new JSONObject();
            message.put("type", "offer");
            message.put("sdp", sdpOffer);
            send(message.toString());
        } catch (JSONException e) {
            listener.onError(e);
        }
    }
    
    public void sendIceCandidate(IceCandidate candidate) {
        try {
            JSONObject message = new JSONObject();
            message.put("type", "ice_candidate");
            message.put("candidate", candidate.sdp);
            message.put("sdpMid", candidate.sdpMid);
            message.put("sdpMLineIndex", candidate.sdpMLineIndex);
            send(message.toString());
        } catch (JSONException e) {
            listener.onError(e);
        }
    }
    
    public void sendPing() {
        try {
            JSONObject message = new JSONObject();
            message.put("type", "ping");
            send(message.toString());
        } catch (JSONException e) {
            listener.onError(e);
        }
    }
    
    public void sendBye() {
        try {
            JSONObject message = new JSONObject();
            message.put("type", "bye");
            send(message.toString());
        } catch (JSONException e) {
            listener.onError(e);
        }
    }
}
```

#### 2. WebRTC Connection Manager

Create a class to manage the WebRTC connection:

```java
public class WebRTCClient implements SignalingClient.SignalingClientListener {
    private Context context;
    private PeerConnectionFactory peerConnectionFactory;
    private PeerConnection peerConnection;
    private SignalingClient signalingClient;
    private final List<IceServer> iceServers = new ArrayList<>();
    private SurfaceViewRenderer remoteRenderer;
    private VideoTrack remoteVideoTrack;
    
    // Listener interface for client events
    public interface WebRTCClientListener {
        void onConnectionEstablished();
        void onConnectionFailed();
        void onVideoTrackReceived();
    }
    
    private WebRTCClientListener listener;
    
    public WebRTCClient(Context context, SurfaceViewRenderer remoteRenderer, WebRTCClientListener listener) {
        this.context = context;
        this.remoteRenderer = remoteRenderer;
        this.listener = listener;
        
        // Initialize WebRTC components
        initWebRTC();
    }
    
    private void initWebRTC() {
        // Initialize PeerConnectionFactory
        PeerConnectionFactory.InitializationOptions initOptions =
                PeerConnectionFactory.InitializationOptions.builder(context)
                        .createInitializationOptions();
        PeerConnectionFactory.initialize(initOptions);
        
        PeerConnectionFactory.Options options = new PeerConnectionFactory.Options();
        peerConnectionFactory = PeerConnectionFactory.builder()
                .setOptions(options)
                .createPeerConnectionFactory();
        
        // Configure ICE servers (usually not needed as server handles ICE)
        iceServers.add(IceServer.builder("stun:stun.l.google.com:19302").createIceServer());
    }
    
    public void connect(String serverUrl) {
        try {
            URI uri = new URI(serverUrl);
            signalingClient = new SignalingClient(uri, this);
            signalingClient.connect();
        } catch (URISyntaxException e) {
            Log.e("WebRTCClient", "Invalid server URL", e);
            if (listener != null) {
                listener.onConnectionFailed();
            }
        }
    }
    
    private void createPeerConnection() {
        PeerConnection.RTCConfiguration rtcConfig = 
                new PeerConnection.RTCConfiguration(iceServers);
        
        // Creating PeerConnection
        peerConnection = peerConnectionFactory.createPeerConnection(rtcConfig, new PeerConnection.Observer() {
            @Override
            public void onSignalingChange(PeerConnection.SignalingState signalingState) {}
            
            @Override
            public void onIceConnectionChange(PeerConnection.IceConnectionState iceConnectionState) {
                if (iceConnectionState == PeerConnection.IceConnectionState.CONNECTED ||
                        iceConnectionState == PeerConnection.IceConnectionState.COMPLETED) {
                    if (listener != null) {
                        listener.onConnectionEstablished();
                    }
                } else if (iceConnectionState == PeerConnection.IceConnectionState.FAILED ||
                        iceConnectionState == PeerConnection.IceConnectionState.DISCONNECTED ||
                        iceConnectionState == PeerConnection.IceConnectionState.CLOSED) {
                    if (listener != null) {
                        listener.onConnectionFailed();
                    }
                }
            }
            
            @Override
            public void onIceConnectionReceivingChange(boolean b) {}
            
            @Override
            public void onIceGatheringChange(PeerConnection.IceGatheringState iceGatheringState) {}
            
            @Override
            public void onIceCandidate(IceCandidate iceCandidate) {
                // Send ICE candidate to server
                signalingClient.sendIceCandidate(iceCandidate);
            }
            
            @Override
            public void onIceCandidatesRemoved(IceCandidate[] iceCandidates) {}
            
            @Override
            public void onAddStream(MediaStream mediaStream) {
                // Add remote video track to renderer
                if (mediaStream.videoTracks.size() > 0) {
                    remoteVideoTrack = mediaStream.videoTracks.get(0);
                    remoteVideoTrack.addSink(remoteRenderer);
                    if (listener != null) {
                        listener.onVideoTrackReceived();
                    }
                }
            }
            
            @Override
            public void onRemoveStream(MediaStream mediaStream) {}
            
            @Override
            public void onDataChannel(DataChannel dataChannel) {}
            
            @Override
            public void onRenegotiationNeeded() {}
            
            @Override
            public void onAddTrack(RtpReceiver rtpReceiver, MediaStream[] mediaStreams) {}
        });
    }
    
    private void createOffer() {
        peerConnection.createOffer(new SdpObserver() {
            @Override
            public void onCreateSuccess(SessionDescription sessionDescription) {
                // Set local description
                peerConnection.setLocalDescription(new SdpObserver() {
                    @Override
                    public void onCreateSuccess(SessionDescription sessionDescription) {}
                    
                    @Override
                    public void onSetSuccess() {
                        // Send offer to server
                        signalingClient.sendOffer(sessionDescription.description);
                    }
                    
                    @Override
                    public void onCreateFailure(String s) {}
                    
                    @Override
                    public void onSetFailure(String s) {}
                }, sessionDescription);
            }
            
            @Override
            public void onSetSuccess() {}
            
            @Override
            public void onCreateFailure(String s) {}
            
            @Override
            public void onSetFailure(String s) {}
        }, new MediaConstraints());
    }
    
    // Signaling client callbacks
    @Override
    public void onConnectionEstablished() {
        // Create peer connection after WebSocket connection is established
        createPeerConnection();
        // Create and send offer
        createOffer();
        
        // Start ping-pong keepalive
        startKeepAlive();
    }
    
    private void startKeepAlive() {
        // Send ping every 10 seconds for keep-alive
        new Thread(() -> {
            while (signalingClient.isOpen()) {
                signalingClient.sendPing();
                try {
                    Thread.sleep(10000);
                } catch (InterruptedException e) {
                    break;
                }
            }
        }).start();
    }
    
    @Override
    public void onOfferReceived(JSONObject data) {
        // Not expected from server
    }
    
    @Override
    public void onAnswerReceived(JSONObject data) {
        try {
            String sdp = data.getString("sdp");
            SessionDescription sessionDescription = new SessionDescription(
                    SessionDescription.Type.ANSWER, sdp);
            
            peerConnection.setRemoteDescription(new SdpObserver() {
                @Override
                public void onCreateSuccess(SessionDescription sessionDescription) {}
                
                @Override
                public void onSetSuccess() {
                    Log.d("WebRTCClient", "Remote description set successfully");
                }
                
                @Override
                public void onCreateFailure(String s) {}
                
                @Override
                public void onSetFailure(String s) {
                    Log.e("WebRTCClient", "Failed to set remote description: " + s);
                }
            }, sessionDescription);
        } catch (JSONException e) {
            Log.e("WebRTCClient", "Error parsing answer", e);
        }
    }
    
    @Override
    public void onIceCandidateReceived(JSONObject data) {
        // Not expected - server handles ICE internally
    }
    
    @Override
    public void onConnectionClosed() {
        disconnect();
    }
    
    @Override
    public void onError(Exception e) {
        Log.e("WebRTCClient", "Signaling error", e);
    }
    
    public void disconnect() {
        // Send bye message
        if (signalingClient != null && signalingClient.isOpen()) {
            signalingClient.sendBye();
            signalingClient.close();
        }
        
        // Release WebRTC resources
        if (remoteVideoTrack != null) {
            remoteVideoTrack.removeSink(remoteRenderer);
            remoteVideoTrack = null;
        }
        
        if (peerConnection != null) {
            peerConnection.close();
            peerConnection = null;
        }
    }
}
```

#### 3. Activity Implementation

Create an Activity to display the stream:

```java
public class StreamViewActivity extends AppCompatActivity {
    private SurfaceViewRenderer remoteRenderer;
    private WebRTCClient webRTCClient;
    private final String serverUrl = "ws://SERVER_IP:PORT/ws"; // Replace with actual server address
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_stream_view);
        
        // Initialize UI components
        remoteRenderer = findViewById(R.id.remote_renderer);
        
        // Initialize the renderer
        initializeRenderer();
        
        // Create WebRTC client
        webRTCClient = new WebRTCClient(this, remoteRenderer, new WebRTCClient.WebRTCClientListener() {
            @Override
            public void onConnectionEstablished() {
                runOnUiThread(() -> Toast.makeText(StreamViewActivity.this, 
                        "Connection established", Toast.LENGTH_SHORT).show());
            }
            
            @Override
            public void onConnectionFailed() {
                runOnUiThread(() -> Toast.makeText(StreamViewActivity.this, 
                        "Connection failed", Toast.LENGTH_SHORT).show());
            }
            
            @Override
            public void onVideoTrackReceived() {
                runOnUiThread(() -> {
                    // Video is now being received
                });
            }
        });
        
        // Connect to server
        webRTCClient.connect(serverUrl);
    }
    
    private void initializeRenderer() {
        // Initialize EglBase instance
        EglBase eglBase = EglBase.create();
        
        // Initialize SurfaceViewRenderer
        remoteRenderer.init(eglBase.getEglBaseContext(), null);
        remoteRenderer.setMirror(false);
        remoteRenderer.setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT);
    }
    
    @Override
    protected void onDestroy() {
        // Clean up WebRTC resources
        if (webRTCClient != null) {
            webRTCClient.disconnect();
        }
        
        if (remoteRenderer != null) {
            remoteRenderer.release();
        }
        
        super.onDestroy();
    }
}
```

#### 4. Layout XML

Create a layout for the stream view:

```xml
<?xml version="1.0" encoding="utf-8"?>
<RelativeLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="#000000">

    <org.webrtc.SurfaceViewRenderer
        android:id="@+id/remote_renderer"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:layout_centerInParent="true" />
    
    <ProgressBar
        android:id="@+id/loading_indicator"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_centerInParent="true"
        android:visibility="visible" />

</RelativeLayout>
```

## Connection Settings and Parameters

Server default settings your Android client should be able to handle:

- **Resolution**: 480x272 pixels (default, configurable on server)
- **Frame Rate**: 10 FPS (default, configurable on server)
- **Video Format**: BGRA converted to standard H.264/VP8 via WebRTC
- **Transport**: UDP with fallback to TCP via WebRTC's ICE mechanisms

## Error Handling

Implement proper error handling for these common situations:

1. **Connection Failures**: Retry connection with exponential backoff
2. **WebSocket Disconnection**: Attempt reconnection with same strategy
3. **ICE Connection Failures**: Display appropriate error and retry
4. **Media Stream Issues**: Provide feedback when video freezes or has quality issues

## Performance Considerations

1. **Resource Management**: Release WebRTC resources properly in onPause/onDestroy
2. **Battery Usage**: Consider adding options to reduce quality when on battery
3. **Network Conditions**: The server may reduce quality under poor network conditions
4. **Screen Orientation**: Handle orientation changes properly without disconnecting

## Testing

Test your implementation with various network conditions:

1. Strong WiFi connection
2. Cellular data (4G/5G)
3. Poor network conditions
4. Network switching (WiFi to cellular)

## Security Considerations

1. The basic implementation doesn't include authentication
2. Consider adding authentication to the WebSocket connection
3. Use WSS (WebSocket Secure) instead of WS in production

## Advanced Features

Consider implementing these additional features:

1. Quality selection (request different resolutions)
2. Connection statistics display
3. Screenshot capability
4. Touch feedback to server

## Troubleshooting

Common issues and solutions:

1. **Black Screen**: Check that the video track is being received and properly attached to the renderer
2. **Connection Failure**: Verify server URL and network connectivity
3. **Stuttering Video**: May indicate network congestion or device performance issues
4. **High Latency**: Check network conditions and server load