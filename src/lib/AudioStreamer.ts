export class AudioStreamer {
  private inputCtx: AudioContext | null = null;
  private outputCtx: AudioContext | null = null;
  private micStream: MediaStream | null = null;
  private micSource: MediaStreamAudioSourceNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private micAnalyser: AnalyserNode | null = null;
  private playbackAnalyser: AnalyserNode | null = null;
  private activeSources: AudioBufferSourceNode[] = [];
  private nextStartTime = 0;
  private isRecording = false;

  constructor() {}

  async startRecording(
    onAudioChunk: (base64PCM: string) => void,
    onUserVolume: (vol: number) => void
  ): Promise<void> {
    if (this.isRecording) return;
    
    // Initialize Input AudioContext at 16kHz
    const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
    this.inputCtx = new AudioCtxClass({ sampleRate: 16000 });
    
    // Initialize Output AudioContext at 24kHz
    this.outputCtx = new AudioCtxClass({ sampleRate: 24000 });
    
    // Create Playback Analyser to read volume of played audio
    this.playbackAnalyser = this.outputCtx.createAnalyser();
    this.playbackAnalyser.fftSize = 128;
    this.playbackAnalyser.connect(this.outputCtx.destination);

    // Get microphone permission
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: { 
        echoCancellation: true, 
        noiseSuppression: true,
        autoGainControl: true
      } 
    });

    if (!this.inputCtx) {
      // If context was cleaned up while waiting for permission, stop the tracks and abort gracefully
      stream.getTracks().forEach(track => track.stop());
      return;
    }

    this.micStream = stream;
    this.micSource = this.inputCtx.createMediaStreamSource(this.micStream);
    
    // Create Mic Analyser to read volume of mic audio
    this.micAnalyser = this.inputCtx.createAnalyser();
    this.micAnalyser.fftSize = 128;
    this.micSource.connect(this.micAnalyser);

    // Create processor for capturing raw PCM chunk
    this.processor = this.inputCtx.createScriptProcessor(2048, 1, 1);
    this.micAnalyser.connect(this.processor);
    this.processor.connect(this.inputCtx.destination);

    this.processor.onaudioprocess = (e) => {
      if (!this.isRecording) return;
      const channelData = e.inputBuffer.getChannelData(0);
      
      // Calculate average volume / RMS
      let sum = 0;
      for (let i = 0; i < channelData.length; i++) {
        sum += channelData[i] * channelData[i];
      }
      const rms = Math.sqrt(sum / channelData.length);
      // Map to 0-100 range
      onUserVolume(Math.min(100, Math.round(rms * 300)));

      // Convert to 16-bit PCM little endian
      const pcm16Buffer = this.floatTo16BitPCM(channelData);
      const base64PCM = this.arrayBufferToBase64(pcm16Buffer);
      onAudioChunk(base64PCM);
    };

    this.isRecording = true;
    this.nextStartTime = 0;
  }

  stopRecording(): void {
    this.isRecording = false;
    
    if (this.processor) {
      try {
        this.processor.disconnect();
      } catch (e) {}
      this.processor = null;
    }
    if (this.micSource) {
      try {
        this.micSource.disconnect();
      } catch (e) {}
      this.micSource = null;
    }
    if (this.micStream) {
      try {
        this.micStream.getTracks().forEach(track => track.stop());
      } catch (e) {}
      this.micStream = null;
    }
    if (this.inputCtx) {
      try {
        this.inputCtx.close();
      } catch (e) {}
      this.inputCtx = null;
    }
    this.micAnalyser = null;
    this.stopPlayback();
  }

  playChunk(base64Audio: string, onOutputVolume?: (vol: number) => void): void {
    if (!this.outputCtx || !this.playbackAnalyser) return;
    
    try {
      const pcm16 = this.base64To16BitPCM(base64Audio);
      const float32 = this.pcmToFloat32(pcm16);
      
      const audioBuffer = this.outputCtx.createBuffer(1, float32.length, 24000);
      audioBuffer.copyToChannel(float32, 0);
      
      const sourceNode = this.outputCtx.createBufferSource();
      sourceNode.buffer = audioBuffer;
      sourceNode.connect(this.playbackAnalyser);
      
      const currentTime = this.outputCtx.currentTime;
      if (this.nextStartTime < currentTime) {
        this.nextStartTime = currentTime + 0.05;
      }
      
      sourceNode.start(this.nextStartTime);
      this.nextStartTime += audioBuffer.duration;
      
      this.activeSources.push(sourceNode);
      sourceNode.onended = () => {
        this.activeSources = this.activeSources.filter(n => n !== sourceNode);
      };

      if (onOutputVolume) {
        let sum = 0;
        for (let i = 0; i < float32.length; i++) {
          sum += float32[i] * float32[i];
        }
        const rms = Math.sqrt(sum / float32.length);
        onOutputVolume(Math.min(100, Math.round(rms * 250)));
      }
    } catch (err) {
      console.error("Error playing audio chunk:", err);
    }
  }

  stopPlayback(): void {
    this.activeSources.forEach(node => {
      try {
        node.stop();
      } catch (e) {}
    });
    this.activeSources = [];
    this.nextStartTime = 0;
  }

  isPlaying(): boolean {
    return this.activeSources.length > 0;
  }

  getMicAnalyser(): AnalyserNode | null {
    return this.micAnalyser;
  }

  getPlaybackAnalyser(): AnalyserNode | null {
    return this.playbackAnalyser;
  }

  cleanup(): void {
    this.stopRecording();
    if (this.outputCtx) {
      try {
        this.outputCtx.close();
      } catch (e) {}
      this.outputCtx = null;
    }
    this.playbackAnalyser = null;
  }

  // Conversions
  private floatTo16BitPCM(float32Array: Float32Array): ArrayBuffer {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32Array.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, float32Array[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
  }

  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    let binary = "";
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  private base64To16BitPCM(base64: string): Int16Array {
    const binaryString = atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return new Int16Array(bytes.buffer);
  }

  private pcmToFloat32(pcm16: Int16Array): Float32Array {
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768.0;
    }
    return float32;
  }
}
