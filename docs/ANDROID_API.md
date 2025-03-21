# Android API Integration Guide

This document provides a comprehensive guide for integrating Android clients with the LLM PC Control server using the REST API.

## Introduction

The LLM PC Control server supports two different connection methods for Android clients:

1. **REST API Approach (Recommended)**: Standard HTTP/HTTPS requests that are well-supported on all platforms
2. **WebSocket Approach (Legacy)**: Real-time WebSocket connections (more complex and less reliable for mobile)

This guide focuses on the REST API approach, which is simpler and more reliable for mobile clients.

## Server Setup for Android

### Starting the Server

Use the provided script to start the server with Android-compatible settings:

```bash
# Basic setup
python start_android_server_rest.py

# Enable SSL (recommended for security)
python start_android_server_rest.py --ssl --self-signed-ssl

# Generate QR code for easy connection
python start_android_server_rest.py --qr

# Save QR code to a file
python start_android_server_rest.py --qr-file connection.png
```

### Server Options

- `--port`: Port to bind the server to (default: 5000)
- `--whisper-model`: Whisper model size to use (default: base)
- `--enable-translation`: Enable automatic translation
- `--no-ssl`: Disable SSL/TLS (not recommended)
- `--ssl-cert`: Path to custom SSL certificate
- `--ssl-key`: Path to custom SSL private key
- `--debug`: Run in debug mode
- `--qr`: Generate QR code for easy connection
- `--qr-file`: Save QR code to a file

## REST API Endpoints

### Discovery Endpoint

#### `GET /api/info`

Returns information about the server, its capabilities, and available endpoints.

**Response:**

```json
{
  "server": {
    "name": "LLM PC Control Server",
    "version": "1.0.0",
    "api_version": "1",
    "timestamp": "2023-03-17T12:34:56.789Z"
  },
  "capabilities": {
    "transcription": true,
    "translation": true,
    "voice_commands": true,
    "text_commands": true
  },
  "endpoints": {
    "health": "https://server-ip:port/health",
    "transcribe": "https://server-ip:port/transcribe",
    "command": "https://server-ip:port/command",
    "voice_command": "https://server-ip:port/voice-command",
    "system_info": "https://server-ip:port/api/system-info"
  }
}
```

### Health Check

#### `GET /health`

Check if the server is running and healthy.

**Response:**

```json
{
  "status": "ok",
  "timestamp": "2023-03-17T12:34:56.789Z"
}
```

### System Information

#### `GET /api/system-info`

Get information about the server system.

**Response:**

```json
{
  "platform": {
    "system": "Linux",
    "release": "5.15.0-84-generic",
    "version": "#93-Ubuntu SMP Tue Jan 30 10:26:01 UTC 2024",
    "machine": "x86_64"
  },
  "server": {
    "uptime": "1:23:45",
    "started": "2023-03-17T12:34:56.789Z"
  },
  "cpu": {
    "percent": 12.5,
    "cores": 8,
    "threads": 16
  },
  "memory": {
    "total": 16000000000,
    "available": 8000000000,
    "percent": 50.0
  },
  "disk": {
    "total": 500000000000,
    "free": 250000000000,
    "percent": 50.0
  }
}
```

### Text Commands

#### `POST /command`

Execute a text command on the server.

**Request Body:**

```json
{
  "command": "click on the start button"
}
```

**Response:**

```json
{
  "status": "success",
  "command": "click on the start button",
  "result": "Command executed successfully"
}
```

### Voice Commands

#### `POST /voice-command`

Send audio for transcription and command execution.

**Form Data:**
- `audio_file`: Audio file (supported formats: wav, mp3, ogg)
- `model_size`: Whisper model size (tiny, base, small, medium, large)
- `translate`: Whether to translate from Spanish to English (true/false)

**Alternative Form Data:**
- `audio_data`: Base64-encoded audio data
- `model_size`: Whisper model size
- `translate`: Translation flag

**Response:**

```json
{
  "status": "success",
  "transcription": "click on the start button",
  "language": "en",
  "steps": 1,
  "result": "Command executed successfully"
}
```

### Audio Transcription

#### `POST /transcribe`

Transcribe audio to text without executing commands.

**Form Data:**
- `audio_file`: Audio file (supported formats: wav, mp3, ogg)
- `model_size`: Whisper model size (tiny, base, small, medium, large)
- `translate`: Whether to translate from Spanish to English (true/false)

**Response:**

```json
{
  "status": "success",
  "transcription": "hello world",
  "language": "en",
  "translated": false
}
```

## Android Implementation Guide

### Setting Up Your Android Project

1. Add the necessary dependencies to your `build.gradle` file:

```gradle
// Retrofit for API calls
implementation 'com.squareup.retrofit2:retrofit:2.9.0'
implementation 'com.squareup.retrofit2:converter-gson:2.9.0'

// OkHttp for networking
implementation 'com.squareup.okhttp3:okhttp:4.11.0'
implementation 'com.squareup.okhttp3:logging-interceptor:4.11.0'

// For QR code scanning (optional)
implementation 'com.journeyapps:zxing-android-embedded:4.3.0'
```

2. Create API service interfaces:

```kotlin
interface LlmPcControlApi {
    @GET("api/info")
    suspend fun getApiInfo(): ApiInfo
    
    @GET("health")
    suspend fun checkHealth(): HealthResponse
    
    @GET("api/system-info")
    suspend fun getSystemInfo(): SystemInfo
    
    @POST("command")
    suspend fun executeCommand(@Body command: CommandRequest): CommandResponse
    
    @Multipart
    @POST("voice-command")
    suspend fun executeVoiceCommand(
        @Part audioFile: MultipartBody.Part,
        @Part("model_size") modelSize: RequestBody,
        @Part("translate") translate: RequestBody
    ): VoiceCommandResponse
}
```

3. Create the Retrofit client:

```kotlin
object ApiClient {
    private const val BASE_URL = "https://your-server-ip:5000/"
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        // For self-signed certificates in development
        .hostnameVerifier { _, _ -> true }
        .build()
    
    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(client)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
    
    val api: LlmPcControlApi = retrofit.create(LlmPcControlApi::class.java)
}
```

### Discovery Process

When your app starts, the recommended flow is:

1. Discover server information and endpoints:

```kotlin
viewModelScope.launch {
    try {
        val apiInfo = ApiClient.api.getApiInfo()
        
        // Save endpoints for later use
        apiInfo.endpoints?.let { endpoints ->
            commandEndpoint = endpoints.command
            voiceCommandEndpoint = endpoints.voiceCommand
        }
        
        // Check capabilities
        apiInfo.capabilities?.let { capabilities ->
            isTranscriptionAvailable = capabilities.transcription == true
            isTranslationAvailable = capabilities.translation == true
        }
        
        // Validate server is healthy
        val health = ApiClient.api.checkHealth()
        isServerHealthy = health.status == "ok"
        
    } catch (e: Exception) {
        // Handle connection errors
    }
}
```

### Sending Commands

For text commands:

```kotlin
viewModelScope.launch {
    try {
        val request = CommandRequest(command = "click on the start button")
        val response = ApiClient.api.executeCommand(request)
        
        if (response.status == "success") {
            // Command succeeded
        } else {
            // Command failed
        }
    } catch (e: Exception) {
        // Handle error
    }
}
```

For voice commands:

```kotlin
viewModelScope.launch {
    try {
        // Get audio file
        val audioFile = File(audioFilePath)
        val requestFile = audioFile.asRequestBody("audio/wav".toMediaTypeOrNull())
        val audioPart = MultipartBody.Part.createFormData(
            "audio_file", 
            audioFile.name, 
            requestFile
        )
        
        // Set parameters
        val modelSize = "base".toRequestBody("text/plain".toMediaTypeOrNull())
        val translate = "false".toRequestBody("text/plain".toMediaTypeOrNull())
        
        // Send request
        val response = ApiClient.api.executeVoiceCommand(
            audioPart,
            modelSize,
            translate
        )
        
        // Handle response
        if (response.status == "success") {
            // Show transcription and result
        }
    } catch (e: Exception) {
        // Handle error
    }
}
```

### QR Code Configuration

To use QR code for easy configuration:

1. Add QR code scanning functionality to your app
2. Scan the QR code generated by the server
3. Parse the URL from the QR code and use it as your API base URL
4. Test connection with a health check request

## SSL Certificate Handling

Android apps require proper SSL certificate handling, especially when connecting to servers with self-signed certificates.

### Option 1: Add Network Security Configuration (Recommended)

1. Create `network_security_config.xml` in your `res/xml` directory:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">your-server-ip</domain>
        <trust-anchors>
            <certificates src="@raw/server_cert"/>
        </trust-anchors>
    </domain-config>
</network-security-config>
```

2. Save your server's certificate as `server_cert.crt` in the `res/raw` directory
3. Reference the configuration in your manifest:

```xml
<application
    ...
    android:networkSecurityConfig="@xml/network_security_config">
</application>
```

### Option 2: Use a Trust Manager (Development Only)

For development purposes only, you can use a trust manager that accepts all certificates:

```kotlin
val trustAllCerts = arrayOf<TrustManager>(object : X509TrustManager {
    override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
    override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
    override fun getAcceptedIssuers() = arrayOf<X509Certificate>()
})

val sslContext = SSLContext.getInstance("SSL")
sslContext.init(null, trustAllCerts, java.security.SecureRandom())

val client = OkHttpClient.Builder()
    .sslSocketFactory(sslContext.socketFactory, trustAllCerts[0] as X509TrustManager)
    .hostnameVerifier { _, _ -> true }
    .build()
```

**Warning:** This approach bypasses SSL certificate validation and should NEVER be used in production.

## Troubleshooting

### Connection Issues

If your app cannot connect to the server:

1. Verify the server is running: `python test_rest_api.py --url https://your-server-ip:5000`
2. Check network configuration (firewalls, port forwarding)
3. Try connecting without SSL first: `--no-ssl`
4. Verify Android has proper network permissions

### SSL Certificate Issues

If you see SSL handshake failures:

1. Export the server certificate and add it to your app's trusted certificates
2. Verify the certificate includes your server's IP in the Subject Alternative Name (SAN) field
3. Check the certificate has not expired
4. Use a regular CA-signed certificate for production

## Voice Recording in Android

Capturing high-quality audio is essential for accurate voice command recognition. Here's how to implement audio recording in your Android app:

### Permissions

First, add the necessary permissions to your AndroidManifest.xml:

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" 
                 android:maxSdkVersion="28" />
```

For Android 6.0 (API level 23) and higher, you need to request permissions at runtime:

```kotlin
private fun requestRecordPermissions() {
    if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) 
            != PackageManager.PERMISSION_GRANTED) {
        ActivityCompat.requestPermissions(this,
            arrayOf(Manifest.permission.RECORD_AUDIO),
            PERMISSION_REQUEST_CODE)
    }
}
```

### Audio Recording Implementation

Here's a sample implementation for recording audio:

```kotlin
class AudioRecorder(private val context: Context) {
    private var recorder: MediaRecorder? = null
    private var filePath: String? = null
    
    fun startRecording(): String? {
        recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            MediaRecorder()
        }
        
        filePath = "${context.externalCacheDir?.absolutePath}/voice_command_${System.currentTimeMillis()}.ogg"
        
        try {
            recorder?.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.OGG)
                setAudioEncoder(MediaRecorder.AudioEncoder.OPUS)
                setAudioSamplingRate(16000)  // 16kHz is good for speech recognition
                setAudioEncodingBitRate(128000)  // 128kbps offers good quality
                setOutputFile(filePath)
                prepare()
                start()
            }
            return filePath
        } catch (e: Exception) {
            Log.e("AudioRecorder", "Recording failed: ${e.message}")
            stopRecording()
            return null
        }
    }
    
    fun stopRecording(): String? {
        try {
            recorder?.apply {
                stop()
                release()
            }
            recorder = null
            return filePath
        } catch (e: Exception) {
            Log.e("AudioRecorder", "Stop recording failed: ${e.message}")
            return null
        }
    }
}
```

### UI Implementation

Integrate recording with a simple UI:

```kotlin
class VoiceCommandActivity : AppCompatActivity() {
    private lateinit var audioRecorder: AudioRecorder
    private var isRecording = false
    private var audioFilePath: String? = null
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_voice_command)
        
        audioRecorder = AudioRecorder(this)
        
        findViewById<Button>(R.id.btnRecord).setOnClickListener {
            if (isRecording) {
                stopRecording()
            } else {
                startRecording()
            }
        }
        
        findViewById<Button>(R.id.btnSend).setOnClickListener {
            audioFilePath?.let { path ->
                sendAudioToServer(path)
            } ?: run {
                Toast.makeText(this, "No recording available", Toast.LENGTH_SHORT).show()
            }
        }
    }
    
    private fun startRecording() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) 
                == PackageManager.PERMISSION_GRANTED) {
            audioFilePath = audioRecorder.startRecording()
            isRecording = true
            updateUI()
        } else {
            requestRecordPermissions()
        }
    }
    
    private fun stopRecording() {
        audioFilePath = audioRecorder.stopRecording()
        isRecording = false
        updateUI()
    }
    
    private fun updateUI() {
        val recordButton = findViewById<Button>(R.id.btnRecord)
        recordButton.text = if (isRecording) "Stop Recording" else "Start Recording"
        
        findViewById<Button>(R.id.btnSend).isEnabled = audioFilePath != null
    }
    
    private fun sendAudioToServer(filePath: String) {
        lifecycleScope.launch {
            try {
                val file = File(filePath)
                val requestFile = file.asRequestBody("audio/ogg".toMediaTypeOrNull())
                val audioPart = MultipartBody.Part.createFormData("audio_file", file.name, requestFile)
                
                val modelSize = "base".toRequestBody("text/plain".toMediaTypeOrNull())
                val translate = "false".toRequestBody("text/plain".toMediaTypeOrNull())
                
                val response = ApiClient.api.executeVoiceCommand(audioPart, modelSize, translate)
                
                // Display results
                findViewById<TextView>(R.id.tvTranscription).text = 
                    "Transcription: ${response.transcription}"
                findViewById<TextView>(R.id.tvResult).text = 
                    "Result: ${response.result}"
                
            } catch (e: Exception) {
                Toast.makeText(this@VoiceCommandActivity, 
                    "Error: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }
}
```

### Optimizing Audio for Recognition

For better speech recognition results:

1. **Use Appropriate Sampling Rate**: 16kHz is ideal for speech recognition
2. **Format Matters**: OGG with OPUS codec provides good compression while maintaining quality
3. **Audio Processing**: Consider implementing:
   - Noise suppression
   - Auto gain control
   - Echo cancellation
   - Voice activity detection (VAD)

Android provides AudioEffect classes that can help with some of these requirements:

```kotlin
fun applyAudioEffects(audioSessionId: Int) {
    // Noise suppression
    val noiseSuppressor = if (NoiseSuppressor.isAvailable()) {
        NoiseSuppressor.create(audioSessionId)?.apply {
            enabled = true
        }
    } else null
    
    // Automatic gain control
    val automaticGainControl = if (AutomaticGainControl.isAvailable()) {
        AutomaticGainControl.create(audioSessionId)?.apply {
            enabled = true
        }
    } else null
    
    // Echo cancellation for device speakers
    val acousticEchoCanceler = if (AcousticEchoCanceler.isAvailable()) {
        AcousticEchoCanceler.create(audioSessionId)?.apply {
            enabled = true
        }
    } else null
}
```

### Streaming vs. File-Based Recording

You can implement two approaches for voice commands:

1. **File-Based (Easiest)**: Record to a file, then send the complete file
2. **Streaming (More Responsive)**: Stream audio in real-time as it's being recorded

For streaming, consider using WebSockets or chunked HTTP uploads, though this requires more complex client and server code.

### Voice Activity Detection

To automatically start and stop recording when the user speaks:

```kotlin
class VoiceActivityDetector(
    private val amplitudeThreshold: Int = 2000,
    private val silenceDurationThresholdMs: Long = 1500,
    private val onSpeechDetected: () -> Unit,
    private val onSilenceDetected: () -> Unit
) {
    private var lastNonSilentTime = 0L
    
    fun processAudioAmplitude(amplitude: Int) {
        val now = System.currentTimeMillis()
        
        if (amplitude > amplitudeThreshold) {
            if (lastNonSilentTime == 0L) {
                onSpeechDetected()
            }
            lastNonSilentTime = now
        } else if (lastNonSilentTime > 0) {
            val silenceDuration = now - lastNonSilentTime
            if (silenceDuration > silenceDurationThresholdMs) {
                onSilenceDetected()
                lastNonSilentTime = 0
            }
        }
    }
}
```

You would use this with a recording loop that regularly checks microphone amplitude.

By implementing robust audio recording with these optimizations, your Android client will provide high-quality voice recordings to the LLM PC Control server, resulting in better command recognition and execution.

## Conclusion

The REST API approach provides a simpler and more reliable method for Android clients to connect to the LLM PC Control server. By following this guide, you can integrate your Android app with the server and provide a smooth voice control experience for your users. 