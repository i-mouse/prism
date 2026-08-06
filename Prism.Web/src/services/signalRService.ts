import * as signalR from '@microsoft/signalr';

const jitterRetryPolicy: signalR.IRetryPolicy = {
  nextRetryDelayInMilliseconds: (retryContext) => {
    if (retryContext.previousRetryCount >= 5) return null; // Stop after 5 tries
    const retryDelay = Math.pow(2, retryContext.previousRetryCount) * 1000;
    const jitter = Math.random() * 1000;
    return retryDelay + jitter;
  },
};

// Wraps the DocumentHub connection and keeps it joined to the active chat's
// group across reconnects, so the server can broadcast by ChatId instead of
// a ConnectionId that may go stale (HMR, network blips, tab backgrounding).
class SignalRService {
  private connection: signalR.HubConnection | null = null;
  private currentChatId: string | null = null;
  private startPromise: Promise<signalR.HubConnection> | null = null;

  start(baseUrl: string): Promise<signalR.HubConnection> {
    if (this.startPromise) return this.startPromise;

    const connection = new signalR.HubConnectionBuilder()
      .withUrl(`${baseUrl}/hubs/document`)
      .withAutomaticReconnect(jitterRetryPolicy)
      .build();

    connection.onreconnected(() => {
      console.log('✅ SignalR reconnected:', connection.connectionId);
      if (this.currentChatId) {
        this.joinChat(this.currentChatId).catch((err) =>
          console.error('❌ Failed to rejoin chat group after reconnect:', err)
        );
      }
    });

    connection.onclose((err) => {
      console.warn('⚠️ SignalR connection closed.', err);
      this.startPromise = null;
    });

    this.connection = connection;
    this.startPromise = connection
      .start()
      .then(async () => {
        console.log('✅ Connected to SignalR Hub!');
        if (this.currentChatId) {
          await this.joinChat(this.currentChatId);
        }
        return connection;
      })
      .catch((err) => {
        console.error('❌ SignalR Connection Error: ', err);
        this.startPromise = null;
        throw err;
      });

    return this.startPromise;
  }

  async joinChat(chatId: string): Promise<void> {
    this.currentChatId = chatId;
    if (!this.connection || this.connection.state !== signalR.HubConnectionState.Connected) {
      return;
    }
    try {
      await this.connection.invoke('JoinChat', chatId);
      console.log(`✅ Joined SignalR group for chat ${chatId}`);
    } catch (err) {
      console.error('❌ Failed to join chat group:', err);
    }
  }

  on(event: string, callback: (...args: any[]) => void) {
    this.connection?.on(event, callback);
  }

  off(event: string, callback?: (...args: any[]) => void) {
    this.connection?.off(event, callback as any);
  }

  get connectionId(): string | null {
    return this.connection?.connectionId ?? null;
  }

  get state(): signalR.HubConnectionState | null {
    return this.connection?.state ?? null;
  }

  async stop(): Promise<void> {
    const conn = this.connection;
    this.connection = null;
    this.startPromise = null;
    if (conn) {
      await conn.stop();
    }
  }
}

export const signalRService = new SignalRService();
