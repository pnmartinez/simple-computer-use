# Android WebRTC Client Guide

This guide explains how to build a simple Android app that can connect to the WebRTC screen streaming server to receive and display the screen feed.

## Prerequisites

- Android Studio (latest stable version)
- Basic knowledge of Android development
- Android device running Android 10+ or emulator
- A running instance of the WebRTC screen streaming server

## Project Setup

1. Open Android Studio and create a new project:
   - Choose "Empty Activity" template
   - Set application name: "Screen Viewer"
   - Package name: `com.example.screenviewer`
   - Minimum SDK: API 29 (Android 10.0)
   - Language: Kotlin

2. Add WebRTC dependencies to your app's `build.gradle`:

```gradle
dependencies {
    // Existing dependencies...
    
    // WebRTC
    implementation 'org.webrtc:google-webrtc:1.0.32006'
    
    // OkHttp for WebSocket connection
    implementation 'com.squareup.okhttp3:okhttp:4.11.0'
    
    // Optional: Coroutine support
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.1'
    
    // Optional: ViewModel and LiveData
    implementation 'androidx.lifecycle:lifecycle-viewmodel-ktx:2.6.2'
    implementation 'androidx.lifecycle:lifecycle-livedata-ktx:2.6.2'
}
```

3. Add required permissions to `AndroidManifest.xml`:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.screenviewer">
    
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    
    <!-- Application definition... -->
</manifest>
```

## Layout Design

Create a simple layout for the main activity in `res/layout/activity_main.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    xmlns:tools="http://schemas.android.com/tools"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    tools:context=".MainActivity">

    <org.webrtc.SurfaceViewRenderer
        android:id="@+id/remote_renderer"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toTopOf="parent" />

    <EditText
        android:id="@+id/server_url"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_margin="16dp"
        android:hint="Server URL (ws://your-server-ip:8080/ws)"
        android:textSize="14sp"
        android:padding="8dp"
        android:background="#99FFFFFF"
        app:layout_constraintBottom_toTopOf="@id/connect_button"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent" />

    <Button
        android:id="@+id/connect_button"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_margin="16dp"
        android:text="Connect"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <TextView
        android:id="@+id/status_text"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_margin="16dp"
        android:background="#99000000"
        android:padding="8dp"
        android:text="Disconnected"
        android:textColor="#FFFFFF"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toTopOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>
```

## WebRTC Client Implementation

### 1. Create a WebRTC Client Class

Create a new Kotlin file `WebRTCClient.kt`:

```kotlin
package com.example.screenviewer

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.*
import org.json.JSONObject
import org.webrtc.*
import java.util.concurrent.ConcurrentHashMap
import java.io.IOException

class WebRTCClient(
    private val context: Context,
    private val listener: WebRTCClientListener
) {
    private val TAG = "WebRTCClient"
    
    interface WebRTCClientListener {
        fun onConnectionStateChanged(state: String)
        fun onRemoteStreamAdded(stream: MediaStream)
        fun onError(error: String)
    }
    
    // WebRTC components
    private var eglBase: EglBase? = null
    private var peerConnectionFactory: PeerConnectionFactory? = null
    private var peerConnection: PeerConnection? = null
    private var localMediaStream: MediaStream? = null
    private var webSocket: WebSocket? = null
    
    // ICE servers - we don't need STUN/TURN for local network as specified in PRD
    private val iceServers = listOf(
        PeerConnection.IceServer.builder("stun:stun.l.google.com:19302").createIceServer()
    )
    
    // Initialize WebRTC components
    fun initWebRTC() {
        eglBase = EglBase.create()
        
        val options = PeerConnectionFactory.InitializationOptions.builder(context)
            .setEnableInternalTracer(true)
            .createInitializationOptions()
        
        PeerConnectionFactory.initialize(options)
        
        val encoderFactory = DefaultVideoEncoderFactory(eglBase?.eglBaseContext, true, true)
        val decoderFactory = DefaultVideoDecoderFactory(eglBase?.eglBaseContext)
        
        val peerConnectionFactoryOptions = PeerConnectionFactory.Options()
        
        peerConnectionFactory = PeerConnectionFactory.builder()
            .setOptions(peerConnectionFactoryOptions)
            .setVideoEncoderFactory(encoderFactory)
            .setVideoDecoderFactory(decoderFactory)
            .createPeerConnectionFactory()
        
        Log.d(TAG, "WebRTC initialized")
    }
    
    // Connect to WebRTC signaling server
    fun connect(serverUrl: String) {
        if (webSocket != null) {
            disconnect()
        }
        
        listener.onConnectionStateChanged("Connecting...")
        
        // Create a WebSocket client
        val client = OkHttpClient()
        val request = Request.Builder().url(serverUrl).build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket onOpen")
                listener.onConnectionStateChanged("WebSocket Connected")
                
                // Create peer connection
                createPeerConnection()
                
                // Create and send offer
                createOffer()
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(TAG, "WebSocket onMessage: $text")
                
                try {
                    val json = JSONObject(text)
                    val type = json.optString("type")
                    
                    when (type) {
                        "answer" -> {
                            val sdp = json.getString("sdp")
                            val answer = SessionDescription(
                                SessionDescription.Type.ANSWER, sdp
                            )
                            
                            CoroutineScope(Dispatchers.Main).launch {
                                peerConnection?.setRemoteDescription(
                                    object : SdpObserver {
                                        override fun onSetFailure(p0: String?) {
                                            Log.e(TAG, "setRemoteDescription error: $p0")
                                            listener.onError("Failed to set remote description: $p0")
                                        }
                                        
                                        override fun onSetSuccess() {
                                            Log.d(TAG, "setRemoteDescription success")
                                            listener.onConnectionStateChanged("Connected to server")
                                        }
                                        
                                        override fun onCreateSuccess(p0: SessionDescription?) {
                                            // Not used for answer
                                        }
                                        
                                        override fun onCreateFailure(p0: String?) {
                                            // Not used for answer
                                        }
                                    }, answer
                                )
                            }
                        }
                        "ice_candidate" -> {
                            val candidate = json.getString("candidate")
                            val sdpMid = json.getString("sdpMid")
                            val sdpMLineIndex = json.getInt("sdpMLineIndex")
                            
                            val iceCandidate = IceCandidate(sdpMid, sdpMLineIndex, candidate)
                            
                            CoroutineScope(Dispatchers.Main).launch {
                                peerConnection?.addIceCandidate(iceCandidate)
                            }
                        }
                        "pong" -> {
                            // Server responded to ping
                            Log.d(TAG, "Received pong from server")
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing WebSocket message", e)
                    listener.onError("Error parsing WebSocket message: ${e.message}")
                }
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket onFailure", t)
                listener.onError("WebSocket failure: ${t.message}")
                listener.onConnectionStateChanged("Connection failed")
            }
            
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket onClosed: $code - $reason")
                listener.onConnectionStateChanged("Disconnected")
            }
        })
    }
    
    private fun createPeerConnection() {
        if (peerConnectionFactory == null) {
            Log.e(TAG, "PeerConnectionFactory is null")
            listener.onError("PeerConnectionFactory is null")
            return
        }
        
        val rtcConfig = PeerConnection.RTCConfiguration(iceServers)
        rtcConfig.sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
        rtcConfig.continualGatheringPolicy = PeerConnection.ContinualGatheringPolicy.GATHER_CONTINUALLY
        
        peerConnection = peerConnectionFactory?.createPeerConnection(
            rtcConfig,
            object : PeerConnection.Observer {
                override fun onConnectionChange(newState: PeerConnection.PeerConnectionState?) {
                    Log.d(TAG, "onConnectionChange: $newState")
                    
                    when (newState) {
                        PeerConnection.PeerConnectionState.CONNECTED -> {
                            listener.onConnectionStateChanged("Connected")
                        }
                        PeerConnection.PeerConnectionState.DISCONNECTED -> {
                            listener.onConnectionStateChanged("Disconnected")
                        }
                        PeerConnection.PeerConnectionState.FAILED -> {
                            listener.onConnectionStateChanged("Connection failed")
                        }
                        else -> {
                            listener.onConnectionStateChanged(newState.toString())
                        }
                    }
                }
                
                override fun onAddStream(stream: MediaStream?) {
                    Log.d(TAG, "onAddStream: ${stream?.videoTracks?.size} video tracks")
                    
                    if (stream != null) {
                        CoroutineScope(Dispatchers.Main).launch {
                            listener.onRemoteStreamAdded(stream)
                        }
                    }
                }
                
                override fun onIceCandidate(candidate: IceCandidate?) {
                    Log.d(TAG, "onIceCandidate: ${candidate?.sdp}")
                    
                    if (candidate != null) {
                        // Convert to json and send to server
                        val json = JSONObject().apply {
                            put("type", "ice_candidate")
                            put("candidate", candidate.sdp)
                            put("sdpMid", candidate.sdpMid)
                            put("sdpMLineIndex", candidate.sdpMLineIndex)
                        }
                        
                        webSocket?.send(json.toString())
                    }
                }
                
                // Other required overrides
                override fun onSignalingChange(p0: PeerConnection.SignalingState?) {}
                override fun onIceConnectionChange(p0: PeerConnection.IceConnectionState?) {}
                override fun onIceConnectionReceivingChange(p0: Boolean) {}
                override fun onIceGatheringChange(p0: PeerConnection.IceGatheringState?) {}
                override fun onAddTrack(p0: RtpReceiver?, p1: Array<out MediaStream>?) {}
                override fun onRemoveStream(p0: MediaStream?) {}
                override fun onDataChannel(p0: DataChannel?) {}
                override fun onRenegotiationNeeded() {}
                override fun onRemoveIceCandidate(p0: IceCandidate?) {}
                override fun onTrack(p0: RtpTransceiver?) {}
            }
        )
    }
    
    private fun createOffer() {
        peerConnection?.createOffer(object : SdpObserver {
            override fun onCreateSuccess(sessionDescription: SessionDescription?) {
                Log.d(TAG, "createOffer: onCreateSuccess")
                
                if (sessionDescription != null) {
                    peerConnection?.setLocalDescription(object : SdpObserver {
                        override fun onSetSuccess() {
                            Log.d(TAG, "setLocalDescription: onSetSuccess")
                            
                            // Send offer to server
                            val json = JSONObject().apply {
                                put("type", "offer")
                                put("sdp", sessionDescription.description)
                            }
                            
                            webSocket?.send(json.toString())
                        }
                        
                        override fun onSetFailure(p0: String?) {
                            Log.e(TAG, "setLocalDescription: onSetFailure: $p0")
                            listener.onError("Failed to set local description: $p0")
                        }
                        
                        override fun onCreateSuccess(p0: SessionDescription?) {}
                        override fun onCreateFailure(p0: String?) {}
                    }, sessionDescription)
                }
            }
            
            override fun onCreateFailure(p0: String?) {
                Log.e(TAG, "createOffer: onCreateFailure: $p0")
                listener.onError("Failed to create offer: $p0")
            }
            
            override fun onSetSuccess() {}
            override fun onSetFailure(p0: String?) {}
        }, MediaConstraints())
    }
    
    // Disconnect and clean up resources
    fun disconnect() {
        try {
            peerConnection?.close()
            peerConnection = null
            
            webSocket?.close(1000, "User disconnected")
            webSocket = null
            
            listener.onConnectionStateChanged("Disconnected")
        } catch (e: Exception) {
            Log.e(TAG, "Error during disconnect", e)
        }
    }
    
    // Release all resources
    fun release() {
        try {
            disconnect()
            
            peerConnectionFactory?.dispose()
            peerConnectionFactory = null
            
            eglBase?.release()
            eglBase = null
        } catch (e: Exception) {
            Log.e(TAG, "Error during release", e)
        }
    }
    
    // Get EGL context for rendering
    fun getEglContext(): EglBase.Context? {
        return eglBase?.eglBaseContext
    }
}
```

### 2. Update MainActivity

Modify `MainActivity.kt` to use our WebRTC client:

```kotlin
package com.example.screenviewer

import android.os.Bundle
import android.util.Log
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.webrtc.MediaStream
import org.webrtc.SurfaceViewRenderer
import org.webrtc.VideoTrack

class MainActivity : AppCompatActivity(), WebRTCClient.WebRTCClientListener {
    private val TAG = "MainActivity"
    
    private lateinit var remoteRenderer: SurfaceViewRenderer
    private lateinit var serverUrlEditText: EditText
    private lateinit var connectButton: Button
    private lateinit var statusTextView: TextView
    
    private var webRTCClient: WebRTCClient? = null
    private var isConnected = false
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        // Initialize views
        remoteRenderer = findViewById(R.id.remote_renderer)
        serverUrlEditText = findViewById(R.id.server_url)
        connectButton = findViewById(R.id.connect_button)
        statusTextView = findViewById(R.id.status_text)
        
        // Initialize WebRTC client
        webRTCClient = WebRTCClient(applicationContext, this)
        webRTCClient?.initWebRTC()
        
        // Initialize renderer
        remoteRenderer.init(webRTCClient?.getEglContext(), null)
        remoteRenderer.setEnableHardwareScaler(true)
        remoteRenderer.setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT)
        
        // Set up connect button
        connectButton.setOnClickListener {
            if (isConnected) {
                disconnect()
            } else {
                connect()
            }
        }
    }
    
    private fun connect() {
        val serverUrl = serverUrlEditText.text.toString().trim()
        
        if (serverUrl.isEmpty()) {
            statusTextView.text = "Please enter server URL"
            return
        }
        
        webRTCClient?.connect(serverUrl)
    }
    
    private fun disconnect() {
        webRTCClient?.disconnect()
        updateConnectButton(false)
    }
    
    private fun updateConnectButton(connected: Boolean) {
        isConnected = connected
        connectButton.text = if (connected) "Disconnect" else "Connect"
    }
    
    // WebRTCClientListener implementation
    override fun onConnectionStateChanged(state: String) {
        runOnUiThread {
            statusTextView.text = state
            updateConnectButton(state == "Connected")
        }
    }
    
    override fun onRemoteStreamAdded(stream: MediaStream) {
        Log.d(TAG, "onRemoteStreamAdded: ${stream.videoTracks.size} video tracks")
        
        if (stream.videoTracks.size > 0) {
            val videoTrack = stream.videoTracks[0]
            
            runOnUiThread {
                videoTrack.addSink(remoteRenderer)
            }
        }
    }
    
    override fun onError(error: String) {
        Log.e(TAG, "WebRTC error: $error")
        
        runOnUiThread {
            statusTextView.text = "Error: $error"
            updateConnectButton(false)
        }
    }
    
    override fun onDestroy() {
        remoteRenderer.release()
        webRTCClient?.release()
        super.onDestroy()
    }
}
```

## Building and Running the App

1. Ensure you have the WebRTC screen streaming server running on your computer.

2. Build and run the Android app on your device or emulator.

3. Enter the WebSocket URL of your server in the format:
   ```
   ws://YOUR_SERVER_IP:8080/ws
   ```
   Replace `YOUR_SERVER_IP` with the IP address of your computer on the local network.

4. Tap "Connect" to establish the WebRTC connection and view the screen stream.

## Troubleshooting

- **Connection issues**: Verify that the Android device and the server are on the same network and can reach each other. Check firewall settings.

- **Black screen**: If you see a black screen after connecting, verify that:
  - The server is capturing the screen correctly
  - The WebRTC connection is established (check logs)
  - The video track is properly added to the renderer

- **Poor performance**: Adjust the resolution and FPS on the server side to match your network capabilities.

## Next Steps

This implementation covers the basic requirements from the PRD. For a more complete application, consider implementing:

1. Connection retry logic
2. Better error handling and user feedback
3. Full-screen viewing mode
4. Settings page for different resolution/quality options
5. Screen orientation handling
6. Remote control capabilities (as mentioned in future improvements)

## Resources

- [Google WebRTC for Android](https://webrtc.github.io/webrtc-org/native-code/android/)
- [Android WebRTC samples](https://github.com/webrtc/samples)
- [OkHttp WebSocket documentation](https://square.github.io/okhttp/4.x/okhttp/okhttp3/-web-socket/) 