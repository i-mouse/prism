import { useState, useRef, useEffect } from 'react';
import './App.css';
// Icons
import { FiUploadCloud, FiFileText, FiSend, FiCpu, FiUser, FiCheckCircle, FiAlertCircle,FiTrash2 } from 'react-icons/fi';
import { BiBot } from 'react-icons/bi';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from "rehype-highlight"
import * as signalR from '@microsoft/signalr';

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

function App() {
  // --- State ---
  const [files, setFiles] = useState<File[]>([]);
  const [uploadStatus, setUploadStatus] = useState<'ready' | 'uploading' | 'success' | 'error'>('ready');
  const [statusMessage, setStatusMessage] = useState('Ready to upload.');
  const [connectionId, setConnectionId] = useState<string>("");

  // 1. CHAT HISTORY STATE
  const [sidebarChats, setSidebarChats] = useState<any[]>([]); // Holds the list from C#
  
  // 🔥 FIX: Use sessionStorage so F5 refreshes keep the chat, but closing the tab wipes it!
  const [activeChatId, setActiveChatId] = useState<string>(() => {
    const savedChatId = sessionStorage.getItem('tender_active_chat');
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

  // 🔥 NEW: Auto-sync sessionStorage and fetch history whenever activeChatId changes!
  useEffect(() => {
    // Save to sessionStorage so it survives the F5 refresh
    sessionStorage.setItem('tender_active_chat', activeChatId);

    const fetchHistory = async () => {
      setMessages([
        { id: 'loading', role: 'ai', content: "Loading conversation...", timestamp: new Date() }
      ]);
      
      try {
        const response = await fetch(`/api/chat/${activeChatId}/history`);
        if (!response.ok) throw new Error("Failed to load history");
        
        const data = await response.json();
        
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
        } else {
          setMessages([
            { id: 'welcome', role: 'ai', content: "Hello! I am your TenderAI assistant. \n\nPlease upload a Tender or RFP document in the sidebar so I can analyze it for you.", timestamp: new Date() }
          ]);
        }
      } catch (error) {
        console.error("Error loading chat history:", error);
        setMessages([{ id: 'error', role: 'ai', content: "Sorry, I couldn't load the history.", timestamp: new Date() }]);
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
  };

  const handleSelectChat = (chatId: string) => {
    // Changing the ID automatically triggers the useEffect to fetch history!
    setActiveChatId(chatId); 
  };

  const jitterRetryPolicy = {
    nextRetryDelayInMilliseconds: (retryContext:any) => {
      if (retryContext.previousRetryCount >= 5) return null; // Stop after 5 tries
      const retryDelay = Math.pow(2, retryContext.previousRetryCount) * 1000;
      const jitter = Math.random() * 1000;
      return retryDelay + jitter;
    }
  };

  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL;

    const connection = new signalR.HubConnectionBuilder()
      .withUrl(`${baseUrl}/hubs/document`)
      .withAutomaticReconnect(jitterRetryPolicy)
      .build();

connection.on("DocumentProcessed", (data) => {
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
          }
      }
    });

    connection.start()
      .then(() => {console.log("✅ Connected to SignalR Hub!");   setConnectionId(connection.connectionId ?? "");})
      .catch(err => console.error("❌ SignalR Connection Error: ", err));

    return () => {
      connection.stop();
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

  // --- 2. REAL API UPLOAD (/rfp) ---
  const handleUpload = async () => {
    if (files.length==0) return;

  if (!connectionId) {
    setUploadStatus('error');
    setStatusMessage('Realtime connection not ready. Please wait a moment.');
    addMessage({ role: 'ai', content: '⚠️ Realtime connection is not ready yet. Please wait a few seconds and try again.' });
    return;
  }
    setUploadStatus('uploading');
    setStatusMessage('Uploading to Secure Storage...');

    const formData = new FormData();
    formData.append('UserId', 'demo-user-01'); 
    formData.append('ConnectionId',connectionId);
    formData.append('ChatId', activeChatId);

    files.forEach((file) => {
      formData.append('Files', file); // Note: 'Files' must match the C# property name
    });
    pendingFilesCount.current = files.length;
    try {
      const response = await fetch('/rfp', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      setUploadStatus('success');
      setStatusMessage('Upload Complete. Processing in background...');
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
    if (!input.trim()) return;

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
          userId : 'demo-user-01'
        }),
      });

      if (!response.ok) throw new Error('Network response was not ok');

      const data = await response.json();
      
      // 🔥 NEW: Pass ALL the enterprise metrics to the UI state
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
    switch(uploadStatus) {
      case 'success': return <FiCheckCircle size={18} />;
      case 'error': return <FiAlertCircle size={18} />;
      case 'uploading': return <FiCpu className="spin" size={18} />;
      default: return <FiFileText size={18} />;
    }
  };
// --- THE NUCLEAR OPTION ---
  const handleNukeSystem = async () => {
    const isSure = window.confirm("⚠️ WARNING: This will permanently delete ALL chats, ALL documents, and ALL AI memory across Postgres, Qdrant, and MinIO. Are you absolutely sure?");
    if (!isSure) return;

    setUploadStatus('uploading');
    setStatusMessage('Wiping entire system...');
    setIsThinking(true);

    try {
      const response = await fetch('/api/system/reset', { method: 'DELETE' });
      if (!response.ok) throw new Error("Failed to reset system");

      // 1. Clear UI State completely
      setMessages([]);
      setSidebarChats([]);
      setFiles([]);
      
      // 2. Force a fresh chat ID
      sessionStorage.removeItem('tender_active_chat');
      setActiveChatId(crypto.randomUUID());
      
      setUploadStatus('success');
      setStatusMessage('System completely wiped.');
      addMessage({ role: 'ai', content: "🧨 **System Wiped.**\n\nI have no memory of any documents or conversations prior to this exact moment. We are starting fresh. What would you like to do?" });
    } catch (error) {
      console.error(error);
      setUploadStatus('error');
      setStatusMessage('Failed to wipe databases.');
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="app-container">
     {/* --- SIDEBAR --- */}
     
      <div className="sidebar">
        <div className="brand">
          <BiBot size={28} /> TenderAI
        </div>
  {/* NUCLEAR BUTTON
        <div style={{ marginTop: 'auto', paddingTop: '20px', borderTop: '1px solid var(--border-color)' }}>
          <button className="nuke-btn" onClick={handleNukeSystem}>
            <FiTrash2 size={18} /> Nuke Entire System
          </button>
        </div> */}
        {/* NEW CHAT BUTTON */}
        <button className="primary-btn" onClick={handleNewChat} style={{ marginBottom: '20px', backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}>
          + New Chat
        </button>

        <div className="section-title">
          Current Context
        </div>

        {/* --- RESTORED UPLOAD CARD --- */}
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
          <div style={{fontWeight: 500, color: 'var(--text-primary)'}}>
            {files.length>0 ? "Change File" : "Select RFP/Tender"}
          </div>
          <div style={{fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '8px'}}>
            Supports PDF, DOCX
          </div>
          {files.length>0 && (
            <div className="file-name">
              <FiFileText style={{marginRight: '8px', verticalAlign: 'middle'}}/>
              {files.length} file(s) ready
            </div>
          )}
        </div>

        <button 
          className="primary-btn"
          onClick={handleUpload}
          disabled={files.length==0 || uploadStatus === 'uploading'}
        >
          {uploadStatus === 'uploading' ? 'Uploading...' : 'Upload & Analyze'}
        </button>

        <div className={`status-indicator status-${uploadStatus}`}>
          {getStatusIcon()}
          <span>{statusMessage}</span>
        </div>
        {/* --- END RESTORED UPLOAD CARD --- */}

        {/* RECENT CHATS LIST */}
        <div className="section-title" style={{ marginTop: '30px' }}>
          Recent RFPs
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

                  {/* 🔥 THE GOLD STANDARD: Inline Sources */}
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
                  {/* 🔥 THE HALLUCINATION GUARD: Caveat Banner */}
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
                <div className="bubble" style={{color: 'var(--text-secondary)', fontStyle: 'italic'}}>
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
              placeholder="Ask anything about the tender requirements, risks, or timeline..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button className="send-btn" onClick={handleSendMessage} disabled={!input.trim() || isThinking}>
              <FiSend size={20} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;