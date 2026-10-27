export type SessionState = 'disconnected' | 'connecting' | 'listening' | 'speaking' | 'processing';

export interface Transcription {
  id: string;
  sender: 'user' | 'model';
  text: string;
  timestamp: Date;
}

export interface WsMessage {
  type: 'state' | 'audio' | 'interrupted' | 'turnComplete' | 'transcription' | 'toolCall' | 'error';
  state?: string;
  data?: string;
  sender?: 'user' | 'model';
  text?: string;
  id?: string;
  name?: string;
  args?: any;
  message?: string;
}
