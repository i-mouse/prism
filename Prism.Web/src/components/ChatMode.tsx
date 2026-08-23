import { useState, useRef, useEffect } from 'react';
import '@/App.css';
// Icons
import { FiUploadCloud, FiFileText, FiSend, FiCpu, FiUser, FiCheckCircle, FiAlertCircle } from 'react-icons/fi';
import { BiBot } from 'react-icons/bi';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from "rehype-highlight"
import { signalRService } from '@/services/signalRService';

interface ChatSource {
  filename: string;
  score: number;
  content: string;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  content: string;
  timestamp: Date;
  caveat?: string;
  isTrusted?: boolean;
  intent?: string;
  sources?: ChatSource[];
}

// Slice 3 will refactor this into the typed component structure used by the
// Matrix UI. Preserved as-is (from the pre-Matrix single-file App.tsx) so no
// chat behavior is lost; not wired into any route yet — see App.tsx.
function ChatMode() {
  // --- State ---
  const [files, setFiles] = useState<File[]>([]);
  const [uploadStatus, setUploadStatus] = useState<'ready' | 'uploading' | 'success' | 'error'>('ready');
  const [statusMessage, setStatusMessage] = useState('Ready to upload.');
  // 'processing': files are being ingested for the active chat (from a live upload
  // or discovered via backfill on chat mount). Blocks chat input until 'ready'.
  const [ingestionStatus, setIngestionStatus] = useState<'idle' | 'processing' | 'ready'>('idle');

  // 1. CHAT HISTORY STATE
  const [sidebarChats, setSidebarChats] = useState<any[]>([]); // Holds the list from C#

  // Use sessionStorage so F5 refreshes keep the chat, but closing the tab wipes it.
  const [activeChatId, setActiveChatId] = useState<string>(() => {
    const savedChatId = sessionStorage.getItem('prism_active_chat');
    return savedChatId || crypto.randomUUID();
  });

  const userId = "demo-user-01"; // Hardcoded for demo
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const pendingFilesCount = useRef<number>(0);

  // Auto-scroll logic
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  useEffect(() => { scrollToBottom(); }, [messages, isThinking]);

  // Auto-sync sessionStorage and fetch history whenever activeChatId changes.
  useEffect(() => {
    // Save to sessionStorage so it survives the F5 refresh
    sessionStorage.setItem('prism_active_chat', activeChatId);

    // Rejoin the SignalR group for this chat (no-ops until the connection is up;
    // signalRService replays it once start() resolves).
    signalRService.joinChat(activeChatId).catch((err) =>
      console.error('Failed to join chat group:', err)
    );

    const fetchHistory = async () => {
      setMessages([
        { id: 'loading', role: 'ai', content: "Loading conversation...", timestamp: new Date() }
      ]);

      let historyMessages: ChatMessage[] = [];

      try {
        const response = await fetch(`/api/chat/${activeChatId}/history`);
        if (!response.ok) throw new Error("Failed to load history");

        const data = await response.json();

        if (data.messages && data.messages.length > 0) {
          historyMessages = data.messages;
          setMessages(historyMessages);
        } else {
          historyMessages = [
            { id: 'welcome', role: 'ai', content: "Hello! I am your Prism assistant.\n\nUpload a research paper in the sidebar and I'll audit its claims.", timestamp: new Date() }
          ];
          setMessages(historyMessages);
        }
      } catch (error) {
        console.error("Error loading chat history:", error);
        setMessages([{ id: 'error', role: 'ai', content: "Sorry, I couldn't load the history.", timestamp: new Date() }]);
        return;
      }

      // Backfill: recover summaries for files whose SignalR push may have been
      // missed (closed tab, dropped connection while this chat wasn't open).
      try {
        const filesRes = await fetch(`/api/chats/${activeChatId}/files`);
        if (!filesRes.ok) throw new Error("Failed to load chat files");

        const files: Array<{ fileName: string; summary: string | null; status: string }> = await filesRes.json();

        const alreadyMentioned = (fileName: string) =>
          historyMessages.some((m) => typeof m.content === 'string' && m.content.includes(fileName));

        for (const file of files) {
          if (file.status === 'Completed' && file.summary && !alreadyMentioned(file.fileName)) {
            addMessage({ role: 'ai', content: `✅ **Processing Complete for ${file.fileName}!**\n\n**Summary:**\n${file.summary}` });
          }
        }

        const hasInProgress = files.some((f) => f.status === 'In progress');
        setIngestionStatus(hasInProgress ? 'processing' : (files.length > 0 ? 'ready' : 'idle'));
      } catch (error) {
        console.error("Error backfilling chat files:", error);
      }
    };

    fetchHistory();
  }, [activeChatId]);

  // --- Helper: Add Message ---
  const addMessage = (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    setMessages(prev => [...prev, {
      ...msg,
      id: Date.now().toString(),
      timestamp: new Date()
    }]);
  };
  // --- CHAT NAVIGATION ---
  const handleNewChat = () => {
    // Generating a new UUID automatically triggers the useEffect to clear the screen!
    setActiveChatId(crypto.randomUUID());
    setFiles([]); // Clear the upload box
    setUploadStatus('ready');
    setStatusMessage('Ready to upload.');
    setIngestionStatus('idle');
  };

  const handleSelectChat = (chatId: string) => {
    // Changing the ID automatically triggers the useEffect to fetch history!
    setActiveChatId(chatId);
  };

  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL;

    const handleDocumentProcessed = (data: any) => {
      console.log("⚡ SignalR Message Received:", data);

      // 1. A file finished! Reduce our pending count by 1
      pendingFilesCount.current -= 1;
      const remaining = pendingFilesCount.current;

      if (data.status === 'Completed') {

        // 2. Output the summary for this specific file
        addMessage({ role: 'ai', content: `✅ **Processing Complete for ${data.fileName}!**\n\n**Summary:**\n${data.summary}` });

        // 3. Are we completely done, or still waiting on others?
        if (remaining > 0) {
          // Still waiting! Keep spinning and update the status text
          setStatusMessage(`Analyzed ${data.fileName}. ${remaining} file(s) remaining...`);
        } else {
          // All done! Turn off the animations
          setUploadStatus('success');
          setStatusMessage('All files processed successfully!');
          setIsThinking(false);
          setIngestionStatus('ready');
          addMessage({ role: 'ai', content: `🎉 **All documents have been indexed!** You can now ask me questions across all of them.` });
        }

      } else if (data.status === 'Error' || data.status === 'Failed') {
        addMessage({ role: 'ai', content: `❌ Error analyzing ${data.fileName}: ${data.summary}` });

        if (remaining > 0) {
          setStatusMessage(`Error on ${data.fileName}. ${remaining} file(s) remaining...`);
        } else {
          setUploadStatus('error');
          setStatusMessage('Processing finished with errors.');
          setIsThinking(false);
          setIngestionStatus('ready');
        }
      }
    };

    signalRService.on('DocumentProcessed', handleDocumentProcessed);
    signalRService.start(baseUrl).catch(() => {
      // Errors are already logged inside signalRService; nothing further to do here.
    });

    return () => {
      signalRService.off('DocumentProcessed', handleDocumentProcessed);
    };
  }, []);

  // --- Fetch Sidebar History on Load ---
  useEffect(() => {
    const fetchSidebar = async () => {
      try {
        const res = await fetch(`/api/chats/${userId}`);
        if (!res.ok) throw new Error("Failed to fetch chats");

        const data = await res.json();
        setSidebarChats(data);
      } catch (error) {
        console.error("Sidebar Load Error:", error);
      }
    };

    fetchSidebar();
  }, [userId]);

  // --- 1. HANDLE FILE SELECTION ---
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      // Convert the FileList object into a standard Array
      const selectedFiles = Array.from(e.target.files);
      setFiles(selectedFiles);
      setUploadStatus('ready');
      setStatusMessage(`${selectedFiles.length} file(s) selected. Click "Upload" to start.`);
    }
  };

  // --- 2. REAL API UPLOAD (/api/papers) ---
  const handleUpload = async () => {
    if (files.length == 0) return;

    // Read the live connection ID at upload time rather than trusting stale
    // React state — signalRService always reflects the current socket.
    const currentConnectionId = signalRService.connectionId;
    if (!currentConnectionId) {
      setUploadStatus('error');
      setStatusMessage('Realtime connection not ready. Please wait a moment.');
      addMessage({ role: 'ai', content: '⚠️ Realtime connection is not ready yet. Please wait a few seconds and try again.' });
      return;
    }
    setUploadStatus('uploading');
    setStatusMessage('Uploading to Secure Storage...');

    const formData = new FormData();
    formData.append('UserId', 'demo-user-01');
    formData.append('ConnectionId', currentConnectionId);
    formData.append('ChatId', activeChatId);

    files.forEach((file) => {
      formData.append('Files', file); // Note: 'Files' must match the C# property name
    });
    pendingFilesCount.current = files.length;
    try {
      const response = await fetch('/api/papers', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      setUploadStatus('success');
      setStatusMessage('Upload Complete. Processing in background...');
      setIngestionStatus('processing');
      addMessage({ role: 'ai', content: `I have received **${files.length} files**. \n\nMy brain is now reading and indexing it. I will notify you as each one finishes!.You can start asking questions shortly!` });
    } catch (error) {
      console.error("Upload Error:", error);
      setUploadStatus('error');
      setStatusMessage('Upload Failed. Check console.');
      addMessage({ role: 'ai', content: '❌ I failed to upload the file. Please check if the Backend API is running.' });
    }
  };

  // --- 3. REAL CHAT API (/api/chat/ask) ---
  const handleSendMessage = async () => {
    if (!input.trim() || ingestionStatus === 'processing') return;

    const userMsg = input;
    addMessage({ role: 'user', content: userMsg }); // Updated call
    setInput('');
    setIsThinking(true);

    try {
      const response = await fetch('/api/chat/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMsg,
          chatId: activeChatId,
          userId: 'demo-user-01'
        }),
      });

      if (!response.ok) throw new Error('Network response was not ok');

      const data = await response.json();

      addMessage({
        role: 'ai',
        content: data.answer || "I received a response, but it was empty.",
        caveat: data.caveat,
        isTrusted: data.isTrusted,
        intent: data.intent,
        sources: data.sources
      });

    } catch (error) {
      console.error("Chat Error:", error);
      addMessage({ role: 'ai', content: "⚠️ I'm having trouble connecting to the brain. Is the Python Service running?" });
    } finally {
      setIsThinking(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const getStatusIcon = () => {
    switch (uploadStatus) {
      case 'success': return <FiCheckCircle size={18} />;
      case 'error': return <FiAlertCircle size={18} />;
      case 'uploading': return <FiCpu className="spin" size={18} />;
      default: return <FiFileText size={18} />;
    }
  };
  return (
    <div className="app-container">
      {/* --- SIDEBAR --- */}

      <div className="sidebar">
        <div className="brand">
          <BiBot size={28} /> Prism
        </div>
        {/* NEW CHAT BUTTON */}
        <button className="primary-btn" onClick={handleNewChat} style={{ marginBottom: '20px', backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}>
          + New Chat
        </button>

        <div className="section-title">
          Current Context
        </div>

        {/* --- UPLOAD CARD --- */}
        <div className="upload-card" onClick={() => document.getElementById('fileInput')?.click()}>
          <input
            type="file"
            id="fileInput"
            hidden
            multiple
            onChange={handleFileChange}
            accept=".pdf,.docx,.txt"
          />
          <div className="upload-icon">
            <FiUploadCloud />
          </div>
          <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
            {files.length > 0 ? "Change File" : "Select paper"}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '8px' }}>
            Supports PDF, DOCX
          </div>
          {files.length > 0 && (
            <div className="file-name">
              <FiFileText style={{ marginRight: '8px', verticalAlign: 'middle' }} />
              {files.length} file(s) ready
            </div>
          )}
        </div>

        <button
          className="primary-btn"
          onClick={handleUpload}
          disabled={files.length == 0 || uploadStatus === 'uploading'}
        >
          {uploadStatus === 'uploading' ? 'Uploading...' : 'Upload & Analyze'}
        </button>

        <div className={`status-indicator status-${uploadStatus}`}>
          {getStatusIcon()}
          <span>{statusMessage}</span>
        </div>
        {/* --- END UPLOAD CARD --- */}

        {/* RECENT CHATS LIST */}
        <div className="section-title" style={{ marginTop: '30px' }}>
          Recent papers
        </div>

        <div className="chat-list" style={{ overflowY: 'auto', flex: 1 }}>
          {sidebarChats.length === 0 ? (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>No previous chats found.</div>
          ) : (
            sidebarChats.map((chat) => (
              <div
                key={chat.chatId}
                onClick={() => handleSelectChat(chat.chatId)}
                style={{
                  padding: '10px',
                  margin: '5px 0',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  backgroundColor: activeChatId === chat.chatId ? 'rgba(0, 120, 212, 0.1)' : 'transparent',
                  borderLeft: activeChatId === chat.chatId ? '3px solid var(--primary-color)' : '3px solid transparent'
                }}
              >
                <div style={{ fontWeight: 500, fontSize: '0.9rem', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {chat.chatTitle}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  {new Date(chat.uploadedAt).toLocaleDateString()} • {chat.status}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* --- MAIN CHAT --- */}
      <div className="chat-area">
        <div className="chat-header">
          <FiCpu size={20} color="var(--primary-color)" />
          Document Intelligence Agent
        </div>

        <div className="messages-container">
          {messages.map((msg) => (
            <div key={msg.id} className={`message-row ${msg.role}`}>

              {msg.role === 'ai' && (
                <div className="avatar ai-avatar">
                  <BiBot size={24} />
                </div>
              )}

              <div className="bubble" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>

                {/* The Answer Text */}
                <div className="markdown-body">
                  {msg.role === 'ai' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                      {typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content, null, 2)}
                    </ReactMarkdown>
                  ) : (
                    typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
                  )}
                </div>

                {/* Inline Sources */}
                {msg.sources && msg.sources.length > 0 && (
                  <div style={{ marginTop: '8px', paddingTop: '12px', borderTop: '1px solid rgba(0,0,0,0.1)' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                      SOURCES CITED:
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {Array.from(new Map(msg.sources.map(s => [s.filename, s])).values()).map((src, idx) => (
                        <span
                          key={idx}
                          title={src.content}
                          style={{ fontSize: '0.75rem', padding: '4px 10px', backgroundColor: '#e0f2fe', color: '#0369a1', borderRadius: '12px', cursor: 'help', border: '1px solid #bae6fd' }}
                        >
                          📄 {src.filename} ({(src.score * 100).toFixed(0)}% match)
                        </span>
                      ))}

                    </div>
                  </div>
                )}
                {/* Hallucination Guard: Caveat Banner */}
                {msg.caveat && (
                  <div style={{ marginTop: '4px', padding: '10px 12px', backgroundColor: '#fffbeb', borderLeft: '4px solid #f59e0b', color: '#92400e', fontSize: '0.85rem', borderRadius: '4px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                    <FiAlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                    <span>{msg.caveat}</span>
                  </div>
                )}

              </div>

              {msg.role === 'user' && (
                <div className="avatar user-avatar">
                  <FiUser size={20} />
                </div>
              )}
            </div>
          ))}

          {isThinking && (
            <div className="message-row ai">
              <div className="avatar ai-avatar"><BiBot size={24} /></div>
              <div className="bubble" style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                Thinking...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* --- INPUT --- */}
        <div className="input-container">
          <div className="input-box-wrapper">
            <textarea
              className="chat-input"
              placeholder="Ask anything about the prism requirements, risks, or timeline..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button
              className="send-btn"
              onClick={handleSendMessage}
              disabled={!input.trim() || isThinking || ingestionStatus === 'processing'}
              title={ingestionStatus === 'processing' ? 'Processing your document...' : undefined}
            >
              <FiSend size={20} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatMode;
