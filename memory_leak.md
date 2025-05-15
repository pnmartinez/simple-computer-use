# Memory Leak Analysis & Fix Plan

## Issue Description
Each new voice command adds approximately 7GB to RAM usage, making the application unsustainable for extended use.

## Root Causes Identified

1. **Whisper Model Retention**: Each transcription loads the Whisper model but doesn't properly unload it.
   - The `transcribe_audio` function in `audio.py` loads the model each time but doesn't explicitly free resources.

2. **Screenshots Accumulation**: Screenshots are being taken and stored but may not be properly cleaned up.
   - The cleanup mechanism in `commands.py` may not be effective or getting called properly.

3. **PyTorch CUDA Memory**: CUDA memory isn't being cleared between transcriptions, causing GPU memory to fill up.

4. **Object References**: Transcription results, command history, and debug information may be retaining large objects in memory.

## Incremental Fix Plan

### Phase 1: Immediate Memory Optimization

1. **Add Explicit Model Unloading in `audio.py`**:
   ```python
   # After transcription is complete
   del model
   torch.cuda.empty_cache()  # Clear CUDA cache
   ```

2. **Fix Screenshot Cleanup**:
   - Ensure `cleanup_old_screenshots` is working properly
   - Lower the default values for `SCREENSHOT_MAX_COUNT` and `SCREENSHOT_MAX_AGE_DAYS`

3. **Implement Garbage Collection**:
   - Add explicit garbage collection after processing each command
   ```python
   # At the end of voice_command_endpoint in server.py
   import gc
   gc.collect()
   ```

### Phase 2: Structural Improvements

4. **Use Singleton Pattern for Whisper Model**:
   - Create a model manager class that reuses the model instead of loading it each time
   - Implement proper resource cleanup methods

5. **Optimize Memory-Heavy Objects**:
   - Limit size of debug information stored
   - Reduce stored history size
   - Trim large objects before storage

6. **Add Memory Monitoring**:
   - Add logging of memory usage before/after command processing
   - Create an endpoint to check current memory usage

### Phase 3: Long-Term Solutions

7. **Process Isolation**:
   - Run the Whisper transcription in a separate process that can be terminated after use
   - Consider implementing a microservices architecture for memory-intensive operations

8. **Implement Resource Pooling**:
   - Create a pool of workers for processing commands
   - Implement timeouts and resource limits

9. **Consider Alternative Transcription Methods**:
   - Evaluate lighter-weight transcription options
   - Add option to use cloud-based transcription services

## Implementation Details

To implement Phase 1 immediately:

1. Edit `llm_control/voice/audio.py`:
   ```python
   def transcribe_audio(audio_data, model_size=WHISPER_MODEL_SIZE, language=DEFAULT_LANGUAGE):
       # Existing code...
       
       try:
           # Load and use the model...
           result = model.transcribe(...)
           
           # Add these lines to release memory:
           del model
           if torch.cuda.is_available():
               torch.cuda.empty_cache()
               
           return result
   ```

2. Edit `llm_control/voice/server.py`:
   ```python
   @app.route('/voice-command', methods=['POST'])
   @cors_preflight
   def voice_command_endpoint():
       # Existing code...
       
       # After processing is complete and before returning:
       import gc
       gc.collect()
       
       return jsonify(result)
   ```

3. Edit `llm_control/voice/commands.py`:
   ```python
   # Ensure screenshot cleanup is effective
   def cleanup_old_screenshots(max_age_days=1, max_count=5):
       # Update default values to be more aggressive with cleanup
   ```

These changes should provide immediate memory usage improvement while we work on the more comprehensive solutions in Phases 2 and 3. 